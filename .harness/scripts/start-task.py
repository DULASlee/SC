#!/usr/bin/env python3
"""
L3 会话启动上下文生成器

用法：
  python .harness/scripts/start-task.py TASK-001

输出：
  .harness/context/TASK-001-context.md

在新会话中，让 Agent 读取此文件，即可获得该任务的完整上下文。
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

HARNESS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = HARNESS_DIR.parent
TASKS_DIR = HARNESS_DIR / "tasks" / "active"
CONTEXT_DIR = HARNESS_DIR / "context"

# 防御性硬编码最小集（即使 .gitignore 缺失这些也该忽略）
_HARDCODED_IGNORED = {".git", "bin", "obj", ".harness/context"}


def glob_to_regex(pattern):
    p = re.escape(pattern)
    p = p.replace(r"\*\*/", r"(?:.*/)?")
    p = p.replace(r"\*\*", r".*")
    p = p.replace(r"\*", r"[^/]*")
    p = p.replace(r"\?", r"[^/]")
    return re.compile(f"^{p}$")


def parse_gitignore(gi_path):
    """
    轻量解析 .gitignore —— 仅支持本项目实际需要的语法：
    - 目录项以 / 结尾（dir/） → 匹配目录及其中所有内容
    - 裸项（coverage） → 匹配同名文件或目录
    - 不支持 ! 取反、** glob 深度（足够）
    返回：(files_set, dirs_set, anchored_prefix_set)
    """
    files, dirs, anchored = set(), set(), set()
    if not gi_path.exists():
        return files, dirs, anchored
    for raw in gi_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        is_dir = False
        if line.endswith("/"):
            is_dir = True
            line = line.rstrip("/")
        is_anchored = line.startswith("/")
        if is_anchored:
            line = line.lstrip("/")
        if is_dir:
            dirs.add(line)
        else:
            files.add(line)
        if is_anchored:
            anchored.add(line)
    return files, dirs, anchored


def is_ignored(rel_path, gi_files, gi_dirs, gi_anchored):
    """判断 rel_path 是否被 .gitignore 忽略（适用本仓库布局）"""
    parts = rel_path.split("/")
    name = parts[-1]
    # 1. 硬编码最小集
    for d in _HARDCODED_IGNORED:
        if d in parts:
            return True
    # 2. 裸目录项（如 coverage/） → 任意层匹配
    for d in gi_dirs:
        if d in parts:
            return True
    # 3. 裸文件项（如 *.coverage） → 文件名匹配
    if name in gi_files:
        return True
    # 4. anchored 前缀（仓库根）→ 仅在根匹配
    for a in gi_anchored:
        if rel_path == a or rel_path.startswith(a + "/"):
            return True
    return False


def collect_files(allow_patterns, deny_patterns):
    """收集匹配 allow_write 且不匹配 deny_write 的文件。
    双保险：硬编码最小集 + 读 .gitignore 解析（治本，避免下次新增 ignore 目录又漏）。"""
    gi_files, gi_dirs, gi_anchored = parse_gitignore(REPO_ROOT / ".gitignore")

    matched = []
    for pattern in allow_patterns:
        rx = glob_to_regex(pattern)
        for path in REPO_ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if is_ignored(rel, gi_files, gi_dirs, gi_anchored):
                continue
            if rx.match(rel):
                if any(glob_to_regex(d).match(rel) for d in deny_patterns):
                    continue
                matched.append(rel)
    return sorted(set(matched))


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)

    task_id = sys.argv[1]
    card_path = TASKS_DIR / f"{task_id}.yaml"
    if not card_path.exists():
        print(f"[FAIL] 任务卡不存在：{card_path}")
        sys.exit(1)

    with open(card_path, encoding="utf-8") as f:
        card = yaml.safe_load(f)

    files = collect_files(
        card["scope"]["allow_write"],
        card["scope"]["deny_write"],
    )

    # 防御性检查：L3"最小上下文加载"原则 — 单任务文件数 ≤ 20
    # 超过则警告，但仍生成（不阻断；架构师决定是否拆分）
    if len(files) > 50:
        print(f"[WARN] 上下文文件数 {len(files)} > 50，可能破坏 L3 最小上下文设计（推荐 ≤ 20）")
    elif len(files) > 20:
        print(f"[INFO] 上下文文件数 {len(files)} > 20，已超过 L3 推荐值。考虑拆分任务卡。")

    out_path = CONTEXT_DIR / f"{task_id}-context.md"
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append(f"# {task_id}: {card['title']}\n")
    lines.append(f"> 本文件由 `start-task.py` 生成于 {datetime.now(timezone.utc).isoformat()}")
    lines.append("> **用途：** 在新会话中，让 Agent 只读取本文件 + 下列文件清单，不加载历史对话。\n")

    lines.append("## 任务卡内容\n")
    lines.append("```yaml")
    lines.append(card_path.read_text(encoding="utf-8").rstrip())
    lines.append("```\n")

    lines.append("## 允许写入的现有文件清单\n")
    lines.append("> Agent 只能修改以下文件。新增文件必须落在 allow_write glob 范围内。\n")
    if files:
        for f in files:
            lines.append(f"- `{f}`")
    else:
        lines.append("- （当前没有匹配文件，可能需要新增文件）")
    lines.append("")

    lines.append("## 验收测试（架构师预先写好，初始为红）\n")
    for t in card["acceptance_tests"]:
        lines.append(f"- `{t}`")
    lines.append("")

    lines.append("## 完成条件（由 CI 判定，Agent 不发表完成声明）\n")
    for c in card["done_when"]:
        lines.append(f"- `{c}`")
    lines.append("")

    if card.get("references"):
        lines.append("## 参考文档\n")
        for r in card["references"]:
            lines.append(f"- `{r}`")
        lines.append("")

    if card.get("notes"):
        lines.append("## 备注\n")
        lines.append(card["notes"])
        lines.append("")

    lines.append("---\n")
    lines.append("## 新会话操作指令（供用户复制）\n")
    lines.append("```")
    lines.append(f"请读取 .harness/context/{task_id}-context.md，")
    lines.append("严格按照其中的 allow_write 范围修改代码，")
    lines.append("不要修改 deny_write 中的任何文件，")
    lines.append("不要发表'完成'声明，等待 CI 判定。")
    lines.append("```")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] 上下文已生成：{out_path}")
    print(f"[INFO] allow_write 范围内现有文件数：{len(files)}")


if __name__ == "__main__":
    main()

