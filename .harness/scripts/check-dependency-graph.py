#!/usr/bin/env python3
"""P4 dependency graph check: ring, suspension, coverage.

- ring: depends_on chain returns to itself
- suspension: depends_on points at a nonexistent card id
- coverage: covers points at REQ ids missing from registry requirements.yaml
  (registry empty means every covers entry is a violation)

Usage:
  python .harness/scripts/check-dependency-graph.py [--cards <dir>]
Exit: 0 clean, 1 violations, 2 bad args.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def load_cards(d: Path) -> dict:
    cards = {}
    for f in sorted(d.glob("TASK-*.yaml")):
        try:
            c = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(c, dict) and c.get("id"):
            cards[c["id"]] = c
    return cards


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", default=None)
    args = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    d = Path(args.cards) if args.cards else root / "tasks" / "active"
    if not d.is_dir():
        print(f"[FAIL] cards dir missing: {d}")
        return 2
    cards = load_cards(d)
    violations: list[str] = []

    for tid, c in cards.items():
        for dep in c.get("depends_on") or []:
            if dep not in cards:
                violations.append(f"[SUSPENSION] {tid} depends on missing {dep}")

    visiting: set[str] = set()
    done: set[str] = set()

    def visit(tid: str, stack: list) -> None:
        if tid in done:
            return
        if tid in visiting:
            cycle = stack[stack.index(tid):] + [tid]
            violations.append("[RING] " + " -> ".join(cycle))
            return
        visiting.add(tid)
        for dep in (cards.get(tid, {}).get("depends_on") or []):
            if dep in cards:
                visit(dep, stack + [tid])
        visiting.discard(tid)
        done.add(tid)

    for tid in cards:
        visit(tid, [])

    reg = root / "registry" / "requirements.yaml"
    known: set[str] = set()
    try:
        data = yaml.safe_load(reg.read_text(encoding="utf-8")) or {}
        for it in data.get("items") or []:
            if isinstance(it, dict) and it.get("id"):
                known.add(it["id"])
    except Exception:
        known = set()
    for tid, c in cards.items():
        for req in c.get("covers") or []:
            if req not in known:
                violations.append(
                    f"[COVERAGE] {tid} covers unknown {req} "
                    f"(registry has {len(known)} REQs)")

    if violations:
        for v in violations:
            print(v)
        return 1
    print(f"[OK] dep graph clean ({len(cards)} cards)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
