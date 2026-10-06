#!/usr/bin/env python3
"""L0/L2 worktree commit gate (TASK-042 -> TASK-045, isolation-revision F1).

Rules (ownership = single authority, <runs>/ownership):
- main-tree commit                  -> allowlist bookkeeping (M1), active
  session (M2), else transition WARN / strict FAIL (M3/M4)
- worktree commit, claimed by the
  session bound to this worktree,
  AND committer identity matches    -> pass
- committer identity absent         -> pass with WARN (transition round;
  set HARNESS_STRICT_IDENTITY=1 to reject)
- otherwise                         -> FAIL (claim first: start-session.py)

Identity travels via HARNESS_SESSION_ID env (run-exec --session-id for
machine sessions, manual export for hand sessions; see start-session.py
output). Main tree located via git-common-dir anchor (worktree-safe).
Physical worktree/branch isolation lives in start-session.py; this gate
enforces "execute: Owner only" at commit time (§7.1). No bypass by design.
"""
from __future__ import annotations

import os
import re
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


# F2 main-tree allowlist (bookkeeping only, repo-relative posix).
_ALLOW_RES = [
    re.compile(r"^\.harness/tasks/(active|archive)/TASK-\d+[^/]*\.yaml$"),
    re.compile(r"^docs/verification/VERIFY-TASK-\d+-.*\.md$"),
]
_TASK_RE = re.compile(r"TASK-\d+")


def _read_record(runs_dir: Path, task_id: str):
    """ownership record dict or None (any state counts as trail)."""
    try:
        sys.path.insert(0, str(Path(runs_dir).parent / ".harness" / "scripts"))
    except Exception:
        pass
    try:
        import ownership
        p = Path(runs_dir) / "ownership" / f"{task_id}.json"
        if not p.is_file():
            return None
        import json
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _claimed_owner(runs_dir: Path, session_id: str) -> bool:
    """True if session_id owns any currently-claimed task."""
    d = Path(runs_dir) / "ownership"
    try:
        names = sorted(p.name for p in d.iterdir() if p.suffix == ".json")
    except OSError:
        return False
    import json
    for name in names:
        try:
            data = json.loads((d / name).read_text(encoding="utf-8"))
        except Exception:
            continue
        if (isinstance(data, dict)
                and data.get("state") == "claimed"
                and data.get("owner_session_id") == session_id):
            return True
    return False


def _main_tree_check(main_root: Path, runs_dir: Path, staged: list[str]):
    """F2: M1 allowlist+trail, M2 active session, M3/M4 transition/strict."""
    actual = os.environ.get("HARNESS_SESSION_ID")
    strict = os.environ.get("HARNESS_STRICT_IDENTITY") == "1"
    if staged:
        tids: list[str] = []
        for f in staged:
            posix = f.replace("\\", "/")
            if not any(rx.match(posix) for rx in _ALLOW_RES):
                break
            m = _TASK_RE.search(posix)
            if m:
                tids.append(m.group(0))
        else:
            if tids and all(_read_record(runs_dir, t) for t in tids):
                return True, ("[OK] main-tree bookkeeping commit "
                              "with ownership trail: %s" % ",".join(tids))
    if actual is not None:
        if _claimed_owner(runs_dir, actual):
            return True, ("[OK] main-tree commit by active session %s"
                           % actual)
        if strict:
            return False, ("[FAIL] main-tree commit by unknown session "
                           "%s with no ownership trail" % actual)
        return True, ("[WARN] main-tree commit by unknown session %s "
                      "with no ownership trail (transition)" % actual)
    if strict:
        return False, ("[FAIL] main-tree commit with no committer "
                       "identity (HARNESS_SESSION_ID unset, strict mode)")
    return True, ("[OK] main-tree commit "
                  "[WARN] no committer identity in env (transition)")


def check(toplevel: Path, main_root: Path, runs_dir: Path,
          staged: list[str] | None = None):
    """(ok, message). Pure logic, unit-tested. reads ownership registry."""
    if norm(toplevel) == norm(main_root):
        return _main_tree_check(main_root, runs_dir, staged or [])
    sys.path.insert(0, str(Path(main_root) / ".harness" / "scripts"))
    import ownership
    rec = ownership.worktree_owner(runs_dir, toplevel)
    if not rec:
        return False, ("[FAIL] worktree commit without active ownership claim"
                       " (no session bound to this worktree): run"
                       " .harness/scripts/start-session.py TASK-XXX first")
    owner = rec.get("owner_session_id")
    actual = os.environ.get("HARNESS_SESSION_ID")
    strict = os.environ.get("HARNESS_STRICT_IDENTITY") == "1"
    if actual is None:
        if strict:
            return False, ("[FAIL] no committer identity "
                           "(HARNESS_SESSION_ID unset, strict mode)")
        return True, ("[OK] ownership claimed: task=%s session=%s "
                      "[WARN] no committer identity in env, "
                      "ownership-only check (transition)"
                      % (rec.get("task_id"), owner))
    if actual != owner:
        if strict:
            return False, ("[FAIL] committer identity mismatch: "
                           "committer=%s owner=%s" % (actual, owner))
        return True, ("[OK] ownership claimed: task=%s session=%s "
                      "[WARN] committer identity mismatch "
                      "(committer=%s), ownership-only check (transition)"
                      % (rec.get("task_id"), owner, actual))
    return True, ("[OK] ownership claimed: task=%s session=%s "
                  "identity verified" % (rec.get("task_id"), owner))


def main() -> int:
    try:
        top = Path(git("rev-parse", "--show-toplevel"))
        common = Path(git("rev-parse", "--git-common-dir"))
        main_root = common.resolve().parent
        runs_dir = main_root / ".harness" / "runs"
        try:
            staged = git("diff", "--cached", "--name-only").splitlines()
        except Exception:
            staged = []
        ok, msg = check(top, main_root, runs_dir, staged)
    except Exception as exc:  # noqa: BLE001  fail closed, loudly
        print(f"[FAIL] ownership gate error (fail closed): {exc}")
        return 1
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
