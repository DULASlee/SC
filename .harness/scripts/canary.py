#!/usr/bin/env python3
"""canary 存活探针：派发前验证执行器链路可用并留证。

用法：
  python .harness/scripts/canary.py [--run-dir DIR]

行为：经 run-exec.py 真起一条 dsh headless 会话
（`dsh --profile headless "Reply with exactly: alive-probe"`，
argv 模板取 dispatch.yaml 的 executor_argv），要求 exit==0 且
stdout 含 alive-probe；通过后 record_state() 把现状快照写入
`.harness/runs/.canary-state.json`。dispatch 派发前调
is_required(cfg)：现状与 state 任一变化（或缺文件）即整轮拒绝派发。
铁律：无 --skip-canary 逃生口。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = HARNESS_DIR.parent
SCRIPTS_DIR = HARNESS_DIR / "scripts"
RUN_EXEC = SCRIPTS_DIR / "run-exec.py"
DISPATCH_YAML = HARNESS_DIR / "dispatch.yaml"

PROBE_TEXT = "Reply with exactly: alive-probe"
STATE_NAME = ".canary-state.json"


def state_path() -> Path:
    return HARNESS_DIR / "runs" / STATE_NAME


def run_exec_sha1() -> str:
    try:
        return hashlib.sha1(
            RUN_EXEC.read_bytes()).hexdigest()
    except OSError:
        return "missing"


def node_version() -> str:
    try:
        p = subprocess.run(["node", "--version"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=15)
        v = (p.stdout or "").strip()
        return v if p.returncode == 0 and v else "unknown"
    except Exception:
        return "unknown"


def machine_name() -> str:
    try:
        return platform.node() or "unknown"
    except Exception:
        return "unknown"


def _load_dispatch_argv() -> list:
    import yaml
    with open(DISPATCH_YAML, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return list(cfg.get("executor_argv") or [])


def current_snapshot(executor_argv: list | None = None) -> dict:
    if executor_argv is None:
        executor_argv = _load_dispatch_argv()
    return {
        "executor_argv": list(executor_argv),
        "run_exec_sha1": run_exec_sha1(),
        "node_version": node_version(),
        "machine": machine_name(),
    }


def record_state(executor_argv: list | None = None) -> Path:
    """留证：现状快照 + ts 写 state 文件，返回 state 路径。"""
    snap = current_snapshot(executor_argv)
    snap["ts"] = datetime.now(timezone.utc).isoformat()
    sp = state_path()
    sp.parent.mkdir(parents=True, exist_ok=True)
    tmp = sp.with_name(sp.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(sp)
    return sp


def is_required(cfg: dict) -> bool:
    """现状与 state 任一变化即 True；缺文件/坏文件即 True（fail-closed）。"""
    cur = current_snapshot(cfg.get("executor_argv"))
    sp = state_path()
    if not sp.exists():
        return True
    try:
        saved = json.loads(sp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    for k in ("executor_argv", "run_exec_sha1", "node_version", "machine"):
        if saved.get(k) != cur.get(k):
            return True
    return False


def probe(executor_argv: list, run_dir: str | Path) -> tuple[bool, str]:
    """经 run-exec.py 真起 dsh 探针，判 exit==0 且 stdout 含 alive-probe。"""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    argv = [(PROBE_TEXT if a == "{prompt}" else a)
            for a in (executor_argv or [])]
    cmd = [sys.executable, str(RUN_EXEC), "--run-dir", str(run_dir),
           "--", *argv]
    try:
        subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    except Exception as exc:
        return False, f"canary 拉起失败：{type(exc).__name__}: {exc}"
    try:
        code = int((run_dir / "exitcode.txt").read_text(
            encoding="utf-8").strip())
    except (OSError, ValueError):
        return False, "canary 无 exitcode（run-exec 未落盘）"
    out = ""
    try:
        out = (run_dir / "stdout.log").read_text(
            encoding="utf-8", errors="replace")
    except OSError:
        pass
    if code == 0 and "alive-probe" in out:
        return True, "canary 存活"
    tail = "\n".join(out.splitlines()[-5:])[:300]
    return False, f"canary 失败：exit={code} stdout尾={tail!r}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default=None)
    args = ap.parse_args()
    argv = _load_dispatch_argv()
    rd = Path(args.run_dir) if args.run_dir else (
        HARNESS_DIR / "runs" / ".canary-probe")
    ok, msg = probe(argv, rd)
    print(f"[{'OK' if ok else 'FAIL'}] {msg}")
    if not ok:
        return 1
    sp = record_state(argv)
    print(f"[OK] canary 留证：{sp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
