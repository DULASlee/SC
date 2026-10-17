#!/usr/bin/env python3
"""P4 requirement links check: covers <-> registry both directions.

- Every covers entry must resolve to a registry REQ.
- Every registry active REQ should be covered by >=1 card (warning only,
  reported but exit stays 0 when only this fires... no: warnings print,
  errors fail; uncovered-active is a warning).

Usage:
  python .harness/scripts/check-requirement-links.py
Exit: 0 clean (warnings allowed), 1 broken links, 2 bad args.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    reg = root / "registry" / "requirements.yaml"
    try:
        data = yaml.safe_load(reg.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"[FAIL] registry unreadable: {exc}")
        return 2
    items = data.get("items") or []
    active = {i["id"] for i in items
              if isinstance(i, dict) and i.get("id")
              and i.get("status", "active") == "active"}
    covered: set[str] = set()
    broken: list[str] = []
    cards = sorted((root / "tasks" / "active").glob("TASK-*.yaml"))
    for f in cards:
        try:
            c = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        for req in c.get("covers") or []:
            covered.add(req)
            if req not in {i.get("id") for i in items
                           if isinstance(i, dict)}:
                broken.append(f"[BROKEN] {c.get('id')} covers unknown {req}")
    if broken:
        for b in broken:
            print(b)
        return 1
    lonely = sorted(active - {r for r in covered})
    if lonely:
        print(f"[WARN] uncovered active REQs: {lonely}")
    print(f"[OK] links clean ({len(cards)} cards, "
          f"{len(active)} active REQs, {len(covered)} covered)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
