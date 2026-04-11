# Claude Code with Local LLMs

How to make `claude -p` (Claude Code's non-interactive mode) talk to a local LLM instead of Anthropic's API. This is how spawn-agent.ps1 delegates review tasks to local models.

## The Key Insight

Claude Code uses the Anthropic Messages API (`/v1/messages`). vLLM 0.19+ implements this endpoint natively. By setting `ANTHROPIC_BASE_URL` to point at vLLM, Claude Code talks to your local model without knowing the difference.

```
claude --bare -p "<prompt>"
  → ANTHROPIC_BASE_URL (http://localhost:8000)
  → vLLM /v1/messages endpoint
  → Qwen3-Coder on GPU
  → response back to Claude Code
```

No proxy, no translation layer, no LiteLLM needed (when using vLLM).

## Required Environment Variables

Set these in PowerShell before calling `claude`:

```powershell
$env:ANTHROPIC_BASE_URL = "http://localhost:8000"
$env:ANTHROPIC_API_KEY = "dummy"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = "default"
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = "default"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = "default"
```

### Why each variable is needed

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_BASE_URL` | Redirects all API calls to vLLM instead of api.anthropic.com |
| `ANTHROPIC_API_KEY` | Claude Code requires an API key. Any value works — vLLM ignores it |
| `ANTHROPIC_DEFAULT_*_MODEL` | Claude Code sends model names like `claude-sonnet-4-6`. vLLM doesn't have that model. These variables remap to `default` (the `--served-model-name` in vLLM) |

## The `--bare` Flag

**Mandatory for local models.** Without it, Claude Code hangs.

```powershell
# HANGS — do not use
claude -p "Say hi"

# WORKS
claude --bare -p "Say hi"
```

### Why it hangs without --bare

Claude Code does several things on startup:
1. Contacts api.anthropic.com for MCP server configuration
2. Runs hooks (UserPromptSubmit, etc.)
3. Syncs plugins
4. Sends attribution headers

With `ANTHROPIC_BASE_URL` pointing at vLLM, step 1 sends MCP requests to vLLM, which doesn't understand them. Claude Code waits indefinitely.

`--bare` skips all of this: no hooks, no LSP, no plugin sync, no attribution, no MCP. Just sends the prompt and gets a response.

### What --bare disables

| Feature | Disabled? | Impact |
|---------|-----------|--------|
| Hooks (UserPromptSubmit etc.) | Yes | No pre/post processing |
| LSP integration | Yes | No IDE features |
| Plugin sync | Yes | No millhouse plugins |
| Attribution header | Yes | No per-request hash (important — see below) |
| MCP servers | Yes | No external tools |
| Auto-memory | Yes | No memory system |
| CLAUDE.md discovery | Yes | No project instructions loaded |

### Attribution Header

Claude Code injects a per-request hash into the system prompt. This breaks vLLM's prefix caching because the prompt changes every request. `--bare` disables this automatically.

If you ever need to run without `--bare` (not recommended), set this in `~/.claude/settings.json`:
```json
{
  "env": {
    "CLAUDE_CODE_ATTRIBUTION_HEADER": "0"
  }
}
```

**Warning:** This affects ALL Claude Code sessions globally, including your main Anthropic-connected session. Only do this if you know what you're doing.

## Tool Use

Local models can use Claude Code's tools (Read, Write, Edit, Grep, Bash) through `claude --bare -p`. This works because:

1. Claude Code sends tool definitions to the model via the Anthropic Messages API
2. The model generates tool calls in its native format
3. vLLM's `--tool-call-parser qwen3_xml` translates these to Anthropic tool_use blocks
4. Claude Code executes the tool and sends results back
5. The model processes results and continues

### Confirmed working tools

| Tool | Status | Notes |
|------|--------|-------|
| Read | Works | Multi-turn, reads file content correctly |
| Write | Works | Creates files with correct content |
| Grep | Works | Multi-turn, finds and counts matches |
| Edit | Not tested | Expected to work (same mechanism as Read/Write) |
| Bash | Not tested | Expected to work |

### Tool use example

```powershell
claude --bare -p "Read the file CLAUDE.md and summarize it" --model default --max-turns 5
```

The `--max-turns` flag limits how many API round-trips are allowed. Each tool call consumes a turn:
1. Model requests Read tool → turn 1
2. Claude Code executes Read, sends result → turn 2
3. Model writes summary → turn 3

### Recommended --max-turns values

| Task type | --max-turns | Reasoning |
|-----------|-------------|-----------|
| Simple question | 1 | No tool use needed |
| Read + analyze | 5 | 1-2 reads + response |
| Code review | 10 | Multiple reads + analysis |
| Review + fix | 20 | Reads + edits + verification |

### Tool call parser is critical

**Must use `--tool-call-parser qwen3_xml` when starting vLLM.** Other parsers produce broken tool calls:

| Parser | Result |
|--------|--------|
| `qwen3_xml` | Correct Anthropic tool_use blocks. Works. |
| `hermes` | Tool calls appear as raw text (`<function=Read>...</function>`). Claude Code sees it as plain text, not a tool call. |
| `qwen3_coder` | Known issues with infinite token streams ("!!!!!!!!") on longer inputs. |

## Model Quality for Reviews

Qwen3-Coder-30B produces good review output. It:
- Identifies real bugs (division by zero, None handling)
- Suggests Pythonic improvements
- Generates working code in suggestions
- Follows review format instructions

It is not Claude-quality, but sufficient for automated review gates where the orchestrator (Claude) makes final decisions.

## Output Format

Use `--output-format json` to capture structured output:

```powershell
claude --bare -p "Review this code: ..." --model default --max-turns 5 --output-format json > result.json
```

The JSON includes:
- `result`: the model's text output
- `num_turns`: how many API round-trips occurred
- `duration_ms`: total wall time
- `usage.output_tokens`: tokens generated
- `stop_reason`: why the model stopped (`end_turn`, `tool_use`, `max_tokens`)

## Common Pitfalls

### "Execution error" when pressing Ctrl+C
This is normal — it's Claude Code's way of saying the request was cancelled. Not a real error.

### Model says "I'm Claude Code"
Normal. `claude --bare` injects a system prompt that says "You are Claude Code." The local model plays along. For review tasks, you provide your own system prompt that overrides this.

### Response seems slow
First request after vLLM startup is slower (KV cache warmup, CUDA graph capture). Subsequent requests are faster. Measure from the second request onward.

### "Not logged in" error
Environment variables are not set. Check `echo $env:ANTHROPIC_BASE_URL` — it must be set in the same PowerShell session.

### Model keeps calling tools forever
Set `--max-turns` to limit round-trips. Without it, the model may loop if it keeps wanting to read more files.
