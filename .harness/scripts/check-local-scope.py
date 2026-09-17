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
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

import yaml

HARNESS_DIR = Path(__file__).resolve().parent.parent
TASKS_DIR = HARNESS_DIR / "tasks" / "active"


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
            print(f"[FAIL] 任务卡不存在：{card_path}")
            return 1
        with open(card_path, encoding="utf-8") as f:
            card = yaml.safe_load(f)
    else:
        card_path, card = find_active_task()
        if not card:
            print("[WARN] 无唯一的活动任务卡（0 或 >= 2 个 ready/in-progress），跳过 scope 检查")
            print("       业务代码提交请显式 --task-id TASK-XXX")
            return 0

    print(f"[INFO] 使用任务卡：{card_path.name}（status: {card.get('status')}）")

    allow = card["scope"]["allow_write"]
    deny = card["scope"]["deny_write"]
    max_lines = card.get("constraints", {}).get("max_lines_changed", 300)
    max_files = card.get("constraints", {}).get("max_files_changed", 10)

    files = get_staged_files()
    lines = get_staged_lines()

    if not files:
        print("[WARN] 无 staged 变更")
        return 0

    violations = []
    for f in files:
        if match_any(f, deny):
            violations.append(f"[DENY] {f} 触碰 deny_write")
        elif not match_any(f, allow):
            violations.append(f"[OUT-OF-SCOPE] {f} 不在 allow_write 内")

    if violations:
        print(f"\n[FAIL] 发现 {len(violations)} 处 scope 违规：")
        for v in violations:
            print(f"  - {v}")
        print("\n修复方式：将变更限制在任务卡 allow_write 范围内，或申请新任务卡。")
        return 1

    if len(files) > max_files:
        print(f"[FAIL] 文件数 {len(files)} 超过限制 {max_files}")
        return 1
    if lines > max_lines:
        print(f"[FAIL] 变更行数 {lines} 超过限制 {max_lines}")
        return 1

    print(f"[OK] scope 检查通过：{len(files)} 文件，{lines} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
