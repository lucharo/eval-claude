# eval-claude

Run [inspect_ai](https://inspect.aisi.org.uk/) evals through the **Claude Code CLI** — use your Claude Pro/Max/Team subscription instead of per-token API billing.

Based on [UKGovernmentBEIS/inspect_ai#2986](https://github.com/UKGovernmentBEIS/inspect_ai/pull/2986), extracted as a standalone pip-installable package.

**Live dashboard:** [lucharo.github.io/eval-claude](https://lucharo.github.io/eval-claude/) — harmonized GPQA Diamond history across 5 Claude models (50 samples, 1 epoch per run).

> **Disclaimer:** the dashboard shows only completed, harmonized runs (n=50, 1 epoch). 27 historical rows were removed: 6 early runs that used a 200-sample config, plus 21 rows where the Claude subscription weekly usage cap or partial backend failures caused generations not to complete. The remaining trend is informative but not exhaustive, and the benchmark is no longer scheduled — workflows are manual-only.

## Why?

Model providers sometimes ship regressions (e.g. [Anthropic's summer incident](https://www.anthropic.com/engineering/a-postmortem-of-three-recent-issues), [GPT-4's 2023 decline](https://futurism.com/the-byte/stanford-chatgpt-getting-dumber)). This package lets you run standard benchmarks for virtually free using your existing Claude subscription — no API keys or per-token billing needed.

## Install

```bash
uv add eval-claude
```

Or from source:

```bash
uv sync
```

This installs `inspect_ai`, `inspect_evals` (standard benchmark suite), and the `claude-code/` provider.

### Prerequisites

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code): `npm install -g @anthropic-ai/claude-code`
- Authenticated: `claude auth`
- Active Claude Pro/Max/Team subscription

## Quick start

No need to clone — run directly with `uvx`:

```bash
uvx --from eval-claude inspect eval inspect_evals/arc_easy --model claude-code/haiku --limit 5 -M max_connections=5
```

## Usage

```bash
# Basic
uv run inspect eval inspect_evals/arc_easy --model claude-code/sonnet --limit 10

# Parallel (10 concurrent CLI processes)
uv run inspect eval inspect_evals/gpqa_diamond --model claude-code/opus -M max_connections=10

# Extended thinking
uv run inspect eval inspect_evals/gpqa_diamond --model claude-code/sonnet -M thinking_level=ultrathink

# Let Claude Code pick the default model
uv run inspect eval task.py --model claude-code/default
```

## Benchmark results

All benchmarks run on a ThinkPad with Claude Code CLI v2.0.76, February 2026.

### ARC Easy (5 samples)

```
╭──────────────────────────────────────────────────────────────────────────────╮
│arc_easy (5 samples): claude-code/haiku                                       │
╰──────────────────────────────────────────────────────────────────────────────╯
total time:                    0:00:25

choice
accuracy  1.000
stderr    0.000
```

### GPQA Diamond (50 samples, all models)

```bash
for model in haiku sonnet opus; do
  uv run inspect eval inspect_evals/gpqa_diamond --model claude-code/$model --limit 50 -M max_connections=10
done
```

**Haiku 4.5** (61.5% +/- 5.9%, 12:42)
```
╭──────────────────────────────────────────────────────────────────────────────╮
│gpqa_diamond (50 x 4 samples): claude-code/haiku                              │
╰──────────────────────────────────────────────────────────────────────────────╯
total time:                 0:12:42

choice
accuracy  0.615
stderr    0.059
```

**Sonnet 4.5** (78.5% +/- 4.8%, 13:20)
```
╭──────────────────────────────────────────────────────────────────────────────╮
│gpqa_diamond (50 x 4 samples): claude-code/sonnet                             │
╰──────────────────────────────────────────────────────────────────────────────╯
total time:                  0:13:20

choice
accuracy  0.785
stderr    0.048
```

**Opus 4.5** (86.0% +/- 4.5%, 14:13)
```
╭──────────────────────────────────────────────────────────────────────────────╮
│gpqa_diamond (50 x 4 samples): claude-code/opus                               │
╰──────────────────────────────────────────────────────────────────────────────╯
total time:                0:14:13

choice
accuracy  0.860
stderr    0.045
```

Results show the expected model ranking: Haiku < Sonnet < Opus.

## Provider comparison: `anthropic/` vs `claude-code/`

| Feature | `anthropic/` | `claude-code/` |
|---------|-------------|----------------|
| **Billing** | Per-token API | Subscription (Pro/Max/Team) |
| **Tool/function calling** | Full support | Not supported |
| **Vision/images** | Yes | No |
| **Streaming** | Yes | No |
| **Concurrent requests** | Configurable | Via `max_connections` |
| **Extended thinking** | Fine-grained (up to 200k tokens) | Coarse-grained via `thinking_level` |
| **Token usage** | Real counts | Real counts |
| **Cost tracking** | Via API | From CLI JSON |

## Model args

| Arg | Default | Description |
|-----|---------|-------------|
| `skip_permissions` | `True` | Skip permission prompts (`--dangerously-skip-permissions`) |
| `timeout` | `300` | CLI timeout in seconds |
| `max_connections` | `1` | Concurrent CLI processes |
| `thinking_level` | `"none"` | `"none"`, `"think"` (~4k tokens), `"megathink"` (~10k), `"ultrathink"` (~32k) |

## Extended thinking

The CLI uses magic words to trigger thinking budgets ([Simon Willison's blog](https://simonwillison.net/2025/Apr/19/claude-code-best-practices/)):

| `thinking_level` | Approx. tokens |
|------------------|----------------|
| `none` (default) | 0 |
| `think` | ~4,000 |
| `megathink` | ~10,000 |
| `ultrathink` | ~32,000 |

Less granular than the API's `budget_tokens` parameter (up to 200k).

## Model names

Passed directly to the CLI. Accepts aliases (`sonnet`, `opus`, `haiku`) and full model IDs (`claude-sonnet-4-5-20250929`). Use `--model claude-code/default` to let Claude Code choose its default model.

## Environment

- `CLAUDE_CODE_COMMAND` — override the CLI path (default: `claude` from PATH)

## Implementation notes

- **CLI discovery**: Supports `CLAUDE_CODE_COMMAND` env var for custom paths
- **Model names**: Passed directly to the CLI — it handles aliases and full model IDs natively
- **Token usage**: Extracted from the CLI's JSON output (`--output-format json`)
- **Cost & timing**: Extracted from CLI JSON (`total_cost_usd`, `duration_ms`, `duration_api_ms`, `session_id`)
- **Tools disabled**: Uses `--tools ""` to disable Claude Code's built-in tools for clean eval responses

## Development

```bash
uv sync --extra dev
uv run pytest tests/ -v
```

## License

MIT
