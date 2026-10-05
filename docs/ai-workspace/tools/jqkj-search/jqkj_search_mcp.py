#!/usr/bin/env python3
"""MCP stdio shim for jqkj-search (TASK: make the self-built search tool loadable as one MCP server).

Single tool exposed: jqkj_search(args: string) -> raw CLI output.
Passes argv through to jqkj_search.py (doc/sym subcommands, --json etc.).
No third-party deps: newline-delimited JSON-RPC 2.0 over stdio.
"""
import json
import shlex
import subprocess
import sys
from pathlib import Path

SEARCH = Path(__file__).resolve().parent / "jqkj_search.py"

TOOL = {
    "name": "jqkj_search",
    "description": "Precise doc/code search for F:/JQKJ. args examples: 'doc <query> --top 6 --json' or 'sym <Name> --refs'. Add --root only if overriding the default repo root.",
    "inputSchema": {
        "type": "object",
        "properties": {"args": {"type": "string", "description": "CLI arguments for jqkj_search.py"}},
        "required": ["args"],
    },
}


def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def call_tool(tool_args):
    argv = shlex.split(tool_args.get("args", ""))
    if not argv:
        return "error: empty args"
    r = subprocess.run([sys.executable, str(SEARCH), *argv],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.returncode != 0 else "")
    return out or "(no output)"


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        mid = msg.get("id")
        method = msg.get("method", "")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "jqkj-search", "version": "0.1.0"}}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [TOOL]}})
        elif method == "tools/call":
            params = msg.get("params", {}) or {}
            targs = params.get("arguments", {}) or {}
            try:
                text = call_tool(targs)
                send({"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": text}], "isError": False}})
            except Exception as e:
                send({"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": "error: %s" % e}], "isError": True}})
        elif mid is not None and method not in ("notifications/initialized",):
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found: %s" % method}})


if __name__ == "__main__":
    main()
