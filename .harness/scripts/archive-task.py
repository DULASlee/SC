#!/usr/bin/env python3
"""
L3 任务归档器

用法：
  python .harness/scripts/archive-task.py TASK-001

行为：
  1. 检查任务卡 status 是否为 done
  2. 将任务卡从 active/ 移动到 archive/
  3. 归档时添加 archived_at 时间戳
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

HARNESS_DIR = Path(__file__).resolve().parent.parent
ACTIVE_DIR = HARNESS_DIR / "tasks" / "active"
ARCHIVE_DIR = HARNESS_DIR / "tasks" / "archive"


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)

    task_id = sys.argv[1]
    src = ACTIVE_DIR / f"{task_id}.yaml"
    dst = ARCHIVE_DIR / f"{task_id}.yaml"

    if not src.exists():
        print(f"[FAIL] 任务卡不存在：{src}")
        sys.exit(1)

    with open(src, encoding="utf-8") as f:
        card = yaml.safe_load(f)

    if card.get("status") != "done":
        print(f"[FAIL] 任务卡 status 不是 done（当前：{card.get('status')}），不能归档")
        sys.exit(1)

    card["archived_at"] = datetime.now(timezone.utc).isoformat()

    with open(dst, "w", encoding="utf-8") as f:
        yaml.safe_dump(card, f, allow_unicode=True, sort_keys=False)

    src.unlink()
    print(f"[OK] 已归档：{src.name} -> archive/{dst.name}")


if __name__ == "__main__":
    main()
