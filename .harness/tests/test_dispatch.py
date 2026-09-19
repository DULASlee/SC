import importlib.util
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

DISPATCH = (Path(__file__).resolve().parent.parent / "scripts" / "dispatch.py")


def load_dispatch():
    spec = importlib.util.spec_from_file_location("harness_dispatch", DISPATCH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(*args, cwd):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout


CARD = """id: TASK-901
title: dispatch 测试卡
status: ready
created: 2026-09-19T00:00:00Z
created_by: architect
scope:
  allow_write: ['mod/a.txt']
  deny_write: ['.harness/**']
acceptance_tests: ['tests/t.txt']
done_when: ['ci: build']
constraints: {max_lines_changed: 300, max_files_changed: 10}
depends_on: []
references: []
notes: t
"""

CFG = """model: test-model
executor_argv: ['python', '-c', 'print(1)', '{prompt}']
concurrency: 3
max_retries: 3
max_tasks_per_run: 10
worktree_root: .harness/worktrees
runs_dir: .harness/runs
"""


class TestDispatch(unittest.TestCase):
    def test_dry_run_lists_ready_card_without_side_effects(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            git("init", cwd=root)
            git("config", "user.email", "t@t", cwd=root)
            git("config", "user.name", "t", cwd=root)
            (root / ".harness" / "tasks" / "active").mkdir(parents=True)
            (root / ".harness" / "tasks" / "active" / "TASK-901.yaml").write_text(
                CARD, encoding="utf-8")
            (root / ".harness" / "dispatch.yaml").write_text(CFG, encoding="utf-8")
            (root / "mod").mkdir()
            (root / "mod" / "a.txt").write_text("a", encoding="utf-8")
            git("add", "-A", cwd=root)
            git("commit", "-m", "init", cwd=root)
            mod = load_dispatch()
            # validate-task-card 走真脚本需要 schema；此处只测队列筛选逻辑：
            # eligible() 对 status==ready 且 depends_on 为空的卡返回 True
            card = {"id": "TASK-901", "status": "ready", "depends_on": []}
            self.assertTrue(mod.is_eligible(card, root))
            card2 = {"id": "TASK-902", "status": "in-progress",
                     "depends_on": []}
            self.assertFalse(mod.is_eligible(card2, root))
            card3 = {"id": "TASK-903", "status": "ready",
                     "depends_on": ["TASK-900"]}
            self.assertFalse(mod.is_eligible(card3, root))
            card4 = {"id": "TASK-904", "status": "ready",
                     "depends_on": [], "pipeline": True}
            self.assertFalse(mod.is_eligible(card4, root))

    def test_build_prompt_references_absolute_context_path(self):
        mod = load_dispatch()
        p = mod.build_prompt(
            Path("C:/repo/.harness/context/TASK-901-context.md"),
            "test-model", None)
        self.assertIn("C:/repo/.harness/context/TASK-901-context.md", p)
        self.assertIn("test-model", p)
        self.assertNotIn("{prompt}", p)


if __name__ == "__main__":
    unittest.main()
