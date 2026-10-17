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
REPO_ROOT = HARNESS_DIR.parent
SCHEMA_PATH = HARNESS_DIR / "schema" / "task-card.schema.json"
ACTIVE_DIR = HARNESS_DIR / "tasks" / "active"
ARCHIVE_DIR = HARNESS_DIR / "tasks" / "archive"
BASELINE_PATH = HARNESS_DIR / "registry" / "known-shared-tests.yaml"

# TASK-050：验收测试根放开。此前只允许 tests/ 与 *.Tests/，
# 导致修改 harness 自身的任务卡结构性地无法引用 .harness/tests/ 下的真实测试，
# 只能填无关的既有测试工程（占位），"Done 只来自 CI" 因而失去依据。
ALLOWED_TEST_ROOTS = ("tests/", ".harness/tests/")
ALLOWED_TEST_SUFFIX_DIR = ".Tests/"
SHARED_TEST_THRESHOLD = 2


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


def test_root_allowed(t):
    """验收测试路径是否落在允许的根下。"""
    return t.startswith(ALLOWED_TEST_ROOTS) or ALLOWED_TEST_SUFFIX_DIR in t


def validate_card(card_path, schema, repo_root=None):
    """卡级校验。

    repo_root: 非 None 时启用 acceptance_tests 存在性检查。
               默认 None 保持向后兼容（老调用方不传也能跑）。
    """
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

    # 2.3 acceptance_tests 必须落在允许的测试根下
    #     tests/ | *.Tests/ | .harness/tests/（TASK-050 新增第三项）
    for t in card["acceptance_tests"]:
        if not test_root_allowed(t):
            errors.append(
                "acceptance_tests root not allowed (must be under tests/ or "
                f".harness/tests/ or a *.Tests/ project): {t}"
            )

    # 2.4 done_when 里不能有未定义的 gate
    valid_gates = {
        "build", "test", "acceptance_tests", "coverage_diff",
        "mutation_test", "contract_consistency", "no_generated_code_modified",
        "architecture_tests", "harness_tests",
    }
    for cond in card["done_when"]:
        gate = cond.replace("ci: ", "").strip()
        if gate not in valid_gates:
            errors.append(f"done_when references unknown gate: {gate}")

    # 2.5 验收测试文件必须存在（仅在给定 repo_root 时启用）
    #     draft 卡豁免：草稿按定义不完整，可能引用尚未写出的测试。
    #     存在性检查只对 ready 及之后的卡生效。
    if repo_root is not None and card.get("status") != "draft":
        root = Path(repo_root)
        for t in card["acceptance_tests"]:
            if not (root / t).is_file():
                errors.append(f"acceptance_tests file not found: {t}")

    return errors


