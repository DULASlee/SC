"""P2 需求追溯 + P3 契约引用 — 验收测试（契约 v1.0 §2.2 / §6.3 / §6.4）。

覆盖：covers 引用完整性 / 未覆盖需求检出 / contracts 引用完整性 / 契约冻结检查。

初始状态：红（check_requirement_refs / check_contract_refs / load_registry 尚不存在）
目标状态：绿

本文件只验证新机制本身，不对现有 27 张 active 卡做任何断言。
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent
SCRIPT = HARNESS / "scripts" / "validate-task-card.py"


def load_mod():
    spec = importlib.util.spec_from_file_location("harness_validate_p2", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def card(task_id, covers=None, contracts=None):
    return {
        "id": task_id,
        "title": "p2 fixture card",
        "status": "ready",
        "created": "2026-09-21T00:00:00Z",
        "created_by": "architect",
        "scope": {"allow_write": ["mod/a.txt"], "deny_write": ["src/**"]},
        "acceptance_tests": ["tests/A/T.cs"],
        "done_when": ["ci: build"],
        "covers": list(covers or []),
        "contracts": list(contracts or []),
    }


def req_registry(items):
    return {"schema_version": 1, "items": list(items)}


def ctr_registry(items):
    return {"schema_version": 1, "items": list(items)}


class TestRequirementRefs(unittest.TestCase):
    def test_known_requirement_ok(self):
        mod = load_mod()
        cards = [card("TASK-901", covers=["REQ-001"])]
        reg = req_registry([{"id": "REQ-001", "title": "r1", "source": "s", "status": "active"}])
        errs = mod.check_requirement_refs(cards, reg)
        self.assertEqual(errs, [], "已登记需求应通过: %r" % (errs,))

    def test_unknown_requirement_rejected(self):
        mod = load_mod()
        cards = [card("TASK-901", covers=["REQ-999"])]
        reg = req_registry([{"id": "REQ-001", "title": "r1", "source": "s", "status": "active"}])
        errs = mod.check_requirement_refs(cards, reg)
        self.assertTrue(
            any("unknown requirement" in e for e in errs),
            "未登记需求 ID 必须被拒: %r" % (errs,))

    def test_uncovered_active_requirement_reported(self):
        mod = load_mod()
        cards = [card("TASK-901", covers=["REQ-001"])]
        reg = req_registry([
            {"id": "REQ-001", "title": "r1", "source": "s", "status": "active"},
            {"id": "REQ-002", "title": "r2", "source": "s", "status": "active"},
        ])
        errs = mod.check_requirement_refs(cards, reg)
        self.assertTrue(
            any("uncovered requirement" in e and "REQ-002" in e for e in errs),
            "无卡承接的 active 需求必须被报出: %r" % (errs,))

    def test_done_requirement_not_required_to_cover(self):
        mod = load_mod()
        cards = [card("TASK-901")]
        reg = req_registry([
            {"id": "REQ-001", "title": "r1", "source": "s", "status": "done"},
            {"id": "REQ-002", "title": "r2", "source": "s", "status": "dropped"},
        ])
        errs = mod.check_requirement_refs(cards, reg)
        self.assertEqual(errs, [], "done/dropped 需求不要求被覆盖: %r" % (errs,))

    def test_missing_covers_treated_as_empty(self):
        mod = load_mod()
        c = card("TASK-901")
        del c["covers"]
        errs = mod.check_requirement_refs([c], req_registry([]))
        self.assertEqual(errs, [], "缺省 covers 视为空数组: %r" % (errs,))

    def test_message_carries_task_id_prefix(self):
        mod = load_mod()
        cards = [card("TASK-901", covers=["REQ-999"])]
        errs = mod.check_requirement_refs(cards, req_registry([]))
        self.assertTrue(errs, "应产生错误")
        self.assertTrue(
            all(e.split(":")[0].startswith("TASK-") for e in errs),
            "每条消息必须以 TASK-ID 前缀开头: %r" % (errs,))


class TestContractRefs(unittest.TestCase):
    def test_frozen_contract_ok(self):
        mod = load_mod()
        cards = [card("TASK-901", contracts=["CTR-001"])]
        reg = ctr_registry([{"id": "CTR-001", "title": "c1", "path": "p", "frozen": True}])
        errs = mod.check_contract_refs(cards, reg)
        self.assertEqual(errs, [], "已冻结契约应通过: %r" % (errs,))

    def test_unknown_contract_rejected(self):
        mod = load_mod()
        cards = [card("TASK-901", contracts=["CTR-999"])]
        reg = ctr_registry([{"id": "CTR-001", "title": "c1", "path": "p", "frozen": True}])
        errs = mod.check_contract_refs(cards, reg)
        self.assertTrue(
            any("unknown contract" in e for e in errs),
            "未登记契约 ID 必须被拒: %r" % (errs,))

    def test_unfrozen_contract_rejected(self):
        mod = load_mod()
        cards = [card("TASK-901", contracts=["CTR-001"])]
        reg = ctr_registry([{"id": "CTR-001", "title": "c1", "path": "p", "frozen": False}])
        errs = mod.check_contract_refs(cards, reg)
        self.assertTrue(
            any("contract not frozen" in e for e in errs),
            "未冻结契约不得被卡依赖: %r" % (errs,))

    def test_missing_contracts_treated_as_empty(self):
        mod = load_mod()
        c = card("TASK-901")
        del c["contracts"]
        errs = mod.check_contract_refs([c], ctr_registry([]))
        self.assertEqual(errs, [], "缺省 contracts 视为空数组: %r" % (errs,))

    def test_message_carries_task_id_prefix(self):
        mod = load_mod()
        cards = [card("TASK-901", contracts=["CTR-999"])]
        errs = mod.check_contract_refs(cards, ctr_registry([]))
        self.assertTrue(errs, "应产生错误")
        self.assertTrue(
            all(e.split(":")[0].startswith("TASK-") for e in errs),
            "每条消息必须以 TASK-ID 前缀开头: %r" % (errs,))


class TestLoadRegistry(unittest.TestCase):
    def test_missing_registry_returns_empty(self):
        mod = load_mod()
        with tempfile.TemporaryDirectory() as tmp:
            reg = mod.load_registry(Path(tmp), "requirements")
            self.assertEqual(reg.get("items"), [], "缺文件时应返回空表: %r" % (reg,))

    def test_existing_registry_parsed(self):
        mod = load_mod()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / ".harness" / "registry"
            d.mkdir(parents=True, exist_ok=True)
            (d / "requirements.yaml").write_text(
                "schema_version: 1\nitems:\n  - id: REQ-001\n    title: t\n"
                "    source: s\n    status: active\n",
                encoding="utf-8")
            reg = mod.load_registry(root, "requirements")
            self.assertEqual(len(reg.get("items", [])), 1, "应解析出 1 条: %r" % (reg,))
            self.assertEqual(reg["items"][0]["id"], "REQ-001")


if __name__ == "__main__":
    unittest.main()
