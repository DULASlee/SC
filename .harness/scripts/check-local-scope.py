#!/usr/bin/env python3
"""
本地 scope 检查器（替代 check-pr-scope.py 用于本地 git hooks）

在没有 PR 的情况下，检查：
1. 当前 staged 变更是否在活动任务卡的 allow_write 范围内
2. 变更是否触碰 deny_write
3. 变更规模是否超过任务卡限制

用法：
  python .harness/scripts/check-local-scope.py
  python .harness/scripts/check-local-scope.py --task-id TASK-002

退出码：
  0 - 通过
  1 - 越界或规模超限
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

import yaml

HARNESS_DIR = Path(__file__).resolve().parent.parent
TASKS_DIR = (Path(os.environ["HARNESS_TASKS_DIR"]).resolve()
             if os.environ.get("HARNESS_TASKS_DIR") else
             HARNESS_DIR / "tasks" / "active")


def glob_to_regex(pattern: str) -> re.Pattern:
    p = re.escape(pattern)
    p = p.replace(r"\*\*/", r"(?:.*/)?")
    p = p.replace(r"\*\*", r".*")
    p = p.replace(r"\*", r"[^/]*")
    p = p.replace(r"\?", r"[^/]")
    return re.compile(f"^{p}$")


def match_any(path: str, patterns: list[str]) -> bool:
    return any(glob_to_regex(p).match(path) for p in patterns)


def get_staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def get_staged_lines() -> int:
    result = subprocess.run(
        ["git", "diff", "--cached", "--numstat"],
        capture_output=True, text=True, check=True,
    )
    total = 0
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            total += int(parts[0]) + int(parts[1])
    return total


def find_active_task() -> tuple[Path | None, dict | None]:
    """当只有 1 个 ready/in-progress 任务卡时，自动使用它。"""
    cards = list(TASKS_DIR.glob("TASK-*.yaml"))
    ready: list[tuple[Path, dict]] = []
    for card in cards:
        with open(card, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data.get("status") in ("ready", "in-progress"):
            ready.append((card, data))
    if len(ready) == 1:
        return ready[0]
    return None, None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", help="显式指定任务卡 ID")
    args = parser.parse_args()

    if args.task_id:
        card_path = TASKS_DIR / f"{args.task_id}.yaml"
        if not card_path.exists():
            print(f"[FAIL] task card not found: {card_path}")
            return 1
        with open(card_path, encoding="utf-8") as f:
            card = yaml.safe_load(f)
    else:
        card_path, card = find_active_task()
        if not card:
            # isolation-revision F4: resolve by staged files instead of
            # skipping. Exactly one covering card -> use it; else FAIL
            # (transition: HARNESS_LENIENT_SCOPE=1 keeps old warn-skip).
            import os
            staged_early = get_staged_files()
            if not staged_early:
                print("[WARN] no staged changes")
                return 0
            matches = []
            for cp in TASKS_DIR.glob("TASK-*.yaml"):
                try:
                    with open(cp, encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                except Exception:
                    continue
                if (data.get("status") not in ("ready", "in-progress")
                        or not staged_early):
                    continue
                allow = ((data.get("scope") or {}).get("allow_write")) or []
                deny = ((data.get("scope") or {}).get("deny_write")) or []
                if any(match_any(x, deny) for x in staged_early):
                    continue
                if all(match_any(x, allow) for x in staged_early):
                    matches.append((cp, data))
            if len(matches) == 1:
                card_path, card = matches[0]
                print(f"[INFO] resolved covering card: {card_path.name}")
            else:
                if os.environ.get("HARNESS_LENIENT_SCOPE") == "1":
                    print("[WARN] no unique covering task card "
                          f"({len(matches)} candidates), skipping scope check "
                          "(lenient transition)")
                    return 0
                print("[FAIL] no unique covering task card "
                      f"({len(matches)} candidates for {len(staged_early)} "
                      "staged file(s)): pass --task-id TASK-XXX explicitly "
                      "or open a card covering these files")
                return 1

    print(f"[INFO] using task card: {card_path.name} (status: {card.get('status')})")

    allow = card["scope"]["allow_write"]
    deny = card["scope"]["deny_write"]
    max_lines = card.get("constraints", {}).get("max_lines_changed", 300)
    max_files = card.get("constraints", {}).get("max_files_changed", 10)

    files = get_staged_files()
    lines = get_staged_lines()

    if not files:
        print("[WARN] no staged changes")
        return 0

    violations = []
    for f in files:
        if match_any(f, deny):
            violations.append(f"[DENY] {f} touches deny_write")
        elif not match_any(f, allow):
            violations.append(f"[OUT-OF-SCOPE] {f} outside allow_write")

    if violations:
        print(f"\n[FAIL] {len(violations)} scope violation(s):")
        for v in violations:
            print(f"  - {v}")
        print("\nFix: limit changes to the card allow_write, or open a new task card.")
        # TASK-024 C2: 现行模型——受保护路径由 commit-msg hook + check_approval.py
        # 判定（覆盖卡 allow_write + 非空 approver），[APPROVED-BY]/豁免前缀旧语义已作废。
        print("Note: protected paths (.github/, tests/, .harness/, ...) are enforced by the "
              "commit-msg hook + check_approval.py: an active card whose allow_write covers "
              "the file with a non-empty approver field, or architect sets SKIP_PROTECTED_CHECK=1.")
        return 1

    if len(files) > max_files:
        print(f"[FAIL] file count {len(files)} exceeds limit {max_files}")
        return 1
    if lines > max_lines:
        print(f"[FAIL] changed lines {lines} exceed limit {max_lines}")
        return 1

    print(f"[OK] scope check passed: {len(files)} file(s), {lines} line(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