def load_baseline():
    """读历史遗留共享清单。

    返回 {path: {card_id, ...}}。文件不存在或不可解析时返回空表
    （空表 = 不做豁免，全部按新规则判）。
    """
    if not BASELINE_PATH.is_file():
        return {}
    try:
        data = yaml.safe_load(BASELINE_PATH.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    out = {}
    for e in (data.get("baseline") or []):
        if isinstance(e, dict) and e.get("path"):
            out[e["path"]] = set(e.get("cards") or [])
    return out


def check_test_sharing(cards, threshold=SHARED_TEST_THRESHOLD, baseline=None):
    """同一验收测试文件被过多卡引用 -> 报错（拦「批量占位」模式）。

    cards: list[dict]
    baseline: {path: {card_id, ...}} 历史遗留豁免。基线路径只对清单内的卡豁免；
              未列入清单的卡引用基线路径同样报错（防止新卡复用旧占位）。
    返回: list[str]，每条形如 "<TASK-ID>: <message>"
    """
    baseline = baseline or {}
    by_path = {}
    for c in cards:
        tid = c.get("id") or "?"
        for t in (c.get("acceptance_tests") or []):
            by_path.setdefault(t, []).append(tid)

    errors = []
    for t, ids in sorted(by_path.items()):
        ids = sorted(set(ids))
        if t in baseline:
            allowed = baseline[t]
            intruders = [i for i in ids if i not in allowed]
            if intruders:
                errors.append(
                    "%s: acceptance_tests shared by %d cards "
                    "(baseline path reused by new card): %s"
                    % (intruders[0], len(ids), t)
                )
            continue
        if len(ids) > threshold:
            errors.append(
                "%s: acceptance_tests shared by %d cards: %s"
                % (ids[0], len(ids), t)
            )
    return errors


def check_dependency_graph(cards, known_ids):
    """自依赖 / 悬空依赖 / 环检测。

    cards: list[dict]
    known_ids: set[str]  active + archive 的全部 TASK-ID
    返回: list[str]，每条形如 "<TASK-ID>: <message>"
    """
    errors = []
    deps = {}
    for c in cards:
        tid = c.get("id")
        if tid:
            deps[tid] = list(c.get("depends_on") or [])

    # 自依赖 + 悬空
    for tid in sorted(deps):
        for d in deps[tid]:
            if d == tid:
                errors.append("%s: self-dependency: %s" % (tid, tid))
            elif d not in known_ids:
                errors.append("%s: unknown dependency: %s" % (tid, d))

    # 环检测（三色 DFS），按规范化后的环去重
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {t: WHITE for t in deps}
    stack = []
    seen_cycles = set()

    def visit(node):
        color[node] = GRAY
        stack.append(node)
        for d in deps.get(node, []):
            if d not in deps:
                continue  # 悬空已在上面报过
            if color.get(d) == GRAY:
                i = stack.index(d)
                cycle = stack[i:] + [d]
                key = tuple(sorted(set(cycle)))
                if key not in seen_cycles:
                    seen_cycles.add(key)
                    errors.append("%s: dependency cycle: %s" % (node, " -> ".join(cycle)))
            elif color.get(d) == WHITE:
                visit(d)
        stack.pop()
        color[node] = BLACK

    for t in sorted(deps):
        if color[t] == WHITE:
            visit(t)

    return errors


def load_registry(repo_root, name):
    """读 .harness/registry/<name>.yaml。

    name: "requirements" | "contracts"
    返回: dict；文件缺失或不可解析时返回 {"schema_version": 1, "items": []}
    """
    p = Path(repo_root) / ".harness" / "registry" / ("%s.yaml" % name)
    if not p.is_file():
        return {"schema_version": 1, "items": []}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {"schema_version": 1, "items": []}
    if not isinstance(data, dict):
        return {"schema_version": 1, "items": []}
    data.setdefault("items", [])
    return data


def check_requirement_refs(cards, registry):
    """covers 字段引用完整性 + 未覆盖需求检出。

    返回: list[str]，每条形如 "<TASK-ID>: <message>"
    """
    errors = []
    items = {}
    for i in (registry.get("items") or []):
        if isinstance(i, dict) and i.get("id"):
            items[i["id"]] = i

    covered = set()
    for c in cards:
        tid = c.get("id") or "?"
        for r in (c.get("covers") or []):
            if r not in items:
                errors.append("%s: unknown requirement: %s" % (tid, r))
            else:
                covered.add(r)

    for rid in sorted(items):
        if items[rid].get("status") == "active" and rid not in covered:
            errors.append("%s: uncovered requirement: no active card covers it" % rid)

    return errors


def check_contract_refs(cards, registry):
    """contracts 字段引用完整性 + frozen 检查。

    返回: list[str]，每条形如 "<TASK-ID>: <message>"
    """
    errors = []
    items = {}
    for i in (registry.get("items") or []):
        if isinstance(i, dict) and i.get("id"):
            items[i["id"]] = i

    for c in cards:
        tid = c.get("id") or "?"
        for k in (c.get("contracts") or []):
            if k not in items:
                errors.append("%s: unknown contract: %s" % (tid, k))
            elif not items[k].get("frozen"):
                errors.append("%s: contract not frozen: %s" % (tid, k))

    return errors


def _load_card_dict(path):
    try:
        with open(path, encoding="utf-8") as f:
            card = yaml.safe_load(f)
        return json.loads(json.dumps(card, default=str))
    except Exception:
        return None


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
        errors = validate_card(card, schema, repo_root=REPO_ROOT)
        if errors:
            total_errors += len(errors)
            print(f"[FAIL] {card.name}")
            for e in errors:
                print(f"       - {e}")
        else:
            print(f"[OK]   {card.name}")

    # 集合级检查：仅对 active 卡做（drafts 未定稿，不参与）
    if len(sys.argv) >= 2 and sys.argv[1] == "--all":
        active_cards = [d for d in (_load_card_dict(p) for p in sorted(ACTIVE_DIR.glob("TASK-*.yaml"))) if d]

        known_ids = set()
        for src in (ACTIVE_DIR, ARCHIVE_DIR):
            if src.is_dir():
                for cp in src.glob("TASK-*.yaml"):
                    d = _load_card_dict(cp)
                    if d and d.get("id"):
                        known_ids.add(d["id"])

        collection_checks = [
            ("acceptance test sharing", check_test_sharing(active_cards, SHARED_TEST_THRESHOLD, load_baseline())),
            ("dependency graph", check_dependency_graph(active_cards, known_ids)),
            ("requirement refs", check_requirement_refs(active_cards, load_registry(REPO_ROOT, "requirements"))),
            ("contract refs", check_contract_refs(active_cards, load_registry(REPO_ROOT, "contracts"))),
        ]
        for label, errs in collection_checks:
            if errs:
                total_errors += len(errs)
                print("[FAIL] %s" % label)
                for e in errs:
                    print("       - %s" % e)

    if total_errors:
        print(f"\n{total_errors} error(s) total")
        sys.exit(1)
    print("\nall task cards validated OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
