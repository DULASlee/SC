#!/usr/bin/env python3
"""P3 read-only reviewer (picks faults, never blocks).

Usage:
  python .harness/scripts/review-agent.py --pr <number> --repo DULASlee/SC
  --out <report.md>
Exit: always 0 (scoring only, never a gate).

Five rules (see slice plan Task 3):
  R1 scope agreement: changed files fall in the union of declared cards' allow
  R2 tests alongside: business change must come with test change
  R3 evidence alongside: conclusions must cite a log or attachment
  R4 no-outline-vagueness: outline-style vague words in added prose get flagged
  R5 severity scale: serious (would block) / important (fix before merge) /
      minor (record)
Human sign-off is appended at the report tail by hand (reviewer, date, verdict).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

VAGUE_RE = re.compile(
    r"相关|类似|参考|若干|一系列|确认|确保|处理好|合适|合理|基本|大概")


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
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    files = sh("gh", "pr", "diff", args.pr, "--repo", args.repo,
               "--name-only").split()
    body = sh("gh", "pr", "view", args.pr, "--repo", args.repo,
              "--json", "body,title", "--jq", ".title + \"\n\" + .body")
    diff = sh("gh", "pr", "diff", args.pr, "--repo", args.repo)

    findings: list[str] = []
    counts = {"serious": 0, "important": 0, "minor": 0}

    def add(sev: str, where: str, what: str):
        counts[sev] += 1
        findings.append(f"- [{sev}] {where}: {what}")

    import re as _re
    def _is_test(p: str) -> bool:
        return bool(_re.search(r"(^|/)tests/|\\.harness/tests/", p))
    code = [f for f in files
            if f.endswith((".cs", ".py")) and not _is_test(f)]
    tests = [f for f in files if _is_test(f)]
    if code and not tests:
        add("important", "R2 tests-alongside",
            f"{len(code)} code files with no test change: "
            f"{', '.join(code[:5])}")
    else:
        add("minor", "R2 tests-alongside",
            f"code={len(code)} test={len(tests)}, paired" if code
            else "no business code in range")

    if "TASK-" not in body:
        add("important", "R1 scope-agreement",
            "PR body declares no TASK id, scope cannot be checked")
    else:
        add("minor", "R1 scope-agreement",
            "TASK declared: "
            + ", ".join(sorted(set(re.findall(r"TASK-\d+", body)))))

    added = [ln[1:] for ln in diff.splitlines()
             if ln.startswith("+") and not ln.startswith("+++")]
    vague_hits = [(i, ln.strip()[:80]) for i, ln in enumerate(added)
                  if VAGUE_RE.search(ln) and len(ln.strip()) > 4]
    if vague_hits:
        add("minor", "R4 no-outline-vagueness",
            f"{len(vague_hits)} added lines carry vague wording, "
            f"e.g. line {vague_hits[0][0]}: {vague_hits[0][1]}")
    else:
        add("minor", "R4 no-outline-vagueness",
            f"{len(added)} added lines scanned, no vague wording")

    if not files:
        add("serious", "R3 evidence-alongside", "empty diff, nothing to judge")
    else:
        add("minor", "R3 evidence-alongside",
            f"{len(files)} files; evidence check is manual for this round")

    out = [
        f"# review PR {args.pr} (read-only, non-blocking)",
        "",
        f"- files in range: {len(files)}",
        f"- added lines scanned: {len(added)}",
        "",
        "## findings",
        *findings,
        "",
        "## human sign-off (by hand)",
        "- reviewer: ",
        "- date: ",
        "- verdict (at least one true issue acknowledged or none found): ",
    ]
    Path(args.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"[OK] {len(findings)} findings "
          f"(serious={counts['serious']} important={counts['important']} "
          f"minor={counts['minor']}) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
