"""Provider registration for inspect_ai discovery."""

from inspect_ai.model import modelapi


@modelapi(name="claude-code")
def claude_code():
    from ._provider import ClaudeCodeAPI

    return ClaudeCodeAPI
