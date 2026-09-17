#!/usr/bin/env python3
"""
关键目录保护检查器（替代 CODEOWNERS 用于本地 git hooks）

逻辑：
- 如果 staged 变更涉及受保护路径 → 必须有 [APPROVED-BY: <name>] 标记或豁免前缀
- 架构师本人可用 SKIP_PROTECTED_CHECK=1 绕过

受保护路径（架构师 S7）：
  tests/**, contracts/**, .harness/**, .githooks/**, .github/**,
  Directory.Build.props, Directory.Build.targets, stryker-config.json

豁免前缀：chore: / docs:
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from fnmatch import fnmatch

PROTECTED_PATTERNS = [
    "tests/**",
    "contracts/**",
    ".harness/**",
    ".githooks/**",
    ".github/**",
    "Directory.Build.props",
    "Directory.Build.targets",
    "stryker-config.json",
]

EXEMPT_PREFIXES = ("chore:", "docs:")


def get_staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def is_protected(path: str) -> bool:
    return any(fnmatch(path, p) for p in PROTECTED_PATTERNS)


def main() -> int:
    if os.environ.get("SKIP_PROTECTED_CHECK") == "1":
        print("[INFO] SKIP_PROTECTED_CHECK=1，跳过保护检查（架构师本人）")
        return 0

    files = get_staged_files()
    protected_hits = [f for f in files if is_protected(f)]

    if not protected_hits:
        print("[OK] 未触碰受保护路径")
        return 0

    # 有受保护路径变更 → 必须有 commit message 标记
    commit_msg_file = os.environ.get("GIT_COMMIT_MSG_FILE")
    if commit_msg_file and os.path.exists(commit_msg_file):
        with open(commit_msg_file, encoding="utf-8") as f:
            commit_msg = f.read()
    else:
        # pre-commit 阶段：git 还没记录 commit message。
        # 这种情况下，要么提交者用 GIT_COMMIT_MSG_FILE 提供，要么 commit-msg hook 兜底。
        # 本脚本主要在 pre-commit 跑：如果在 pre-commit 跑，期望 GIT_COMMIT_MSG_FILE 被设置。
        # 但 git 1.x pre-commit 不会自动设此环境变量。
        # 兜底策略：如果检测到 commit-msg hook 配置存在，则 trust 它已检查。
        result = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            capture_output=True, text=True, check=False,
        )
        if ".githooks" in result.stdout:
            print("[OK] commit-msg hook 已配置，信任其独立检查 APPROVED-BY")
            return 0
        print(
            f"\n[FAIL] 触碰 {len(protected_hits)} 个受保护路径，且无法读取 commit message："
        )
        for f in protected_hits:
            print(f"  - {f}")
        print("\n修复方式之一：")
        print("  1. 在 commit message 中添加 [APPROVED-BY: architect-name]")
        print("  2. 使用豁免前缀（chore:/docs:）")
        print("  3. 架构师本人设置 SKIP_PROTECTED_CHECK=1 绕过")
        print("  4. 配置 commit-msg hook 独立检查（推荐）")
        return 1

    first_line = commit_msg.strip().split("\n")[0]
    for prefix in EXEMPT_PREFIXES:
        if first_line.startswith(prefix):
            print(f"[OK] 豁免前缀：{prefix}")
            return 0

    if re.search(r"\[APPROVED-BY:\s*\S+\]", commit_msg):
        print("[OK] commit message 包含 APPROVED-BY 标记")
        return 0

    print(f"\n[FAIL] 触碰 {len(protected_hits)} 个受保护路径：")
    for f in protected_hits:
        print(f"  - {f}")
    print("\n修复方式之一：")
    print("  1. 在 commit message 中添加 [APPROVED-BY: architect-name]")
    print("  2. 使用豁免前缀（chore:/docs:）")
    print("  3. 架构师本人设置 SKIP_PROTECTED_CHECK=1 绕过")
    return 1


if __name__ == "__main__":
    sys.exit(main())
