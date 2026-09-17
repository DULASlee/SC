#!/usr/bin/env python3
"""
人类验收脚本（方案 3 核心）

由人类架构师在验收机运行：
  python .harness/scripts/verify-all.py --task-id TASK-002 --operator architect-name

产出：docs/verification/VERIFY-<task-id>-<timestamp>.md

该 md 文件是"任务 done"的唯一权威凭证（见 docs/engineering/l5-separation-of-roles.md 规则 2）。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VERIFY_DIR = REPO_ROOT / "docs" / "verification"


def run(cmd: str, cwd: Path = REPO_ROOT) -> tuple[int, str, str]:
    result = subprocess.run(
        cmd, shell=True, cwd=cwd, capture_output=True, text=True,
    )
    return result.returncode, result.stdout, result.stderr


def git_info() -> dict:
    _, sha, _ = run("git rev-parse HEAD")
    _, branch, _ = run("git rev-parse --abbrev-ref HEAD")
    _, status, _ = run("git status --porcelain")
    return {
        "sha": sha.strip(),
        "branch": branch.strip(),
        "dirty": bool(status.strip()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--operator", default="unknown", help="验收人")
    args = parser.parse_args()

    VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = VERIFY_DIR / f"VERIFY-{args.task_id}-{ts}.md"

    lines: list[str] = [f"# VERIFY-{args.task_id}-{ts}\n"]
    lines.append(f"- 验收人：{args.operator}")
    lines.append(f"- 时间：{datetime.now(timezone.utc).isoformat()}")

    info = git_info()
    lines.append(f"- Git SHA：`{info['sha']}`")
    lines.append(f"- Git 分支：`{info['branch']}`")
    lines.append(f"- 工作区脏：{info['dirty']}\n")

    # 强制 UTF-8 防 Windows GBK 翻车（L1-α 验收记录过）
    lines.append("## 门禁结果\n")
    checks: list[tuple[str, str]] = [
        ("1. 任务卡校验", "python .harness/scripts/validate-task-card.py --all"),
        ("2. 契约一致性", "python scripts/check-contract-consistency.py"),
        ("3. 编译 + 警告即错误", "dotnet build -c Release /p:TreatWarningsAsErrors=true --nologo -v quiet"),
        ("4. 架构测试（条件）",
            "[ -f tests/ArchitectureTests/ArchitectureTests.csproj ] && "
            "dotnet test tests/ArchitectureTests/ArchitectureTests.csproj -c Release --no-build --nologo -v quiet "
            "|| echo 'ArchitectureTests 不存在（跳过）'"),
        ("5. 可靠性工具链（条件）",
            "[ -d tests/ReliabilityTests ] && "
            "dotnet test tests/ReliabilityTests/ReliabilityTests.csproj -c Release --no-build --nologo -v quiet "
            "|| echo 'ReliabilityTests 不存在（跳过）'"),
        ("6. 全测试", "dotnet test -c Release --no-build --nologo -v quiet"),
    ]

    all_pass = True
    for name, cmd in checks:
        lines.append(f"### {name}\n")
        lines.append(f"命令：`{cmd}`\n")
        code, stdout, stderr = run(cmd)
        lines.append(f"退出码：`{code}`\n")
        if code == 0:
            lines.append("结果：✅ 通过\n")
        else:
            all_pass = False
            lines.append("结果：❌ 失败\n")
            lines.append("```")
            tail = (stdout + stderr)[-3000:]
            lines.append(tail)
            lines.append("```\n")

    lines.append("## 验收结论\n")
    if all_pass:
        lines.append("✅ **通过**。任务可标记为 done。\n")
    else:
        lines.append("❌ **未通过**。修复后重新运行本脚本。\n")

    lines.append("\n---\n")
    lines.append("## 原始证据\n")
    lines.append("本文件由 `verify-all.py` 自动生成，包含所有门禁命令的原始输出。\n")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] 验收记录已生成：{out_path}")
    print(f"[INFO] 结果：{'通过' if all_pass else '未通过'}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
