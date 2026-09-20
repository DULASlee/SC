#!/usr/bin/env python3
"""L0/L2 worktree commit gate (TASK-042 -> TASK-045), ASCII output only.

Rules (ownership = single authority, <runs>/ownership/):
- main-tree commit                  -> pass (human/dispatcher flow intact)
- worktree commit, claimed by a
  session bound to this worktree    -> pass
- otherwise                         -> FAIL (claim first: start-session.py)

Main tree located via git-common-dir anchor (worktree-safe). Physical
worktree/branch isolation lives in start-session.py; this gate enforces
"execute: Owner only" at commit time (§7.1). No bypass by design.
"""
from __future__ import annotations

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


def check(toplevel: Path, main_root: Path, runs_dir: Path):
    """(ok, message). Pure logic, unit-tested. reads ownership registry."""
    if norm(toplevel) == norm(main_root):
        return True, "[OK] main-tree commit, ownership check skipped"
    sys.path.insert(0, str(Path(main_root) / ".harness" / "scripts"))
    import ownership
    rec = ownership.worktree_owner(runs_dir, toplevel)
    if rec:
        return True, ("[OK] ownership claimed: task=%s session=%s"
                      % (rec.get("task_id"), rec.get("owner_session_id")))
    return False, ("[FAIL] worktree commit without active ownership claim"
                   " (no session bound to this worktree): run"
                   " .harness/scripts/start-session.py TASK-XXX first")


def main() -> int:
    try:
        top = Path(git("rev-parse", "--show-toplevel"))
        common = Path(git("rev-parse", "--git-common-dir"))
        main_root = common.resolve().parent
        runs_dir = main_root / ".harness" / "runs"
        ok, msg = check(top, main_root, runs_dir)
    except Exception as exc:  # noqa: BLE001  fail closed, loudly
        print(f"[FAIL] ownership gate error (fail closed): {exc}")
        return 1
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
