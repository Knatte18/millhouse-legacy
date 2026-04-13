#!/usr/bin/env python3
"""
spawn_agent.py — Python entry point for spawn-agent dispatch.

Today this only implements the Ollama backend (local GPU inference via
http://localhost:11434). Claude and Gemini still go through spawn-agent.ps1.
The long-term plan is to migrate the PS script into this module.

Contract (matches spawn-agent.ps1):
  stdout: single JSON line {"verdict": "...", "review_file": "..."}
  stderr: [spawn-agent] log lines
  exit:   0 success
          1 infrastructure error (parse failure, missing file, missing VERDICT)
          3 provider/mode not implemented
         12 backend not available (e.g. ollama daemon not reachable)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')

# Provider name → (model tag, think flag).
# think=True routes reasoning into a separate `thinking` field so the
# `response` field contains only the final answer. Thinker models need
# think=True to use their reasoning pathway; non-thinker models do not
# care either way.
OLLAMA_MODELS = {
    'ollama-glm-flash':    ('glm-4.7-flash:latest', False),
    'ollama-qwen-thinker': ('qwen3:30b-thinking',  True),
}

_THINK_BLOCK_RE = re.compile(r'<think>.*?</think>', re.DOTALL)


def strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> CoT blocks emitted by reasoning models."""
    return _THINK_BLOCK_RE.sub('', text).strip()

# GLM-4.7-Flash stability ceiling (tokens). Anything larger degrades.
OLLAMA_MAX_NUM_CTX = 98304


def log(msg: str) -> None:
    print(f'[spawn-agent] {msg}', file=sys.stderr, flush=True)


def compute_num_ctx(prompt_chars: int) -> int:
    """Size the KV cache to the prompt plus a 4k response budget.

    Rounds up to the nearest 4096 and caps at OLLAMA_MAX_NUM_CTX (96k tokens,
    the GLM-4.7-Flash stability ceiling). Chars→tokens at ~3 chars/token is
    deliberately pessimistic so that English text has headroom.
    """
    estimate = prompt_chars // 3 + 4096
    candidate = max(8192, estimate)
    candidate = ((candidate + 4095) // 4096) * 4096
    return min(candidate, OLLAMA_MAX_NUM_CTX)


def ollama_generate(model: str, prompt: str, timeout: int, think: bool) -> tuple[str, int]:
    num_ctx = compute_num_ctx(len(prompt))
    body = json.dumps({
        'model': model,
        'prompt': prompt,
        'stream': False,
        'think': think,
        'options': {'num_ctx': num_ctx},
    }).encode('utf-8')
    req = urllib.request.Request(
        f'{OLLAMA_URL}/api/generate',
        data=body,
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        payload = json.loads(r.read())
    response_text = strip_think_blocks(payload.get('response', ''))
    return response_text, num_ctx


def parse_verdict(text: str) -> str | None:
    # Tolerate markdown wrapping around the line ("**VERDICT: APPROVE**",
    # "# VERDICT: ...", "> VERDICT: ...") by stripping common decoration chars.
    pattern = re.compile(r'VERDICT:\s*(APPROVE|REQUEST_CHANGES|GAPS_FOUND)')
    for line in reversed(text.splitlines()):
        stripped = line.strip().strip('*_#>` ').strip()
        m = pattern.match(stripped)
        if m:
            return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Tool-use mode (Ollama /api/chat with tools)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the workspace. Returns the file contents with line numbers prefixed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Workspace-relative or absolute path"},
                    "offset": {"type": "integer", "description": "1-indexed starting line (optional)"},
                    "limit": {"type": "integer", "description": "Number of lines to read (optional, default 2000)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search files using ripgrep. Returns matching lines with file:line prefixes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern"},
                    "path": {"type": "string", "description": "File or directory to search (optional, defaults to workspace root)"},
                    "glob": {"type": "string", "description": "File glob filter e.g. '*.py' (optional)"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command in the workspace. Use for git commands (git diff, git log), file listings, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run"},
                },
                "required": ["command"],
            },
        },
    },
]

TOOL_OUTPUT_MAX_CHARS = 16000


def _truncate_tool_output(text: str) -> str:
    if len(text) <= TOOL_OUTPUT_MAX_CHARS:
        return text
    head = TOOL_OUTPUT_MAX_CHARS // 2
    tail = TOOL_OUTPUT_MAX_CHARS - head - 100
    return text[:head] + f'\n... [truncated {len(text) - head - tail} chars] ...\n' + text[-tail:]


