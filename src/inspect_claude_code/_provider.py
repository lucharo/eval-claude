"""Claude Code CLI provider for inspect_ai.

Uses the `claude` CLI to run evals via Claude Pro/Max/Team subscription
instead of per-token API billing.

Usage:
    inspect eval inspect_evals/arc_easy --model claude-code/sonnet --limit 100

Model args:
    skip_permissions: bool - Skip permission prompts (default: True for automation)
    timeout: int - CLI timeout in seconds (default: 300)
    max_connections: int - Number of concurrent CLI processes (default: 1)
    thinking_level: str - "none", "think", "megathink", "ultrathink" (default: "none")
"""

import asyncio
import json
import os
import shutil
import subprocess
from typing import Any

from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    GenerateConfig,
    ModelAPI,
    ModelOutput,
    ModelUsage,
)
from inspect_ai.model._model_output import ChatCompletionChoice
from inspect_ai.tool import ToolChoice, ToolInfo

# Thinking level magic words for Claude Code CLI
# These trigger extended thinking with different token budgets
THINKING_LEVELS: dict[str, str] = {
    "none": "",
    "think": "think",  # ~4,000 tokens
    "megathink": "megathink",  # ~10,000 tokens
    "ultrathink": "ultrathink",  # ~31,999 tokens
}


def find_claude_cli() -> str:
    """Find the claude CLI executable.

    Checks CLAUDE_CODE_COMMAND env var first (for custom paths),
    then falls back to PATH lookup.
    """
    custom_cmd = os.environ.get("CLAUDE_CODE_COMMAND")
    if custom_cmd:
        if os.path.isfile(custom_cmd):
            return custom_cmd
        found = shutil.which(custom_cmd)
        if found:
            return found
        return custom_cmd

    claude_path = shutil.which("claude")
    if claude_path:
        return claude_path

    raise RuntimeError(
        "Claude Code CLI not found.\n\n"
        "Install it with:\n"
        "  npm install -g @anthropic-ai/claude-code\n\n"
        "Or set CLAUDE_CODE_COMMAND environment variable to the full path.\n"
        "Make sure to authenticate with: claude auth"
    )


def messages_to_prompt(messages: list[ChatMessage]) -> str:
    """Convert chat messages to a single prompt string.

    Claude Code expects a single prompt, not a message array,
    so we concatenate with role prefixes.
    """
    parts = []
    for msg in messages:
        role = msg.role.capitalize()
        parts.append(f"[{role}]: {msg.text}")
    return "\n\n".join(parts)


