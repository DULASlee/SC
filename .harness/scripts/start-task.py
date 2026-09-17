#!/usr/bin/env python3
"""
L3 会话启动上下文生成器

用法：
  python .harness/scripts/start-task.py TASK-001

输出：
  .harness/context/TASK-001-context.md

在新会话中，让 Agent 读取此文件，即可获得该任务的完整上下文。
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

HARNESS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = HARNESS_DIR.parent
TASKS_DIR = HARNESS_DIR / "tasks" / "active"
CONTEXT_DIR = HARNESS_DIR / "context"


def glob_to_regex(pattern):
    import re
    p = re.escape(pattern)
    p = p.replace(r"\*\*/", r"(?:.*/)?")
    p = p.replace(r"\*\*", r".*")
    p = p.replace(r"\*", r"[^/]*")
    p = p.replace(r"\?", r"[^/]")
    return re.compile(f"^{p}$")


def collect_files(allow_patterns, deny_patterns):
    matched = []
    for pattern in allow_patterns:
        rx = glob_to_regex(pattern)
        for path in REPO_ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            # 跳过明显非源码目录
            if rel.startswith(".git/") or rel.startswith("bin/") or rel.startswith("obj/"):
                continue
            if rx.match(rel):
                # deny_write 优先级更高
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

    # 收集 allow_write 范围内的现有文件
    files = collect_files(
        card["scope"]["allow_write"],
        card["scope"]["deny_write"],
    )

    # 生成上下文
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