def tool_read_file(workspace: str, args: dict) -> str:
    path = args.get('path', '')
    if not path:
        return 'ERROR: path is required'
    abs_path = path if os.path.isabs(path) else os.path.join(workspace, path)
    if not os.path.exists(abs_path):
        return f'ERROR: file not found: {path}'
    if os.path.isdir(abs_path):
        return f'ERROR: path is a directory: {path}'

    offset = int(args.get('offset', 1))
    limit = int(args.get('limit', 2000))
    try:
        with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
    except Exception as e:
        return f'ERROR: {e}'

    start = max(0, offset - 1)
    end = min(len(all_lines), start + limit)
    numbered = [f'{i + 1:6d}\t{all_lines[i].rstrip()}' for i in range(start, end)]
    return _truncate_tool_output('\n'.join(numbered))


def tool_grep(workspace: str, args: dict) -> str:
    pattern = args.get('pattern', '')
    if not pattern:
        return 'ERROR: pattern is required'
    path = args.get('path', workspace)
    if not os.path.isabs(path):
        path = os.path.join(workspace, path)
    glob_filter = args.get('glob', '')

    rg = shutil.which('rg')
    if rg:
        cmd = [rg, '--line-number', '--no-heading', '--color', 'never', pattern, path]
        if glob_filter:
            cmd += ['--glob', glob_filter]
    else:
        if glob_filter:
            return f'ERROR: glob filter requires ripgrep; install rg or omit glob (got: {glob_filter})'
        cmd = ['grep', '-rn', pattern, path]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=workspace)
    except subprocess.TimeoutExpired:
        return 'ERROR: grep timed out after 30s'
    except FileNotFoundError:
        return 'ERROR: rg/grep not available'

    output = result.stdout.strip()
    if not output:
        return '(no matches)'
    return _truncate_tool_output(output)


def tool_bash(workspace: str, args: dict) -> str:
    command = args.get('command', '')
    if not command:
        return 'ERROR: command is required'

    shell = shutil.which('bash') or shutil.which('bash.exe')
    try:
        if shell:
            result = subprocess.run(
                [shell, '-c', command],
                capture_output=True, text=True, timeout=60, cwd=workspace,
            )
        else:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=60, cwd=workspace,
            )
    except subprocess.TimeoutExpired:
        return 'ERROR: command timed out after 60s'

    output = ''
    if result.stdout:
        output += result.stdout
    if result.stderr:
        output += f'\n--- stderr ---\n{result.stderr}'
    if result.returncode != 0:
        output += f'\n--- exit code: {result.returncode} ---'
    return _truncate_tool_output(output.strip() or '(no output)')


TOOL_DISPATCH = {
    'read_file': tool_read_file,
    'grep': tool_grep,
    'bash': tool_bash,
}


