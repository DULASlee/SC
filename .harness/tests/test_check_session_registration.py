"""TASK-042 red tests: worktree commit registration gate (hook engine)."""
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
    # hook engine lives in the single-source hooks dir (AGENTS rule 6,
    # same convention as check_approval.py)
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "docs" / "ai-workspace" / "hooks" / f"{name}.py")
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


class TestCheckRegistration(unittest.TestCase):
    def _engine(self):
        return load_script("check_session_registration")

    def test_main_tree_always_passes(self):
        eng = self._engine()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            ok, msg = eng.check(Path(root), Path(root),
                                Path(root) / ".harness" / "runs" / "sessions")
            self.assertTrue(ok, msg)

    def test_unregistered_worktree_fails(self):
        eng = self._engine()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wt = Path(root) / ".harness" / "worktrees" / "TASK-901"
            wt.mkdir(parents=True)
            git("worktree", "add", "-B", "feat/TASK-901", str(wt), cwd=root)
            sessions = Path(root) / ".harness" / "runs" / "sessions"
            ok, msg = eng.check(wt.resolve(), Path(root).resolve(), sessions)
            self.assertFalse(ok)
            self.assertIn("registration", msg)

    def test_active_registration_passes(self):
        eng = self._engine()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wt = Path(root) / ".harness" / "worktrees" / "TASK-901"
            wt.mkdir(parents=True)
            git("worktree", "add", "-B", "feat/TASK-901", str(wt), cwd=root)
            sessions = Path(root) / ".harness" / "runs" / "sessions"
            sessions.mkdir(parents=True)
            reg = {"task_id": "TASK-901",
                   "worktree": str(wt.resolve()).replace("\\", "/"),
                   "branch": "feat/TASK-901", "session_id": "TASK-901.1",
                   "owner": "t", "status": "active"}
            (sessions / "TASK-901.json").write_text(
                json.dumps(reg), encoding="utf-8")
            ok, msg = eng.check(wt.resolve(), Path(root).resolve(), sessions)
            self.assertTrue(ok, msg)

    def test_released_registration_fails(self):
        eng = self._engine()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wt = Path(root) / ".harness" / "worktrees" / "TASK-901"
            wt.mkdir(parents=True)
            git("worktree", "add", "-B", "feat/TASK-901", str(wt), cwd=root)
            sessions = Path(root) / ".harness" / "runs" / "sessions"
            sessions.mkdir(parents=True)
            reg = {"task_id": "TASK-901",
                   "worktree": str(wt.resolve()).replace("\\", "/"),
                   "branch": "feat/TASK-901", "session_id": "TASK-901.1",
                   "owner": "t", "status": "released"}
            (sessions / "TASK-901.json").write_text(
                json.dumps(reg), encoding="utf-8")
            ok, _ = eng.check(wt.resolve(), Path(root).resolve(), sessions)
            self.assertFalse(ok)

    def test_path_normalization_windows_case(self):
        eng = self._engine()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wt = Path(root) / ".harness" / "worktrees" / "TASK-901"
            wt.mkdir(parents=True)
            git("worktree", "add", "-B", "feat/TASK-901", str(wt), cwd=root)
            sessions = Path(root) / ".harness" / "runs" / "sessions"
            sessions.mkdir(parents=True)
            upper = str(wt.resolve()).replace("\\", "/").upper()
            reg = {"task_id": "TASK-901", "worktree": upper,
                   "branch": "feat/TASK-901", "session_id": "TASK-901.1",
                   "owner": "t", "status": "active"}
            (sessions / "TASK-901.json").write_text(
                json.dumps(reg), encoding="utf-8")
            ok, msg = eng.check(wt.resolve(), Path(root).resolve(), sessions)
            self.assertTrue(ok, msg)


if __name__ == "__main__":
    unittest.main()
