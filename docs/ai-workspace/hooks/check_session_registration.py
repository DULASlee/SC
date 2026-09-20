#!/usr/bin/env python3
"""L0 worktree commit registration gate (TASK-042, v1.1 A4).

Invoked from pre-commit. Output is ASCII only (AGENTS rule 4).

Rules:
- main-tree commit            -> pass (unchanged human/dispatcher flow)
- worktree commit, active     -> pass   (registered + same worktree)
- worktree commit, none/      -> FAIL   ("must run start-session.py first";
  released/stale-mismatch        this is the mechanism side of
                                 "no manual session bypasses L0")

Main tree is located via git-common-dir anchor (worktree-safe; P0 map
defect B: __file__/toplevel resolution reads a branch snapshot otherwise).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def git(*args) -> str:
    p = subprocess.run(["git", *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError((p.stderr or "").strip()[:200])
    return p.stdout.strip()


def norm(p) -> str:
    return str(Path(p).resolve()).replace("\\", "/").casefold()


def check(toplevel: Path, main_root: Path, sessions_dir: Path):
    """(ok, message). Pure logic, unit-tested."""
    if norm(toplevel) == norm(main_root):
        return True, "[OK] main-tree commit, registration check skipped"
    if not Path(sessions_dir).is_dir():
        return False, ("[FAIL] worktree commit without active session "
                       "registration (no sessions dir): run "
                       ".harness/scripts/start-session.py TASK-XXX first")
    want = norm(toplevel)
    for f in sorted(Path(sessions_dir).glob("*.json")):
        try:
            reg = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if reg.get("status") != "active":
            continue
        if norm(reg.get("worktree", "")) == want:
            return True, ("[OK] session registration active: task=%s "
                          "owner=%s" % (reg.get("task_id"),
                                        reg.get("owner")))
    return False, ("[FAIL] worktree commit without active session "
                   "registration: run .harness/scripts/start-session.py "
                   "TASK-XXX first")


def main() -> int:
    try:
        top = Path(git("rev-parse", "--show-toplevel"))
        common = Path(git("rev-parse", "--git-common-dir"))
        main_root = common.resolve().parent
        # main-tree runs_dir convention (coordination root = repo level, A5)
        sessions = main_root / ".harness" / "runs" / "sessions"
        ok, msg = check(top, main_root, sessions)
    except Exception as exc:  # noqa: BLE001  hook must fail closed, loudly
        print(f"[FAIL] registration gate error (fail closed): {exc}")
        return 1
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
