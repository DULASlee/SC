"""check-pr-scope TaskId 查找单测（TDD 先行，TASK-029 配套修复）。

背景：check-pr-scope.py 原实现按严格文件名 active/TASK-XXX.yaml 查卡，
而带人类可读后缀的卡（TASK-021-base-url-domain-error.yaml）会被误判
"任务卡不存在"。裁定：脚本改按卡内容 id 字段提取稳定 TaskId，
不破坏文件命名。

覆盖：
1. 裸文件名 TASK-901.yaml + id 字段匹配 → 找到
2. 后缀文件名 TASK-901-base-url.yaml + id 字段匹配 → 找到
3. 文件名与 id 字段不一致（TASK-901-foo.yaml 内 id: TASK-902）→ 不算 901 的卡
4. active/ 无匹配卡 → (None, None)，由调用方报"任务卡不存在"
5. 同 id 双卡并存 → (None, 冲突错误)，显式暴露不静默取一
"""
import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

CHECK_PR_SCOPE = (
    Path(__file__).resolve().parent.parent
    / "scripts" / "check-pr-scope.py"
)


def load_mod():
    spec = importlib.util.spec_from_file_location("check_pr_scope", CHECK_PR_SCOPE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_card(cards_dir: Path, name: str, card_id: str, status="ready"):
    card = {
        "id": card_id,
        "title": "task id lookup test card",
        "status": status,
        "created": "2026-09-19T00:00:00Z",
        "created_by": "architect",
        "scope": {
            "allow_write": ["docs/ai-workspace/rules/lessons-learned.md"],
            "deny_write": ["src/**"],
        },
        "acceptance_tests": ["tests/GenCollector.Tests/LessonsIndexTests.cs"],
        "done_when": ["ci: acceptance_tests"],
    }
    (cards_dir / name).write_text(
        yaml.safe_dump(card, allow_unicode=True), encoding="utf-8")


class TestTaskIdLookup(unittest.TestCase):
    def _lookup(self, tmp: str, task_id: str):
        mod = load_mod()
        mod.TASKS_DIR = Path(tmp)
        return mod.load_task_card(task_id)

    def test_bare_filename_found(self):
        with TemporaryDirectory() as tmp:
            write_card(Path(tmp), "TASK-901.yaml", "TASK-901")
            card, err = self._lookup(tmp, "TASK-901")
            self.assertIsNone(err)
            self.assertIsNotNone(card)
            self.assertEqual(card["id"], "TASK-901")

    def test_suffixed_filename_found_by_id_field(self):
        with TemporaryDirectory() as tmp:
            write_card(Path(tmp), "TASK-901-base-url-domain-error.yaml",
                       "TASK-901")
            card, err = self._lookup(tmp, "TASK-901")
            self.assertIsNone(err)
            self.assertIsNotNone(card)
            self.assertEqual(card["id"], "TASK-901")

    def test_filename_id_mismatch_not_matched(self):
        with TemporaryDirectory() as tmp:
            write_card(Path(tmp), "TASK-901-foo.yaml", "TASK-902")
            card, err = self._lookup(tmp, "TASK-901")
            self.assertIsNone(err)
            self.assertIsNone(card)

    def test_no_card_gives_none_none(self):
        with TemporaryDirectory() as tmp:
            card, err = self._lookup(tmp, "TASK-901")
            self.assertIsNone(err)
            self.assertIsNone(card)

    def test_duplicate_id_exposed_not_silent(self):
        with TemporaryDirectory() as tmp:
            write_card(Path(tmp), "TASK-901.yaml", "TASK-901")
            write_card(Path(tmp), "TASK-901-again.yaml", "TASK-901")
            card, err = self._lookup(tmp, "TASK-901")
            self.assertIsNone(card)
            self.assertIsNotNone(err)
            self.assertIn("TASK-901", err)


if __name__ == "__main__":
    unittest.main()
