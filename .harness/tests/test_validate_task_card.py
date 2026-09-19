"""validate-task-card 单测（TASK-030：功能验证 + 输出 ASCII 断言）。

覆盖：
1. 合法卡通过（0 错误）
2. 缺必填字段 / 非法 gate / 2.3 违例 → 报错（拦截真触发）
3. CLI 运行输出无非 ASCII 字符（024 C3 余面归零判据）
"""
import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "validate-task-card.py"
SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "task-card.schema.json"


def load_mod():
    spec = importlib.util.spec_from_file_location("harness_validate_task_card_030", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def valid_card_dict():
    return {
        "id": "TASK-901",
        "title": "ascii output test card",
        "status": "ready",
        "created": "2026-09-19T00:00:00Z",
        "created_by": "architect",
        "scope": {"allow_write": ["mod/a.txt"], "deny_write": ["src/**"]},
        "acceptance_tests": ["tests/GenCollector.Tests/LessonsIndexTests.cs"],
        "done_when": ["ci: build"],
    }


def write_card(path: Path, card: dict):
    import yaml
    path.write_text(yaml.safe_dump(card, allow_unicode=True), encoding="utf-8")


class TestValidateCard(unittest.TestCase):
    def setUp(self):
        self.mod = load_mod()
        self.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_valid_card_passes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TASK-901.yaml"
            write_card(p, valid_card_dict())
            self.assertEqual(self.mod.validate_card(p, self.schema), [])

    def test_missing_required_field_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            card = valid_card_dict()
            del card["acceptance_tests"]
            p = Path(tmp) / "TASK-901.yaml"
            write_card(p, card)
            errors = self.mod.validate_card(p, self.schema)
            self.assertTrue(errors, "缺必填字段必须报错")

    def test_bad_acceptance_path_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            card = valid_card_dict()
            card["acceptance_tests"] = ["docs/rules/lessons.md"]
            p = Path(tmp) / "TASK-901.yaml"
            write_card(p, card)
            errors = self.mod.validate_card(p, self.schema)
            self.assertTrue(any("tests/" in e for e in errors))

    def test_unknown_gate_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            card = valid_card_dict()
            card["done_when"] = ["ci: nonexistent_gate"]
            p = Path(tmp) / "TASK-901.yaml"
            write_card(p, card)
            errors = self.mod.validate_card(p, self.schema)
            self.assertTrue(errors)


class TestCliOutputAscii(unittest.TestCase):
    def test_all_mode_output_is_ascii(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--all"],
            cwd=SCRIPT.parents[2], capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            env={"PYTHONIOENCODING": "utf-8", "PATH": os.environ["PATH"]},
        )
        out = r.stdout + r.stderr
        self.assertTrue(out.isascii(), f"非 ASCII 输出残留: {out!r}")

    def test_bare_invocation_docstring_is_ascii(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=SCRIPT.parents[2], capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            env={"PYTHONIOENCODING": "utf-8", "PATH": os.environ["PATH"]},
        )
        out = r.stdout + r.stderr
        self.assertTrue(out.isascii(), f"裸运行输出非 ASCII: {out!r}")


if __name__ == "__main__":
    unittest.main()
