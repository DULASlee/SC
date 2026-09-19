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


def _collect_declarations(node, prefix=""):
    """收集 json schema 中显式声明的字段路径（含嵌套 object + 数组 items）。"""
    if not isinstance(node, dict):
        return
    props = node.get("properties")
    if isinstance(props, dict):
        for k, v in props.items():
            yield f"{prefix}.{k}" if prefix else k
            yield from _collect_declarations(v, f"{prefix}.{k}" if prefix else k)
    if isinstance(node.get("items"), dict):
        yield from _collect_declarations(node["items"], f"{prefix}[]")


def load_declarations():
    """返回 schema 已声明字段的全集（绝对路径前缀匹配用）。"""
    schema = load_schema()
    return set(_collect_declarations(schema))


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

    # 1.5 检测面自检回路（判据 4/5）：jsonschema 的 additionalProperties 是主防线
    #     （笼统报错）；此处是「点名 + 修复指引」增强层——把笼统报错升级为指名道姓的
    #     未声明字段清单，避免未来有人把 schema 误改宽松后检测面整体失效无人发现。
    #     只在 schema 校验通过（或错误已收集）后追加，不改变 jsonschema 的拦截结果。
    declared_top = {d.split(".")[0] for d in load_declarations()}
    undeclared = [k for k in card.keys() if k not in declared_top]
    if undeclared:
        errors.append(
            f"schema 未声明字段（检测面点名，schema 与数据分叉）：{undeclared}；"
            f"请先在 {SCHEMA_PATH.name} 的 properties 中补定义再提交"
        )

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
        # 检测面：drafts 目录一并校验（堵「挪到 drafts 逃过检测」旁路，判据 4）
        drafts_dir = ACTIVE_DIR.parent / "drafts"
        if drafts_dir.is_dir():
            cards += sorted(drafts_dir.glob("TASK-*.yaml"))
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
