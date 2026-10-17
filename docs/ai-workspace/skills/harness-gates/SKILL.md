# Harness Gates

Use when about to commit, push, or merge, or when a gate turns red and the
reason is unclear.

## The five gates in order

1. Commit-time ownership: worktree commits need a live ownership binding
   plus matching committer identity; main-tree commits need a bookkeeping
   trail or an active session. Unknown actors warn in transition, fail in
   strict mode.
2. Local scope: staged files must resolve to exactly one covering card
   (by allow-list match). No unique card means fail, not skip.
3. PR scope: the PR description declares cards with `Closes TASK-XXX`;
   only declared text after the keyword counts; touched files must sit
   inside the union of those cards' allow lists and outside every deny.
4. Cloud trail: ledgers must never be committed; cards marked done need
   verification evidence in range; branch task must match touched cards.
5. Push: no direct push to main/develop, no force-push anywhere.

## Known bypass ports (do not use, know they exist)

- `git commit --no-verify` skips local hooks; the cloud ownership check
  still judges the push.
- Identity comes from the session environment; unset identity only warns
  during transition, fails in strict mode.

## Reading a red gate

- Copy the bracket tag (`[DENY]`, `[OUT-OF-SCOPE]`, `[CONFIG-CONFLICT]`,
  `[FAIL]`), the file, and the owning card, then fix the card or the
  file set. Never widen allow to silence the gate; narrow the change.
