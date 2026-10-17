# threshold owners (P2 Step 1)

| metric | owner | effective_date |
|---|---|---|
| line-coverage-ratchet-30-target-80 | owner | 2026-10-24 |
| stryker-break-15 | owner | 2026-10-24 |

Anchors: coverage threshold lives in .github/workflows/ci.yml coverage-threshold job (80); mutation break lives in ci.yml mutation job flag --break-at 15 and stryker-config.json thresholds.break.

Note: stryker effective date lives here (config file rejects unknown keys).
