"""P0 验收信号真实化 — 验收测试（契约 v1.0 §2.1 / §2.2 / §6.1）。

覆盖：
  A. 测试路径根放开（.harness/tests/ 被接受；tests/ 与 *.Tests/ 不回归）
  B. 测试文件存在性检查
  C. 同一测试文件多卡共享拒绝

初始状态：红（check_test_sharing 尚不存在；.harness/tests/ 根尚未放开）
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
    spec = importlib.util.spec_from_file_location("harness_validate_p0", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def card(task_id, tests, **kw):
    c = {
        "id": task_id,
        "title": "p0 fixture card",
        "status": "ready",
        "created": "2026-09-21T00:00:00Z",
        "created_by": "architect",
        "scope": {"allow_write": ["mod/a.txt"], "deny_write": ["src/**"]},
        "acceptance_tests": tests,
        "done_when": ["ci: build"],
    }
    c.update(kw)
    return c


def write_card(path, c):
    import yaml
    path.write_text(yaml.safe_dump(c, allow_unicode=True), encoding="utf-8")


class TestAllowedTestRoots(unittest.TestCase):
    """契约 §2.1：accepted roots = tests/ | *.Tests/ | .harness/tests/"""

    def _validate(self, tests, create=True):
        mod = load_mod()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in tests:
                f = root / rel
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text("", encoding="utf-8")
            p = root / "TASK-901.yaml"
            write_card(p, card("TASK-901", tests))
            return mod.validate_card(p, mod.load_schema(), repo_root=root)

    def test_harness_tests_root_accepted(self):
        errs = self._validate([".harness/tests/test_x.py"])
        self.assertEqual(errs, [], "P0: .harness/tests/ 必须被接受为 acceptance_tests 根: %r" % (errs,))

    def test_plain_tests_root_still_accepted(self):
        errs = self._validate(["tests/GenCollector.Tests/LessonsIndexTests.cs"])
        self.assertEqual(errs, [], "回归: tests/ 根不能被新规则误伤: %r" % (errs,))

    def test_dotnet_tests_project_still_accepted(self):
        errs = self._validate(["GenCollector.Tests/CollectorEngineTests.cs"])
        self.assertEqual(errs, [], "回归: *.Tests/ 不能被新规则误伤: %r" % (errs,))

    def test_docs_path_still_rejected(self):
        mod = load_mod()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = root / "docs" / "rules" / "lessons.md"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("", encoding="utf-8")
            p = root / "TASK-901.yaml"
            write_card(p, card("TASK-901", ["docs/rules/lessons.md"]))
            errs = mod.validate_card(p, mod.load_schema(), repo_root=root)
            self.assertTrue(
                any("acceptance_tests root not allowed" in e for e in errs),
                "非法根必须被拒且含关键字: %r" % (errs,))


class TestTestFileExistence(unittest.TestCase):
    """契约 §2.1：repo_root 非 None 时，引用的测试文件必须存在。"""

    def test_missing_test_file_rejected(self):
        mod = load_mod()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "TASK-901.yaml"
            write_card(p, card("TASK-901", ["tests/Ghost/NoSuchTest.cs"]))
            errs = mod.validate_card(p, mod.load_schema(), repo_root=root)
            self.assertTrue(
                any("acceptance_tests file not found" in e for e in errs),
                "不存在的测试文件必须被拒: %r" % (errs,))

    def test_existing_test_file_accepted(self):
        mod = load_mod()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = root / "tests" / "Real" / "RealTest.cs"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("", encoding="utf-8")
            p = root / "TASK-901.yaml"
            write_card(p, card("TASK-901", ["tests/Real/RealTest.cs"]))
            errs = mod.validate_card(p, mod.load_schema(), repo_root=root)
            self.assertEqual(errs, [], "存在的测试文件应通过: %r" % (errs,))

    def test_existence_check_skipped_without_repo_root(self):
        """向后兼容：老调用方不传 repo_root 时不得因存在性报错。"""
        mod = load_mod()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TASK-901.yaml"
            write_card(p, card("TASK-901", ["tests/Ghost/NoSuchTest.cs"]))
            errs = mod.validate_card(p, mod.load_schema())
            self.assertFalse(
                any("acceptance_tests file not found" in e for e in errs),
                "未传 repo_root 时不应做存在性检查: %r" % (errs,))


class TestTestSharing(unittest.TestCase):
    """契约 §6.1：同一测试文件被 >= threshold 张卡引用则报错。"""

    def test_single_owner_ok(self):
        mod = load_mod()
        errs = mod.check_test_sharing([card("TASK-901", ["tests/A/T.cs"])], threshold=2)
        self.assertEqual(errs, [], "单卡独占应通过: %r" % (errs,))

    def test_two_owners_ok_at_threshold_two(self):
        mod = load_mod()
        cards = [card("TASK-901", ["tests/A/T.cs"]), card("TASK-902", ["tests/A/T.cs"])]
        errs = mod.check_test_sharing(cards, threshold=2)
        self.assertEqual(errs, [], "阈值 2 时两卡共享应通过: %r" % (errs,))

    def test_three_owners_rejected(self):
        mod = load_mod()
        cards = [
            card("TASK-901", ["tests/A/T.cs"]),
            card("TASK-902", ["tests/A/T.cs"]),
            card("TASK-903", ["tests/A/T.cs"]),
        ]
        errs = mod.check_test_sharing(cards, threshold=2)
        self.assertTrue(
            any("acceptance_tests shared by" in e for e in errs),
            "三卡共享同一测试必须被拒: %r" % (errs,))

    def test_cards_without_tests_ignored(self):
        mod = load_mod()
        cards = [card("TASK-901", ["tests/A/T.cs"]), card("TASK-902", ["tests/B/U.cs"])]
        errs = mod.check_test_sharing(cards, threshold=2)
        self.assertEqual(errs, [], "不同测试文件不应互相影响: %r" % (errs,))

    def test_message_carries_task_id_prefix(self):
        mod = load_mod()
        cards = [card("TASK-90%d" % i, ["tests/A/T.cs"]) for i in (1, 2, 3)]
        errs = mod.check_test_sharing(cards, threshold=2)
        self.assertTrue(errs, "应产生错误")
        self.assertTrue(
            all(e.split(":")[0].startswith("TASK-") for e in errs),
            "每条消息必须以 TASK-ID 前缀开头: %r" % (errs,))


class TestDraftExemption(unittest.TestCase):
    """草稿卡按定义不完整，可引用尚未写出的测试文件。"""

    def test_draft_card_exempt_from_existence_check(self):
        mod = load_mod()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "TASK-901.yaml"
            c = card("TASK-901", ["tests/Ghost/NoSuchTest.cs"])
            c["status"] = "draft"
            write_card(p, c)
            errs = mod.validate_card(p, mod.load_schema(), repo_root=root)
            self.assertFalse(
                any("acceptance_tests file not found" in e for e in errs),
                "draft 卡应豁免存在性检查: %r" % (errs,))

    def test_ready_card_still_checked(self):
        """回归：ready 卡不享受豁免。"""
        mod = load_mod()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "TASK-901.yaml"
            write_card(p, card("TASK-901", ["tests/Ghost/NoSuchTest.cs"]))
            errs = mod.validate_card(p, mod.load_schema(), repo_root=root)
            self.assertTrue(
                any("acceptance_tests file not found" in e for e in errs),
                "ready 卡必须仍受存在性检查: %r" % (errs,))


if __name__ == "__main__":
    unittest.main()
