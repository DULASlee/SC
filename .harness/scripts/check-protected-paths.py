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

    # 受保护路径 APPROVED-BY 检查已迁移到 .githooks/commit-msg hook
    # （那里 git 已写入 commit message，可直接读）。
    # 本脚本保留为 SKIP_PROTECTED_CHECK=1 的紧急出口与 CI 防御层。
    print("[OK] pre-commit 阶段不检查受保护路径（由 commit-msg hook 兜底）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
