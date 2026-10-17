# Agent Verify Loop

Use when the work is done and ready to hand in, before claiming anything
is complete.

## The loop (no completion claim without it)

1. Red first: write the failing check before the fix (a test, a gate run,
   a red card). Watch it fail and record the output.
2. Fix minimally: one change, one variable, no drive-by refactoring.
3. Green plus regression: the failing check passes and the full suite
   count does not drop (M >= N, no new failures).
4. Evidence on disk: logs under the slice evidence directory, named per
   plan, before any merge request.

## Handoff report (the recipient is not you)

- What was done, in one paragraph a non-programmer can repeat.
- Why it counts as done: gate names plus conclusions, regression M/N.
- One pending decision at most; everything else you decided and can
  roll back.

## Common mistakes

- Declaring green from a dirty tree (local pass, cloud red).
- Pasting log text into chat instead of files (chat is not evidence).
- Appending evidence after the merge (evidence precedes merge, always).
- Marking a task card done before the verification file exists.
