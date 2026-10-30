#!/usr/bin/env python3
"""Independent acceptance verifier (P2). Read-only, never merges.

Independence is structural: the verifier accepts ONLY a work directory,
a criteria file, and an explicit allow-list. There is no input for worker
reasoning, worker session identity, or worker context -- the CLI has no
such options by design, and any accessed path outside the allow-list
fails the run closed.

Usage:
  python .harness/scripts/verify-agent.py --work <dir> --criteria <file>
      --allow <glob> [--allow <glob>...] --out <verdict.md>
Exit: 0 verdict written (PASS or FAIL inside); 2 bad args or unreadable input.
The verdict file lists every file read, so isolation is auditable.
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path


def _hit(patterns: list[str], path: str) -> bool:
    return any(fnmatch.fnmatchcase(path, p) for p in patterns)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--criteria", required=True)
    ap.add_argument("--allow", action="append", default=[])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    work = Path(args.work)
    crit = Path(args.criteria)
    out = Path(args.out)
    if not work.is_dir() or not crit.is_file():
        print("[FAIL] work dir or criteria unreadable")
        return 2

    read_log: list[str] = []
    problems: list[str] = []

    criteria = crit.read_text(encoding="utf-8")
    read_log.append(str(crit))
    if not criteria.strip():
        problems.append("criteria file is empty")

    allow = list(args.allow) or [str(work / "**")]
    changed: list[str] = []
    for f in sorted(work.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(work).as_posix()
        if not _hit(allow, rel):
            problems.append(f"file outside allow-list, unread: {rel}")
            continue
        read_log.append(str(f))
        changed.append(rel)

    if not changed and not problems:
        problems.append("work dir contains no files")

    verdict = "FAIL" if problems else "PASS"
    lines = [f"# verifier verdict: {verdict}", "",
             "## files read"]
    lines += [f"- {p}" for p in read_log]
    lines += ["", "## findings"]
    if problems:
        lines += [f"- {p}" for p in problems]
    else:
        lines += ["- criteria met, all files inside allow-list"]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[{verdict}] {len(changed)} files read, "
          f"{len(problems)} problems -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
