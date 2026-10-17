#!/usr/bin/env python3
"""P4 placeholder inventory: find acceptance_tests unrelated to card scope.

Placeholder definition: an acceptance_tests entry whose path is not covered
by the card's own scope allow_write globs (i.e. the card vouches for a file
it is not allowed to touch). Such entries prove nothing about the change.

Usage:
  python .harness/scripts/find-placeholders.py [--cards <dir>]
Exit: 0 with inventory printed; always 0 (inventory only, never a gate).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def _dbl_star(pattern: str, path: str) -> bool:
    import re
    p = re.escape(pattern)
    p = p.replace(r"\*\*/", r"(?:.*/)?")
    p = p.replace(r"\*\*", r".*")
    p = p.replace(r"\*", r"[^/]*")
    p = p.replace(r"\?", r"[^/]")
    return re.match(f"^{p}$", path) is not None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", default=None)
    args = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    d = Path(args.cards) if args.cards else root / "tasks" / "active"
    rows = 0
    for f in sorted(d.glob("TASK-*.yaml")):
        try:
            card = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"{f.name}: UNREADABLE ({exc})")
            continue
        allow = ((card.get("scope") or {}).get("allow_write")) or []
        tests = card.get("acceptance_tests") or []
        for t in tests:
            if not any(_dbl_star(a, t) for a in allow):
                print(f"{card.get('id')}: placeholder {t} "
                      f"(not in own allow_write)")
                rows += 1
    print(f"placeholder rows: {rows}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
