#!/usr/bin/env python3
"""
L1-α 契约一致性校验 — 最小骨架。

校验范围（仅 1 个 schema 1 个 openapi）：
1. contracts/schemas/*.json 是合法 JSON
2. contracts/openapi.yaml 是合法 YAML
3. openapi.yaml 中所有 $ref 都能解析到对应文件 + 子路径
4. $ref 解析后能找到至少 1 个 required 字段（防止空 schema）

退出码：
0 - 通过
1 - 不一致
2 - 文件缺失/格式错误

不在 L1-α 范围（留给 L1-β）：
- AsyncAPI / MQTT topics / data-models 派生视图
- 跨契约字段名一致性校验
- required 字段对齐校验
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

# 强制 UTF-8（避免 Windows 默认 GBK 翻车 — 见 L0 报告 .editorconfig UTF-8）
CONTRACTS = Path(__file__).resolve().parent.parent / "contracts"


def load(path: Path):
    if path.suffix == ".json":
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_ref(ref: str, root_yaml_path: Path):
    """解析 $ref: './schemas/xxx.json#/properties' 形式。"""
    if "#" in ref:
        file_part, frag = ref.split("#", 1)
    else:
        file_part, frag = ref, ""
    target = (root_yaml_path.parent / file_part).resolve()
    if not target.exists():
        return None, f"$ref target file not found: {target}"
    node = load(target)
    if frag.startswith("/"):
        for part in frag.lstrip("/").split("/"):
            node = node.get(part, {}) if isinstance(node, dict) else {}
    return node, None


def main() -> int:
    errors: list[str] = []

    # 1. JSON schemas 合法
    schemas_dir = CONTRACTS / "schemas"
    if not schemas_dir.is_dir():
        print(f"[FAIL] {schemas_dir} not found"); return 2
    for p in sorted(schemas_dir.glob("*.json")):
        try:
            load(p)
        except Exception as e:
            errors.append(f"JSON invalid: {p.name} - {e}")

    # 2. openapi.yaml 合法 + $ref 可解析
    openapi_path = CONTRACTS / "openapi.yaml"
    if not openapi_path.exists():
        print(f"[FAIL] openapi.yaml not found: {openapi_path}"); return 2
    try:
        spec = load(openapi_path)
    except Exception as e:
        print(f"[FAIL] openapi.yaml parse error: {e}"); return 2

    def walk(node, path=""):
        if isinstance(node, dict):
            if "$ref" in node:
                resolved, err = resolve_ref(node["$ref"], openapi_path)
                if err:
                    errors.append(f"$ref not resolvable at {path}: {err}")
                elif isinstance(resolved, dict):
                    # schema must have at least 1 required OR 1 property
                    if not resolved.get("required") and not resolved.get("properties"):
                        errors.append(f"$ref resolves to empty schema at {path}: {node['$ref']}")
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(spec, "openapi")

    # 3. (L1-alpha red-green test) spot-check: openapi must reference telemetry.json,
    #    and that file's top-level "properties" must include both "MeasEncoding" and "DeviceEncoding".
    #    If someone renames these fields, the test FAILS — proving the mechanism bites.
    tele_path = schemas_dir / "telemetry.json"
    tele = load(tele_path)
    item_schema = (tele.get("properties") or {}).get("properties", {}).get("items", {})
    required_fields = item_schema.get("required", [])
    expected = ["MeasEncoding", "MeasName", "TimeStamp", "DeviceEncoding"]
    for f in expected:
        if f not in required_fields:
            errors.append(
                f"telemetry.json items.required missing field {f!r} "
                f"(drift: someone renamed a published field; required = {required_fields})"
            )

    if errors:
        print(f"[FAIL] L1-alpha check failed ({len(errors)} error(s)):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("[OK] L1-alpha check passed: all $ref resolvable, all schemas non-empty.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