class ClaudeCodeAPI(ModelAPI):
    """Claude Code CLI provider.

    Uses your Claude Pro/Max/Team subscription via the `claude` CLI
    instead of per-token API billing.

    Examples:
        inspect eval task.py --model claude-code/sonnet
        inspect eval task.py --model claude-code/opus
        inspect eval task.py --model claude-code/default

    Limitations:
        - No custom tool/function calling — uses --tools "" to disable
          Claude Code's built-in tools for clean eval responses
    """

    def __init__(
        self,
        model_name: str,
        base_url: str | None = None,
        api_key: str | None = None,
        config: GenerateConfig = GenerateConfig(),
        skip_permissions: bool = True,
        timeout: int = 300,
        max_connections: int = 1,
        thinking_level: str = "none",
        **model_args: Any,
    ) -> None:
        use_default = model_name.lower() == "default"

        super().__init__(
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            config=config,
        )

        self._cli_path = find_claude_cli()
        self._model_arg = None if use_default else model_name
        self._skip_permissions = skip_permissions
        self._timeout = timeout
        self._max_connections = max_connections

        if thinking_level not in THINKING_LEVELS:
            valid = ", ".join(f'"{k}"' for k in THINKING_LEVELS)
            raise ValueError(
                f"Invalid thinking_level: '{thinking_level}'. Must be one of: {valid}"
            )
        self._thinking_level = THINKING_LEVELS[thinking_level]

    def max_connections(self) -> int:
        return self._max_connections

    async def generate(
        self,
        input: list[ChatMessage],
        tools: list[ToolInfo],
        tool_choice: ToolChoice,
        config: GenerateConfig,
    ) -> ModelOutput:
        if tools:
            raise NotImplementedError(
                "Claude Code provider does not support custom tools. "
                "The CLI's built-in tools are disabled for clean eval responses."
            )

        prompt = messages_to_prompt(input)

        if self._thinking_level:
            prompt = f"{self._thinking_level}\n\n{prompt}"

        cmd = [
            self._cli_path,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--tools",
            "",
        ]

        if self._model_arg:
            cmd.extend(["--model", self._model_arg])

        if self._skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        return await asyncio.to_thread(self._run_cli, cmd, self._timeout)

    def _run_cli(self, cmd: list[str], timeout: int) -> ModelOutput:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ModelOutput.from_content(
                model=self.model_name,
                content="",
                stop_reason="unknown",
                error=f"Claude Code CLI timed out after {timeout} seconds",
            )
        except FileNotFoundError:
            return ModelOutput.from_content(
                model=self.model_name,
                content="",
                stop_reason="unknown",
                error=f"Claude Code CLI not found at: {self._cli_path}",
            )
        except Exception as e:
            return ModelOutput.from_content(
                model=self.model_name,
                content="",
                stop_reason="unknown",
                error=f"Claude Code CLI error: {e}",
            )

        if proc.returncode != 0:
            error_msg = proc.stderr.strip() or f"Exit code {proc.returncode}"
            return ModelOutput.from_content(
                model=self.model_name,
                content="",
                stop_reason="unknown",
                error=f"Claude Code CLI failed: {error_msg}",
            )

        return self._parse_json_response(proc.stdout)

    def _parse_json_response(self, stdout: str) -> ModelOutput:
        stdout = stdout.strip()
        if not stdout:
            return ModelOutput.from_content(
                model=self.model_name,
                content="",
                stop_reason="unknown",
                error="Empty response from Claude Code CLI",
            )

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return ModelOutput.from_content(
                model=self.model_name,
                content="",
                stop_reason="unknown",
                error=f"Failed to parse Claude Code CLI response as JSON: {stdout[:200]}",
            )

        content = self._extract_content(data)
        usage = self._extract_usage(data)
        metadata = self._extract_metadata(data, usage)
        error = self._extract_error(data)

        return ModelOutput(
            model=self.model_name,
            choices=[
                ChatCompletionChoice(
                    message=ChatMessageAssistant(
                        content=content,
                        model=self.model_name,
                        source="generate",
                    ),
                    stop_reason="stop" if not error else "unknown",
                )
            ],
            usage=ModelUsage(
                input_tokens=usage["input"],
                output_tokens=usage["output"],
                total_tokens=usage["total"],
            ),
            metadata=metadata if metadata else None,
            error=error,
        )

    def _extract_content(self, data: Any) -> str:
        if isinstance(data, str):
            return data
        if not isinstance(data, dict):
            return ""
        for key in ("result", "content", "text"):
            if key in data:
                return str(data[key])
        return ""

    def _extract_usage(self, data: Any) -> dict[str, int]:
        usage_data = data.get("usage", {}) if isinstance(data, dict) else {}
        input_tokens = usage_data.get("input_tokens", 0)
        output_tokens = usage_data.get("output_tokens", 0)
        cache_creation = usage_data.get("cache_creation_input_tokens", 0)
        cache_read = usage_data.get("cache_read_input_tokens", 0)

        return {
            "input": input_tokens,
            "output": output_tokens,
            "cache_creation": cache_creation,
            "cache_read": cache_read,
            "total": input_tokens + output_tokens + cache_creation,
        }

    def _extract_metadata(
        self, data: Any, usage: dict[str, int]
    ) -> dict[str, Any] | None:
        if not isinstance(data, dict):
            return None

        metadata: dict[str, Any] = {}

        if "total_cost_usd" in data:
            metadata["cost_usd"] = data["total_cost_usd"]
        if "duration_ms" in data:
            metadata["duration_ms"] = data["duration_ms"]
        if "duration_api_ms" in data:
            metadata["duration_api_ms"] = data["duration_api_ms"]
        if "session_id" in data:
            metadata["session_id"] = data["session_id"]

        if usage["cache_creation"] > 0:
            metadata["cache_creation_input_tokens"] = usage["cache_creation"]
        if usage["cache_read"] > 0:
            metadata["cache_read_input_tokens"] = usage["cache_read"]

        return metadata if metadata else None

    def _extract_error(self, data: Any) -> str | None:
        if not isinstance(data, dict):
            return None

        if data.get("is_error"):
            return str(data.get("result", "Unknown error"))
        elif data.get("type") == "error":
            return str(data.get("result", data.get("message", "Unknown error")))

        return None
