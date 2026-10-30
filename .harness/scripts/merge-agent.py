#!/usr/bin/env python3
"""Merge agent (P3). Merges only after re-verifying, never on cache.

Inputs: PR number, verifier verdict file, repo.
Gate: verifier verdict is PASS AND every required check is green right now.
Any red or missing piece -> write escalation record, merge nothing, exit 2.
--dry-run prints the would-merge set without merging.

Usage:
  python .harness/scripts/merge-agent.py --pr <n> --repo <o/r>
      --verdict <file> [--dry-run] [--out <record>]
Exit: 0 merged (or dry-run clean), 2 turned to human, 1 error.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys


def decide(checks: dict[str, str], verdict: str) -> str:
    """Pure decision: 'merge' only when verdict PASS and every check green."""
    if verdict.strip().upper() != "PASS":
        return "escalate:verdict-not-pass"
    bad = sorted(k for k, v in checks.items() if v != "green")
    if bad:
        return "escalate:checks-red:" + ",".join(bad)
    if not checks:
        return "escalate:no-checks-seen"
    return "merge"


def sh(*args):
    p = subprocess.run(list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: "
                           f"{(p.stderr or '').strip()[:300]}")
    return p.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pr", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--verdict", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    try:
        from pathlib import Path
        verdict_text = Path(args.verdict).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[ERROR] unreadable verdict: {exc}")
        return 1
    verdict = "PASS" if "verdict: PASS" in verdict_text else "FAIL"

    try:
        raw = sh("gh", "pr", "checks", args.pr, "--repo", args.repo,
                 "--json", "name,state")
        checks = {c["name"]: ("green" if c["state"] in
                              ("SUCCESS", "SKIPPED", "NEUTRAL") else "red")
                  for c in json.loads(raw)}
    except Exception as exc:
        print(f"[ERROR] cannot read checks: {exc}")
        return 1

    decision = decide(checks, verdict)
    record = [f"pr: {args.pr}", f"verdict: {verdict}",
              f"checks: {len(checks)} seen, "
              f"{sum(1 for v in checks.values() if v != 'green')} red",
              f"decision: {decision}"]
    if args.out:
        from pathlib import Path as _P
        _P(args.out).write_text("\n".join(record) + "\n", encoding="utf-8")
    print("\n".join(record))

    if decision != "merge":
        print("[ESCALATE] merged nothing, human takes over")
        return 2
    if args.dry_run:
        print("[DRYRUN] would merge, merged nothing")
        return 0
    try:
        sh("gh", "pr", "merge", args.pr, "--repo", args.repo, "--merge")
    except Exception as exc:
        print(f"[ERROR] merge failed: {exc}")
        return 1
    print("[MERGED]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
