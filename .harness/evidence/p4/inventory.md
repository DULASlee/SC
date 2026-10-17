# P4 Step 0 placeholder inventory (2026-10-17)

Method: find-placeholders.py (acceptance entry not covered by own allow_write).
Raw: 28 rows across 27 cards.

## Baseline-exempt (known-shared-tests.yaml, historical, frozen)

25 rows: TASK-008 through TASK-047 (each 1x tests/ArchitectureTests/ArchitectureTests.csproj).
These predate the sharing gate and sit on the frozen baseline. No action.

## Actionable

- TASK-053: 2 rows (.harness/tests/test_gen_task_cards_integrity.py, test_gen_task_cards.py not in own allow_write). Card is other-workstream ACTIVE. Action: 转Owner裁定, do not touch.
- TASK-058 (own, merged): 1 row (.harness/tests/test_check_session_registration.py not in own allow_write). Action: documented debt; future cards must pair acceptance with allow coverage (P3 review rule R2 now guards this).

## Counts

- raw: 28; baseline-exempt: 25; actionable-other: 2; actionable-own-merged: 1
- live placeholders requiring code change in this slice: 0
