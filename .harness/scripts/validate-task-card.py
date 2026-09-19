#!/usr/bin/env python3
"""
L3 task card validator.

Usage:
  python .harness/scripts/validate-task-card.py <path-to-task-card.yaml>
  python .harness/scripts/validate-task-card.py --all   # validate all active task cards

Exit codes:
  0 - pass
  1 - validation failed
  2 - argument error
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import yaml
from jsonschema import validate, ValidationError

# 强制 UTF-8（避免 Windows GBK 默认解码翻车——L1-α 验收记录过）
HARNESS_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = HARNESS_DIR / "schema" / "task-card.schema.json"
ACTIVE_DIR = HARNESS_DIR / "tasks" / "active"


def load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def validate_card(card_path, schema):
    errors = []
    try:
        with open(card_path, encoding="utf-8") as f:
            card = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [f"YAML parse failed: {e}"]

    # PyYAML 默认会把 ISO 8601 字符串解析成 datetime 对象
    # 为了让 Schema 校验（json schema 期望 string）通过，
    # 这里 round-trip 一次 json dump（datetime → string）
    try:
        card = json.loads(json.dumps(card, default=str))
    except (TypeError, ValueError) as e:
        errors.append(f"YAML content not JSON-serializable (possible type anomaly): {e}")
        return errors

    # 1. Schema 校验
    try:
        validate(card, schema)
    except ValidationError as e:
        errors.append(f"Schema validation failed: {e.message} (path: {list(e.absolute_path)})")
        return errors

    # 2. 额外业务规则
    # 2.1 时间格式可解析
    try:
        datetime.fromisoformat(card["created"].replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"created time format error: {card['created']}")

    # 2.2 allow_write 不能完全包含于 deny_write（必须留可写路径）
    allow = set(card["scope"]["allow_write"])
    deny = set(card["scope"]["deny_write"])
    if allow.issubset(deny):
        errors.append("allow_write is fully contained in deny_write, leaving no writable path")

    # 2.3 acceptance_tests 必须落在测试工程目录下
    # 适配本项目布局：测试工程名是 *.Tests/（如 GenCollector.Tests/），
    # 而不是集中式 tests/ 目录。架构师原始规则需放宽。
    for t in card["acceptance_tests"]:
        if not (t.startswith("tests/") or ".Tests/" in t):
            errors.append(f"acceptance_tests must start with tests/ or live in a *.Tests/ project: {t}")

    # 2.4 done_when 里不能有未定义的 gate
    valid_gates = {
        "build", "test", "acceptance_tests", "coverage_diff",
        "mutation_test", "contract_consistency", "no_generated_code_modified",
        "architecture_tests",
    }
    for cond in card["done_when"]:
        gate = cond.replace("ci: ", "").strip()
        if gate not in valid_gates:
            errors.append(f"done_when references unknown gate: {gate}")

    return errors


def main():
    schema = load_schema()
    if len(sys.argv) >= 2 and sys.argv[1] == "--all":
        cards = sorted(ACTIVE_DIR.glob("TASK-*.yaml"))
        if not cards:
            print("[WARN] no task cards under .harness/tasks/active/")
            sys.exit(0)
    elif len(sys.argv) == 2:
        cards = [Path(sys.argv[1])]
    else:
        print(__doc__)
        sys.exit(2)

    total_errors = 0
    for card in cards:
        errors = validate_card(card, schema)
        if errors:
            total_errors += len(errors)
            print(f"[FAIL] {card.name}")
            for e in errors:
                print(f"       - {e}")
        else:
            print(f"[OK]   {card.name}")

    if total_errors:
        print(f"\n{total_errors} error(s) total")
        sys.exit(1)
    print("\nall task cards validated OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
