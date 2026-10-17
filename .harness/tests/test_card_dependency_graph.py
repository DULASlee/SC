"""P1 依赖图校验 — 验收测试（契约 v1.0 §2.2 / §6.2）。

覆盖：自依赖 / 悬空依赖 / 环检测 / 合法 DAG 通过。

初始状态：红（check_dependency_graph 尚不存在）
目标状态：绿

本文件只验证新机制本身，不对现有 27 张 active 卡做任何断言。
"""
import importlib.util
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent
SCRIPT = HARNESS / "scripts" / "validate-task-card.py"


def load_mod():
    spec = importlib.util.spec_from_file_location("harness_validate_p1", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def card(task_id, depends_on=None):
    return {
        "id": task_id,
        "title": "p1 fixture card",
        "status": "ready",
        "created": "2026-09-21T00:00:00Z",
        "created_by": "architect",
        "scope": {"allow_write": ["mod/a.txt"], "deny_write": ["src/**"]},
        "acceptance_tests": ["tests/A/T.cs"],
        "done_when": ["ci: build"],
        "depends_on": list(depends_on or []),
    }


class TestSelfDependency(unittest.TestCase):
    def test_self_dependency_rejected(self):
        mod = load_mod()
        cards = [card("TASK-901", ["TASK-901"])]
        errs = mod.check_dependency_graph(cards, {"TASK-901"})
        self.assertTrue(
            any("self-dependency" in e for e in errs),
            "自依赖必须被拒: %r" % (errs,))

    def test_no_dependencies_ok(self):
        mod = load_mod()
        cards = [card("TASK-901")]
        errs = mod.check_dependency_graph(cards, {"TASK-901"})
        self.assertEqual(errs, [], "无依赖应通过: %r" % (errs,))


class TestDanglingDependency(unittest.TestCase):
    def test_unknown_dependency_rejected(self):
        mod = load_mod()
        cards = [card("TASK-901", ["TASK-999"])]
        errs = mod.check_dependency_graph(cards, {"TASK-901"})
        self.assertTrue(
            any("unknown dependency" in e for e in errs),
            "悬空依赖必须被拒: %r" % (errs,))

    def test_known_dependency_ok(self):
        mod = load_mod()
        cards = [card("TASK-901", ["TASK-902"]), card("TASK-902")]
        errs = mod.check_dependency_graph(cards, {"TASK-901", "TASK-902"})
        self.assertEqual(errs, [], "已存在的依赖应通过: %r" % (errs,))

    def test_archived_dependency_counts_as_known(self):
        """known_ids 含 archive 里的卡，引用了就不算悬空。"""
        mod = load_mod()
        cards = [card("TASK-901", ["TASK-030"])]
        errs = mod.check_dependency_graph(cards, {"TASK-901", "TASK-030"})
        self.assertEqual(errs, [], "已归档依赖应通过: %r" % (errs,))


class TestCycleDetection(unittest.TestCase):
    def test_two_node_cycle_rejected(self):
        mod = load_mod()
        cards = [card("TASK-901", ["TASK-902"]), card("TASK-902", ["TASK-901"])]
        errs = mod.check_dependency_graph(cards, {"TASK-901", "TASK-902"})
        self.assertTrue(
            any("dependency cycle" in e for e in errs),
            "二元环必须被拒: %r" % (errs,))

    def test_three_node_cycle_rejected(self):
        mod = load_mod()
        cards = [
            card("TASK-901", ["TASK-902"]),
            card("TASK-902", ["TASK-903"]),
            card("TASK-903", ["TASK-901"]),
        ]
        errs = mod.check_dependency_graph(cards, {"TASK-901", "TASK-902", "TASK-903"})
        self.assertTrue(
            any("dependency cycle" in e for e in errs),
            "三元环必须被拒: %r" % (errs,))

    def test_cycle_message_contains_path(self):
        mod = load_mod()
        cards = [card("TASK-901", ["TASK-902"]), card("TASK-902", ["TASK-901"])]
        errs = mod.check_dependency_graph(cards, {"TASK-901", "TASK-902"})
        cyc = [e for e in errs if "dependency cycle" in e]
        self.assertTrue(cyc, "应有环报错")
        self.assertTrue(
            any("TASK-901" in e and "TASK-902" in e for e in cyc),
            "环报错应列出环上节点: %r" % (cyc,))

    def test_dag_ok(self):
        mod = load_mod()
        cards = [
            card("TASK-901"),
            card("TASK-902", ["TASK-901"]),
            card("TASK-903", ["TASK-902"]),
            card("TASK-904", ["TASK-901", "TASK-902"]),
        ]
        ids = {"TASK-901", "TASK-902", "TASK-903", "TASK-904"}
        errs = mod.check_dependency_graph(cards, ids)
        self.assertEqual(errs, [], "合法 DAG 必须通过: %r" % (errs,))

    def test_diamond_dag_ok(self):
        """菱形依赖（非环）不能被误判为环。"""
        mod = load_mod()
        cards = [
            card("TASK-901"),
            card("TASK-902", ["TASK-901"]),
            card("TASK-903", ["TASK-901"]),
            card("TASK-904", ["TASK-902", "TASK-903"]),
        ]
        ids = {"TASK-901", "TASK-902", "TASK-903", "TASK-904"}
        errs = mod.check_dependency_graph(cards, ids)
        self.assertEqual(errs, [], "菱形 DAG 必须通过: %r" % (errs,))

    def test_message_carries_task_id_prefix(self):
        mod = load_mod()
        cards = [card("TASK-901", ["TASK-902"]), card("TASK-902", ["TASK-901"])]
        errs = mod.check_dependency_graph(cards, {"TASK-901", "TASK-902"})
        self.assertTrue(errs, "应产生错误")
        self.assertTrue(
            all(e.split(":")[0].startswith("TASK-") for e in errs),
            "每条消息必须以 TASK-ID 前缀开头: %r" % (errs,))


if __name__ == "__main__":
    unittest.main()
