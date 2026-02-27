# eval-claude

Run [inspect_ai](https://inspect.aisi.org.uk/) evals through the **Claude Code CLI** — use your Claude Pro/Max/Team subscription instead of per-token API billing.

Based on [UKGovernmentBEIS/inspect_ai#2986](https://github.com/UKGovernmentBEIS/inspect_ai/pull/2986), extracted as a standalone pip-installable package.

## Install

```bash
pip install eval-claude
```

Or from source:

```bash
pip install -e .
```

This installs both `inspect_ai` and `inspect_evals` (standard benchmark suite) as dependencies.

### Prerequisites

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code): `npm install -g @anthropic-ai/claude-code`
- Authenticated: `claude auth`
- Active Claude Pro/Max/Team subscription

## Usage

```bash
# Basic
inspect eval inspect_evals/mmlu_0_shot --model claude-code/sonnet --limit 10

# Parallel (10 concurrent CLI processes)
inspect eval inspect_evals/gpqa_diamond --model claude-code/opus -M max_connections=10

# Extended thinking
inspect eval inspect_evals/gpqa_diamond --model claude-code/sonnet -M thinking_level=ultrathink

# Let Claude Code pick the default model
inspect eval task.py --model claude-code/default
```

## Model args

| Arg | Default | Description |
|-----|---------|-------------|
| `skip_permissions` | `True` | Skip permission prompts (`--dangerously-skip-permissions`) |
| `timeout` | `300` | CLI timeout in seconds |
| `max_connections` | `1` | Concurrent CLI processes |
| `thinking_level` | `"none"` | `"none"`, `"think"` (~4k tokens), `"megathink"` (~10k), `"ultrathink"` (~32k) |

## Model names

Passed directly to the CLI. Accepts aliases (`sonnet`, `opus`, `haiku`) and full IDs (`claude-sonnet-4-5-20250929`).

## Limitations

- No tool/function calling (CLI tools are disabled for clean eval responses)
- No vision/image support
- No streaming
- Extended thinking is coarse-grained (magic words, not `budget_tokens`)

## Environment

- `CLAUDE_CODE_COMMAND` — override the CLI path (default: `claude` from PATH)

## Provider comparison: `anthropic/` vs `claude-code/`

| Feature | `anthropic/` | `claude-code/` |
|---------|-------------|----------------|
| Billing | Per-token API | Subscription |
| Tool calling | Full | None |
| Vision | Yes | No |
| Streaming | Yes | No |
| Concurrent | Configurable | Via `max_connections` |
| Extended thinking | Fine-grained (up to 200k) | Coarse (`thinking_level`) |
| Token usage | Real counts | Real counts |
| Cost tracking | Via API | From CLI JSON |

## License

MIT
