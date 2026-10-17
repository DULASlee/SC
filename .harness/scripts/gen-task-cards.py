#!/usr/bin/env python3
"""任务卡生成器 —— 从施工包清单生成任务卡。

设计依据：设计规格 P-1/P-2 —— 强模型只写验收测试，卡由本脚本生成。
弱模型（执行方）不接触本脚本，也不自写验收标准。

用法:
  python .harness/scripts/gen-task-cards.py --manifest <path> [--dry-run]
                                            [--out-dir <dir>] [--force]

清单格式（YAML）:
  batch: <批次名>
  created_by: architect | strong-model
  defaults:
    done_when: ["ci: harness_tests"]
    deny_write: ["src/**", "tests/**", "contracts/**", ".github/**", ".harness/runs/**", ".harness/worktrees/**"]
    constraints: {max_lines_changed: 300, max_files_changed: 10}
  tasks:
    - id: TASK-050
      title: "..."
      acceptance_tests: [".harness/tests/test_x.py"]
      allow_write: [".harness/scripts/validate-task-card.py"]
      covers: [REQ-001]
      contracts: [CTR-001]
      depends_on: [TASK-049]
      notes: |
        ...

退出码: 0 成功 / 1 有卡校验失败 / 2 参数或清单错误
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

# Windows 控制台默认 GBK，会把中文输出打乱；强制 UTF-8（本仓既有约定：编码显式化）
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HARNESS = Path(__file__).resolve().parent.parent
REPO_ROOT = HARNESS.parent
VALIDATOR = HARNESS / "scripts" / "validate-task-card.py"
DEFAULT_OUT = HARNESS / "tasks" / "active"
ACTIVE_DIR = HARNESS / "tasks" / "active"
ARCHIVE_DIR = HARNESS / "tasks" / "archive"

# deny 优先：这些路径任何生成卡都不得写。注意 .harness 下只禁运行时
# 状态目录（账本/工作区），scripts/tests/evidence/tasks 必须可写，
# 否则生成卡 allow 必然被吞（deny 优先下 allow 形同虚设）。
ALWAYS_DENY = ["src/**", "tests/**", "contracts/**", ".github/**",
               ".harness/runs/**", ".harness/worktrees/**"]


def preflight_validate(specs: list[dict], defaults: dict) -> list[str]:
    """清单级引用完整性校验：重复 ID / 归档冲突 / 悬空依赖。

    返回所有错误（每条一条字符串）；空列表 = 通过。
    任何错误都拒绝整批 —— 绝不允许部分落盘。
    """
    errs: list[str] = []

    # 1) 清单内重复 ID
    seen: dict[str, int] = {}
    for spec in specs:
        tid = (spec or {}).get("id")
        if not tid:
            continue
        seen[tid] = seen.get(tid, 0) + 1
    dups = sorted(tid for tid, n in seen.items() if n > 1)
    for tid in dups:
        errs.append("duplicate task id in manifest: %s" % tid)

    # 2) id 与 archive 中已归档的 TASK-ID 冲突
    archived_ids = set()
    if ARCHIVE_DIR.is_dir():
        archived_ids = {p.stem for p in ARCHIVE_DIR.glob("TASK-*.yaml")}
    for spec in specs:
        tid = (spec or {}).get("id")
        if tid and tid in archived_ids:
            errs.append("id collides with archived card: %s" % tid)

    # 3) depends_on 引用不存在的 TASK-ID
    #    known = active 目录中已存在的 + 本清单准备创建的（允许前向引用）
    active_ids = set()
    if ACTIVE_DIR.is_dir():
        active_ids = {p.stem for p in ACTIVE_DIR.glob("TASK-*.yaml")}
    manifest_ids = {(spec or {}).get("id") for spec in specs if (spec or {}).get("id")}
    known = active_ids | manifest_ids
    for spec in specs:
        deps = (spec or {}).get("depends_on") or []
        for d in deps:
            if d not in known:
                errs.append("dangling dependency: %s -> %s" % ((spec or {}).get("id"), d))

    return errs


def load_validator():
    spec = importlib.util.spec_from_file_location("harness_validator_gen", VALIDATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_manifest(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit("[FAIL] manifest not found: %s" % path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise SystemExit("[FAIL] manifest YAML parse error: %s" % e)
    if not isinstance(data, dict):
        raise SystemExit("[FAIL] manifest must be a YAML mapping")
    if not data.get("tasks"):
        raise SystemExit("[FAIL] manifest has no 'tasks' list")
    return data


def build_card(spec: dict, defaults: dict, created_by: str) -> dict:
    """把清单条目展开成完整任务卡 dict。"""
    if not spec.get("id") or not spec.get("title"):
        raise SystemExit("[FAIL] task entry missing id/title: %r" % (spec,))
    if not spec.get("acceptance_tests"):
        raise SystemExit("[FAIL] %s: acceptance_tests is required" % spec["id"])
    if not spec.get("allow_write"):
        raise SystemExit("[FAIL] %s: allow_write is required" % spec["id"])

    deny = list(defaults.get("deny_write") or [])
    for p in ALWAYS_DENY:
        if p not in deny:
            deny.append(p)

    card = {
        "id": spec["id"],
        "title": spec["title"],
        "status": "ready",
        "created": now_iso(),
        "created_by": created_by,
        "scope": {
            "allow_write": list(spec["allow_write"]),
            "deny_write": deny,
        },
        "acceptance_tests": list(spec["acceptance_tests"]),
        "done_when": list(spec.get("done_when") or defaults.get("done_when") or ["ci: harness_tests"]),
    }

    constraints = dict(defaults.get("constraints") or {})
    constraints.update(spec.get("constraints") or {})
    if constraints:
        card["constraints"] = constraints

    if spec.get("depends_on"):
        card["depends_on"] = list(spec["depends_on"])
    if spec.get("covers"):
        card["covers"] = list(spec["covers"])
    if spec.get("contracts"):
        card["contracts"] = list(spec["contracts"])
    if spec.get("references"):
        card["references"] = list(spec["references"])
    if spec.get("notes"):
        card["notes"] = spec["notes"]
    if spec.get("skills"):
        card["skills"] = list(spec["skills"])
    if spec.get("model"):
        card["model"] = spec["model"]

    return card


def validate_generated(card: dict) -> list[str]:
    """写临时文件后交给 validate-task-card 校验（含存在性检查）。"""
    mod = load_validator()
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / ("%s.yaml" % card["id"])
        p.write_text(yaml.safe_dump(card, allow_unicode=True, sort_keys=False),
                     encoding="utf-8")
        return mod.validate_card(p, mod.load_schema(), repo_root=REPO_ROOT)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate task cards from a manifest.")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    manifest = load_manifest(Path(args.manifest))
    created_by = manifest.get("created_by") or "strong-model"
    if created_by not in ("architect", "strong-model"):
        raise SystemExit("[FAIL] created_by must be architect or strong-model")
    defaults = manifest.get("defaults") or {}
    out_dir = Path(args.out_dir)
    batch = manifest.get("batch") or "(unnamed)"

    print("[INFO] batch=%s tasks=%d created_by=%s" % (batch, len(manifest["tasks"]), created_by))

    # Pre-flight: 引用完整性校验（重复 ID / 归档冲突 / 悬空依赖）。
    # 任何错误都拒绝整批 —— 绝不允许部分落盘。
    preflight = preflight_validate(manifest["tasks"], defaults)
    if preflight:
        print("[FAIL] preflight reference integrity errors (%d):" % len(preflight))
        for e in preflight:
            print("       - %s" % e)
        return 1

    failed = 0
    for spec in manifest["tasks"]:
        card = build_card(spec, defaults, created_by)
        errs = validate_generated(card)
        if errs:
            failed += 1
            print("[FAIL] %s" % card["id"])
            for e in errs:
                print("       - %s" % e)
            continue

        text = yaml.safe_dump(card, allow_unicode=True, sort_keys=False)
        if args.dry_run:
            print("[OK]   %s (dry-run, not written)" % card["id"])
            print("----8<---- %s ----8<----" % card["id"])
            print(text)
            continue

        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / ("%s.yaml" % card["id"])
        if target.exists() and not args.force:
            failed += 1
            print("[FAIL] %s exists (use --force to overwrite)" % target.name)
            continue
        target.write_text(text, encoding="utf-8")
        print("[OK]   %s -> %s" % (card["id"], target))

    if failed:
        print("\n%d card(s) failed" % failed)
        return 1
    print("\nall cards generated OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