def ollama_chat(model: str, messages: list, tools: list, num_ctx: int, timeout: int, think: bool) -> dict:
    body = json.dumps({
        'model': model,
        'messages': messages,
        'stream': False,
        'think': think,
        'tools': tools,
        'options': {'num_ctx': num_ctx},
    }).encode('utf-8')
    req = urllib.request.Request(
        f'{OLLAMA_URL}/api/chat',
        data=body,
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def run_ollama_tool_use(args) -> int:
    if args.provider_name not in OLLAMA_MODELS:
        log(f"provider '{args.provider_name}' not implemented")
        return 3
    model, think = OLLAMA_MODELS[args.provider_name]

    if not os.path.exists(args.prompt_file):
        log(f'prompt file not found: {args.prompt_file}')
        return 1

    with open(args.prompt_file, 'r', encoding='utf-8') as f:
        user_prompt = f.read()

    workspace = os.path.abspath(os.getcwd())
    num_ctx = compute_num_ctx(len(user_prompt) + 8192)
    log(f'Role={args.role} Provider={args.provider_name} Model={model} DispatchMode=tool-use PromptFile={args.prompt_file}')
    log(f'workspace={workspace} num_ctx={num_ctx} max_turns={args.max_turns}')

    messages: list = [
        {
            'role': 'system',
            'content': (
                'You are an independent code reviewer. Use the provided tools '
                '(read_file, grep, bash) to gather context. When you have enough '
                'information, output your review as markdown with a final line '
                '`VERDICT: APPROVE` or `VERDICT: REQUEST_CHANGES`. Do not call '
                'tools after producing the VERDICT line.'
            ),
        },
        {'role': 'user', 'content': user_prompt},
    ]

    final_text = ''
    for turn in range(1, args.max_turns + 1):
        try:
            response = ollama_chat(model, messages, TOOL_SCHEMAS, num_ctx, args.timeout, think)
        except urllib.error.URLError as e:
            log(f'ollama request failed on turn {turn}: {e}')
            return 12

        msg = response.get('message', {})
        content = msg.get('content', '') or ''
        tool_calls = msg.get('tool_calls') or []
        log(f'turn {turn}: content_chars={len(content)} tool_calls={len(tool_calls)}')
        messages.append(msg)

        if not tool_calls:
            final_text = content
            break

        for tc in tool_calls:
            fn = tc.get('function', {})
            name = fn.get('name', '')
            tc_args = fn.get('arguments') or {}
            if isinstance(tc_args, str):
                try:
                    tc_args = json.loads(tc_args)
                except json.JSONDecodeError:
                    tc_args = {}

            handler = TOOL_DISPATCH.get(name)
            if handler is None:
                tool_result = f'ERROR: unknown tool {name}'
            else:
                try:
                    tool_result = handler(workspace, tc_args)
                except Exception as e:
                    tool_result = f'ERROR: tool {name} raised {type(e).__name__}: {e}'

            log(f'  tool {name}({json.dumps(tc_args)[:120]}) → {len(tool_result)} chars')
            messages.append({
                'role': 'tool',
                'name': name,
                'content': tool_result,
            })
    else:
        log(f'hit max_turns={args.max_turns} without final answer')
        if not final_text:
            final_text = messages[-1].get('content', '') if messages else ''

    review_out_path = args.bulk_output_file or os.path.join(
        'plugins', 'mill', 'scripts', '..', '..', '..', '_millhouse', 'scratch',
        'tool-use-review.md',
    )
    abs_out = os.path.abspath(review_out_path)
    os.makedirs(os.path.dirname(abs_out) or '.', exist_ok=True)
    with open(abs_out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(final_text)
    log(f'tool-use review saved to {abs_out}')

    verdict = parse_verdict(final_text)
    if verdict is None:
        tail = '\n'.join(final_text.splitlines()[-20:])
        log('tool-use run did not emit VERDICT: line')
        log(tail)
        return 1

    print(json.dumps({'verdict': verdict, 'review_file': abs_out}))
    return 0


def run_ollama_bulk(args) -> int:
    if args.provider_name not in OLLAMA_MODELS:
        log(f"provider '{args.provider_name}' not implemented")
        return 3
    model, think = OLLAMA_MODELS[args.provider_name]

    if not args.bulk_output_file:
        log('--bulk-output-file is required when --dispatch-mode is bulk')
        return 1

    if not os.path.exists(args.prompt_file):
        log(f'prompt file not found: {args.prompt_file}')
        return 1

    with open(args.prompt_file, 'r', encoding='utf-8') as f:
        prompt = f.read()

    log(f'Role={args.role} Provider={args.provider_name} Model={model} Think={think} DispatchMode=bulk PromptFile={args.prompt_file}')
    log(f'prompt chars={len(prompt)}')

    try:
        response_text, num_ctx = ollama_generate(model, prompt, args.timeout, think)
    except urllib.error.URLError as e:
        log(f'ollama request failed: {e}')
        return 12

    log(f'ollama num_ctx={num_ctx} response chars={len(response_text)}')

    abs_out = os.path.abspath(args.bulk_output_file)
    os.makedirs(os.path.dirname(abs_out) or '.', exist_ok=True)
    with open(abs_out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(response_text)
    log(f'bulk worker output saved to {abs_out}')

    verdict = parse_verdict(response_text)
    if verdict is None:
        tail = '\n'.join(response_text.splitlines()[-20:])
        log('bulk worker did not emit VERDICT: line')
        log(tail)
        return 1

    print(json.dumps({'verdict': verdict, 'review_file': abs_out}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='spawn_agent.py — Python dispatch entry point')
    parser.add_argument('--role', required=True, choices=['reviewer', 'implementer'])
    parser.add_argument('--provider-name', required=True)
    parser.add_argument('--dispatch-mode', default='tool-use', choices=['tool-use', 'bulk'])
    parser.add_argument('--prompt-file', required=True)
    parser.add_argument('--bulk-output-file', default='')
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--max-turns', type=int, default=20)
    args = parser.parse_args()

    if args.provider_name not in OLLAMA_MODELS:
        log(f"provider '{args.provider_name}' not implemented in spawn_agent.py (only ollama providers are wired)")
        return 3

    if args.dispatch_mode == 'bulk':
        return run_ollama_bulk(args)
    if args.dispatch_mode == 'tool-use':
        return run_ollama_tool_use(args)
    log(f"unknown dispatch-mode: {args.dispatch_mode}")
    return 3


if __name__ == '__main__':
    sys.exit(main())
