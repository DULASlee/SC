#!/usr/bin/env python3
"""F3 cloud-side ownership/traIl check (read-only, never writes state).

Usage:
  python .harness/scripts/check-cloud-ownership.py --base origin/main
Exit: 0 pass, 1 violation, 2 bad args.

What it checks over {base}...HEAD (cloud has no ownership registry --
runs/ is gitignored -- so this enforces trail consistency instead):
1. No commit touches ownership/runs ledgers (must never be committed).
2. Any TASK-*.yaml reaching status done in range has a matching
   docs/verification/VERIFY-<id>-*.md in range or already on base.
3. Branch task (feat/TASK-xxx) matches touched cards; stray card
   touches outside the branch task fail.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

TASK_RE = re.compile(r"TASK-\d+")
CARD_RE = re.compile(r"^\.harness/tasks/(active|archive)/TASK-\d+[^/]*\.yaml$")
VERIFY_RE = re.compile(r"^docs/verification/VERIFY-(TASK-\d+)-.*\.md$")
FORBIDDEN_RE = re.compile(r"^\.harness/(runs|worktrees|context)/")


def git(*args, cwd):
    p = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: "
                           f"{(p.stderr or '').strip()[:200]}")
    return p.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--root", default=None,
                    help="repo root override (default: repo containing "
                         "this script; used by tests)")
    args = ap.parse_args()
    root = Path(args.root).resolve() if args.root else \
        Path(__file__).resolve().parents[2]
    try:
        files = git("diff", "--name-only", f"{args.base}...HEAD",
                    cwd=root).splitlines()
    except RuntimeError as exc:
        print(f"[FAIL] {exc}")
        return 2
    files = [f.replace("\\", "/") for f in files if f.strip()]
    violations: list[str] = []

    for f in files:
        if FORBIDDEN_RE.match(f):
            violations.append(f"[DENY] ledger path must never be committed: {f}")

    try:
        branch = git("rev-parse", "--abbrev-ref", "HEAD",
                     cwd=root).strip()
    except RuntimeError:
        branch = ""
    branch_tasks = set(TASK_RE.findall(branch))
    touched_cards = set()
    for f in files:
        if CARD_RE.match(f):
            m = TASK_RE.search(f)
            if m:
                touched_cards.add(m.group(0))
    if branch_tasks and touched_cards - branch_tasks:
        violations.append(
            "[OUT-OF-SCOPE] branch %s touches foreign cards: %s"
            % (branch, sorted(touched_cards - branch_tasks)))

    try:
        base_tree = git("ls-tree", "-r", "--name-only", args.base,
                        cwd=root).split()
    except RuntimeError:
        base_tree = []
    base_verifies = set()
    for f in base_tree:
        m = VERIFY_RE.match(f.replace("\\", "/"))
        if m:
            base_verifies.add(m.group(1))
    range_verifies = set()
    for f in files:
        m = VERIFY_RE.match(f)
        if m:
            range_verifies.add(m.group(1))

    try:
        diff_text = git("diff", f"{args.base}...HEAD", "--",
                        *[f for f in files if CARD_RE.match(f)],
                        cwd=root) if any(CARD_RE.match(f) for f in files) else ""
    except RuntimeError as exc:
        print(f"[FAIL] {exc}")
        return 2
    done_now = set(re.findall(r"[+].*status:\s*done", diff_text))
    if done_now:
        for tid in touched_cards:
            if tid not in range_verifies and tid not in base_verifies:
                try:
                    content = git("show", f"HEAD:.harness/tasks/active/{tid}.yaml",
                                  cwd=root)
                except RuntimeError:
                    try:
                        content = git(
                            "show",
                            f"HEAD:.harness/tasks/archive/{tid}.yaml",
                            cwd=root)
                    except RuntimeError:
                        content = ""
                if "status: done" in content.replace("status:done",
                                                     "status: done"):
                    violations.append(
                        "[FAIL] %s marked done without VERIFY evidence "
                        "(no docs/verification/VERIFY-%s-*.md in range or base)"
                        % (tid, tid))

    if violations:
        for v in violations:
            print(v)
        return 1
    print("[OK] cloud ownership/trail check passed "
          f"({len(files)} files in range)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
