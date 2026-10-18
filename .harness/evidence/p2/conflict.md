# conflict (P2 Step 4 side finding, rule 6)

- Plan says: remove coverage continue-on-error so 80% blocks.
- Reality found during intercept proof: real line coverage is 31.1%.
- Consequence of literal merge: every PR (including this one) goes red
  permanently; main becomes unmergeable. That is a blockade, not a gate.
- Options:
  - C (recommended): ratchet live gate to current reality (30%), blocking
    further drops; raise as coverage improves. Intent preserved, world stays green.
  - B: absolute 80% stays report-only; diff-guard (check-coverage-diff.sh)
    becomes the blocking gate on regressions.
  - A: merge as-is; accept permanent red on all PRs.
- Status: STOPPED before merge. Waiting Owner ruling.
- Date: 2026-10-17.
- Ruling: Owner approved ratchet (option C) 2026-10-17. Live gate set to 30 floor, target 80.
retro-approved by owner at unified acceptance 2026-10-18 (quote: sln fix praised). IoTPlatform.sln stays.
