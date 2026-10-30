# P1 policy review 2026-10-18

- format: allow/forbid lists, default escalate; three tiers verified by 7 unit tests
- drill: added tmp-probe allow entry, action flipped escalate->allow, reverted, flipped back. revert verified.
- verdict: strict-by-default holds; change-and-revert path works
