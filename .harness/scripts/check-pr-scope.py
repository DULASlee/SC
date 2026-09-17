#!/usr/bin/env python3
"""
L3 PR scope 检查器

检查当前分支的所有变更是否在任务卡 allow_write 范围内，且未触碰 deny_write。

用法（在 CI 中）：
  PR_DESCRIPTION="Closes TASK-001 ..." python .harness/scripts/check-pr-scope.py

用法（本地）：
  python .harness/scripts/check-pr-scope.py --task-id TASK-001 --base origin/develop

退出码：
  0 - 通过
  1 - 越界或违规
  2 - 参数错误
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

HARNESS_DIR = Path(__file__).resolve().parent.parent
TASKS_DIR = HARNESS_DIR / "tasks" / "active"


def glob_to_regex(pattern):
    """将 glob 转为正则，支持 ** 递归匹配。"""
    p = re.escape(pattern)
    p = p.replace(r"\*\*/", r"(?:.*/)?")
    p = p.replace(r"\*\*", r".*")
    p = p.replace(r"\*", r"[^/]*")
    p = p.replace(r"\?", r"[^/]")
    return re.compile(f"^{p}$")


def match_any(path, patterns):
    for p in patterns:
        if glob_to_regex(p).match(path):
            return True
    return False


def get_changed_files(base_ref):
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        capture_output=True, text=True, check=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def get_changed_lines(base_ref):
    result = subprocess.run(
        ["git", "diff", "--numstat", f"{base_ref}...HEAD"],
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


def extract_task_id(text):
    if not text:
        return None
    m = re.search(r"TASK-\d{3,}", text)
    return m.group(0) if m else None


def load_task_card(task_id):
    path = TASKS_DIR / f"{task_id}.yaml"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="L3 PR scope 检查器")
    parser.add_argument("--task-id", help="显式指定任务卡 ID")
    parser.add_argument("--base", default="origin/develop", help="对比的基线分支")
    args = parser.parse_args()

    # 1. 确定任务 ID
    task_id = args.task_id
    if not task_id:
        desc = os.environ.get("PR_DESCRIPTION", "")
        task_id = extract_task_id(desc)
    if not task_id:
        print("[FAIL] 未找到 TASK-XXX。请在 PR 描述中写 'Closes TASK-XXX' 或用 --task-id 指定。")
        sys.exit(1)
    print(f"[INFO] Task ID: {task_id}")

    # 2. 加载任务卡
    card = load_task_card(task_id)
    if not card:
        print(f"[FAIL] 任务卡不存在：.harness/tasks/active/{task_id}.yaml")
        sys.exit(1)

    allow = card["scope"]["allow_write"]
    deny = card["scope"]["deny_write"]
    constraints = card.get("constraints", {})
    max_lines = constraints.get("max_lines_changed", 300)
    max_files = constraints.get("max_files_changed", 10)

    # 3. 获取变更
    try:
        changed_files = get_changed_files(args.base)
        changed_lines = get_changed_lines(args.base)
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] git diff 失败：{e.stderr if e.stderr else e}")
        sys.exit(1)

    if not changed_files:
        print("[WARN] 无变更文件")
        sys.exit(0)

    # 4. 检查每个文件
    violations = []
    for f in changed_files:
        if match_any(f, deny):
            violations.append(f"[DENY] {f} 触碰了 deny_write")
        elif not match_any(f, allow):
            violations.append(f"[OUT-OF-SCOPE] {f} 不在 allow_write 范围内")

    if violations:
        print(f"\n[FAIL] 发现 {len(violations)} 处 scope 违规：")
        for v in violations:
            print(f"  - {v}")
        print("\n修复方式：将变更限制在任务卡 allow_write 范围内，或申请新任务卡。")
        sys.exit(1)

    # 5. 检查规模
    if len(changed_files) > max_files:
        print(f"[FAIL] 文件数 {len(changed_files)} 超过限制 {max_files}。请拆分任务。")
        sys.exit(1)
    if changed_lines > max_lines:
        print(f"[FAIL] 变更行数 {changed_lines} 超过限制 {max_lines}。请拆分任务。")
        sys.exit(1)

    print(f"[OK] scope 检查通过：{len(changed_files)} 文件，{changed_lines} 行变更")
    sys.exit(0)


if __name__ == "__main__":
    main()
