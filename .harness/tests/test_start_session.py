"""TASK-042 red tests: start-session entry (L0 physical isolation)."""
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd),
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def load_script(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / ".harness" / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CARD = """id: TASK-901
title: "fixture card"
status: ready
created: 2026-09-20T00:00:00Z
created_by: architect
scope:
  allow_write:
    - mod/**
  deny_write:
    - .harness/**
acceptance_tests:
  - tests/x.cs
done_when:
  - "ci: build"
"""

CFG = """model: test-model
executor_argv: ['python', '-c', 'print(1)', '{prompt}']
concurrency: 3
max_retries: 3
max_tasks_per_run: 10
worktree_root: .harness/worktrees
runs_dir: .harness/runs
"""


def make_repo(tmp):
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
    return root


class TestStartSession(unittest.TestCase):
    def test_creates_worktree_branch_and_ownership_claim(self):
        ss = load_script("start-session")
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            reg = ss.create_session(root, "TASK-901", owner="tester",
                                    with_context=False, claim_card=False)
            self.assertTrue(Path(reg["owner_worktree"]).is_dir())
            self.assertEqual(reg["state"], "claimed")
            self.assertEqual(reg["owner_session_id"], "manual:tester")
            r = git("branch", "--list", "feat/TASK-901", cwd=root)
            self.assertIn("feat/TASK-901", r.stdout)
            path = Path(reg["registration_file"])
            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["task_id"], "TASK-901")

    def test_double_active_registration_refused(self):
        ss = load_script("start-session")
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            ss.create_session(root, "TASK-901", owner="a",
                              with_context=False, claim_card=False)
            with self.assertRaises(RuntimeError) as ctx:
                ss.create_session(root, "TASK-901", owner="b",
                                  with_context=False, claim_card=False)
            self.assertIn("already", str(ctx.exception).lower())

    def test_card_in_progress_refused(self):
        ss = load_script("start-session")
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            card_path = root / ".harness" / "tasks" / "active" / "TASK-901.yaml"
            card_path.write_text(CARD.replace("status: ready",
                                              "status: in-progress"),
                                 encoding="utf-8")
            git("add", "-A", cwd=root)
            git("commit", "-m", "claim", cwd=root)
            with self.assertRaises(RuntimeError):
                ss.create_session(root, "TASK-901", owner="a",
                                  with_context=False, claim_card=False)

    def test_same_session_reclaim_is_idempotent(self):
        """A3-2：同任务重试链复用同一 owner session（幂等刷新）。"""
        ss = load_script("start-session")
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            r1 = ss.create_session(root, "TASK-901", owner="a",
                                   with_context=False, claim_card=False)
            r2 = ss.create_session(root, "TASK-901", owner="a",
                                   with_context=False, claim_card=False)
            self.assertEqual(r1["owner_session_id"], r2["owner_session_id"])

    def test_release_allows_reacquire(self):
        ss = load_script("start-session")
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            reg = ss.create_session(root, "TASK-901", owner="a",
                                    with_context=False, claim_card=False)
            ss.release_session(root, "TASK-901", owner="a")
            reg2 = ss.create_session(root, "TASK-901", owner="b",
                                     with_context=False, claim_card=False)
            self.assertEqual(reg2["owner_session_id"], "manual:b")
            self.assertEqual(Path(reg2["owner_worktree"]),
                             Path(reg["owner_worktree"]))


if __name__ == "__main__":
    unittest.main()
