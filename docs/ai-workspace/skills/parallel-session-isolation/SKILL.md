# Parallel Session Isolation

Use when two or more AI sessions work in the same repository at the same time,
when opening a second worktree, or when a commit is rejected by the ownership gate.

## Symptoms this fixes

- A session writes into another session's branch or worktree.
- Commit rejected: no session bound to this worktree.
- Two sessions claim the same task card.

## The triple (all three, every session)

1. One worktree per task: `git worktree add <wt-root>/<TASK> -b feat/<TASK>`.
   Branch name is always `feat/` plus the card id in full caps.
2. One ownership record per task: `<runs>/ownership/<TASK>.json` with fields
   `task_id`, `owner_session_id` (`manual:<name>` by hand, `dispatch:<id>` by
   machine), `owner_worktree` (absolute path, slashes), `state: claimed`.
3. Anchor by git-common-dir, never by current directory: the registry lives
   under the main tree even when you stand inside a worktree.

## Verify before working

- Worktree clean or intentionally dirty, never accidentally dirty.
- Ownership record exists and `owner_session_id` is yours.
- Branch is exactly `feat/<TASK>`, no suffixes.

## Common mistakes

- Hand-writing the JSON and omitting `state` (gate rejects; copy the shape,
  do not invent it).
- Lowercase branch names (hooks and dispatch match exact case).
- Reading the registry from inside the worktree copy instead of the main tree.
- Reusing an existing directory without checking who owns it (refuse when
  another live session holds it; rebind only after release).
