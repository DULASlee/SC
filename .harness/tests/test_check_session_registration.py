"""TASK-042/045 + isolation-revision F1: worktree commit ownership gate
(hook engine) tests.

Fixture roots get a copy of the real scripts dir so the hook's
git-common-dir-anchored import of ownership.py resolves (same layout as
a merged main tree)."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".harness" / "scripts"


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def load_hook():
    p = ROOT / "docs" / "ai-workspace" / "hooks" / "check_session_registration.py"
    spec = importlib.util.spec_from_file_location(
        "check_session_registration", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_repo(tmp):
    root = Path(tmp)
    git("init", cwd=root)
    git("config", "user.email", "t@t", cwd=root)
    git("config", "user.name", "t", cwd=root)
    (root / ".harness" / "scripts").mkdir(parents=True)
    shutil.copytree(SCRIPTS, root / ".harness" / "scripts", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    (root / "a.txt").write_text("a", encoding="utf-8")
    git("add", "-A", cwd=root)
    git("commit", "-m", "init", cwd=root)
    return root


def make_worktree(root, name):
    wt = root / ".harness" / "worktrees" / name
    wt.mkdir(parents=True)
    r = git("worktree", "add", "-B", f"feat/{name}", str(wt), cwd=root)
    assert r.returncode == 0, r.stderr
    return wt


def write_claim(root, task, session, wt):
    d = root / ".harness" / "runs" / "ownership"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{task}.json").write_text(json.dumps({
        "task_id": task, "owner_session_id": session,
        "owner_worktree": str(Path(wt).resolve()).replace("\\", "/"),
        "state": "claimed"}), encoding="utf-8")


class TestOwnershipGate(unittest.TestCase):
    def test_main_tree_always_passes(self):
        eng = load_hook()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            ok, msg = eng.check(root, root, root / ".harness" / "runs")
            self.assertTrue(ok, msg)

    def test_unclaimed_worktree_fails(self):
        eng = load_hook()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wt = make_worktree(root, "TASK-901")
            ok, msg = eng.check(wt, root, root / ".harness" / "runs")
            self.assertFalse(ok)
            self.assertIn("ownership", msg)

    def test_claimed_worktree_passes(self):
        eng = load_hook()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wt = make_worktree(root, "TASK-901")
            write_claim(root, "TASK-901", "manual:t", wt)
            ok, msg = eng.check(wt, root, root / ".harness" / "runs")
            self.assertTrue(ok, msg)

    def test_other_worktrees_claim_does_not_leak(self):
        """V5/V6 单元面：别的 worktree 有主 ≠ 本 worktree 有主。"""
        eng = load_hook()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wtA = make_worktree(root, "TA")
            wtB = make_worktree(root, "TB")
            write_claim(root, "TA", "manual:a", wtA)
            ok, _ = eng.check(wtB, root, root / ".harness" / "runs")
            self.assertFalse(ok)

    def test_released_claim_gates_again(self):
        eng = load_hook()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wt = make_worktree(root, "TASK-901")
            write_claim(root, "TASK-901", "manual:t", wt)
            f = root / ".harness" / "runs" / "ownership" / "TASK-901.json"
            data = json.loads(f.read_text(encoding="utf-8"))
            data["state"] = "released"
            f.write_text(json.dumps(data), encoding="utf-8")
            ok, _ = eng.check(wt, root, root / ".harness" / "runs")
            self.assertFalse(ok)

    def test_path_case_normalization(self):
        eng = load_hook()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wt = make_worktree(root, "TASK-901")
            d = root / ".harness" / "runs" / "ownership"
            d.mkdir(parents=True, exist_ok=True)
            (d / "TASK-901.json").write_text(json.dumps({
                "task_id": "TASK-901", "owner_session_id": "manual:t",
                "owner_worktree": str(Path(wt).resolve())
                .replace("\\", "/").upper(),
                "state": "claimed"}), encoding="utf-8")
            ok, msg = eng.check(wt, root, root / ".harness" / "runs")
            self.assertTrue(ok, msg)

    def test_identity_match_verified(self):
        """F1: committer == owner -> pass with identity verified."""
        eng = load_hook()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wt = make_worktree(root, "TASK-901")
            write_claim(root, "TASK-901", "manual:t", wt)
            old = os.environ.get("HARNESS_SESSION_ID")
            os.environ["HARNESS_SESSION_ID"] = "manual:t"
            try:
                ok, msg = eng.check(wt, root, root / ".harness" / "runs")
            finally:
                if old is None:
                    del os.environ["HARNESS_SESSION_ID"]
                else:
                    os.environ["HARNESS_SESSION_ID"] = old
            self.assertTrue(ok, msg)
            self.assertIn("identity verified", msg)

    def test_identity_mismatch_warns_in_transition(self):
        """F1 transition: mismatch without strict -> pass with WARN."""
        eng = load_hook()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wt = make_worktree(root, "TASK-901")
            write_claim(root, "TASK-901", "manual:t", wt)
            old = os.environ.get("HARNESS_SESSION_ID")
            os.environ["HARNESS_SESSION_ID"] = "manual:intruder"
            try:
                ok, msg = eng.check(wt, root, root / ".harness" / "runs")
            finally:
                if old is None:
                    del os.environ["HARNESS_SESSION_ID"]
                else:
                    os.environ["HARNESS_SESSION_ID"] = old
            self.assertTrue(ok, msg)
            self.assertIn("WARN", msg)

    def test_identity_mismatch_rejected_in_strict(self):
        """F1 target: mismatch with strict -> FAIL."""
        eng = load_hook()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wt = make_worktree(root, "TASK-901")
            write_claim(root, "TASK-901", "manual:t", wt)
            old_sid = os.environ.get("HARNESS_SESSION_ID")
            old_strict = os.environ.get("HARNESS_STRICT_IDENTITY")
            os.environ["HARNESS_SESSION_ID"] = "manual:intruder"
            os.environ["HARNESS_STRICT_IDENTITY"] = "1"
            try:
                ok, msg = eng.check(wt, root, root / ".harness" / "runs")
            finally:
                if old_sid is None:
                    del os.environ["HARNESS_SESSION_ID"]
                else:
                    os.environ["HARNESS_SESSION_ID"] = old_sid
                if old_strict is None:
                    del os.environ["HARNESS_STRICT_IDENTITY"]
                else:
                    os.environ["HARNESS_STRICT_IDENTITY"] = old_strict
            self.assertFalse(ok, msg)
            self.assertIn("mismatch", msg)

    def test_identity_absent_rejected_in_strict(self):
        """F1 target: no identity with strict -> FAIL."""
        eng = load_hook()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wt = make_worktree(root, "TASK-901")
            write_claim(root, "TASK-901", "manual:t", wt)
            old_sid = os.environ.get("HARNESS_SESSION_ID")
            old_strict = os.environ.get("HARNESS_STRICT_IDENTITY")
            os.environ.pop("HARNESS_SESSION_ID", None)
            os.environ["HARNESS_STRICT_IDENTITY"] = "1"
            try:
                ok, msg = eng.check(wt, root, root / ".harness" / "runs")
            finally:
                if old_sid is not None:
                    os.environ["HARNESS_SESSION_ID"] = old_sid
                if old_strict is None:
                    del os.environ["HARNESS_STRICT_IDENTITY"]
                else:
                    os.environ["HARNESS_STRICT_IDENTITY"] = old_strict
            self.assertFalse(ok, msg)

    def test_main_tree_bookkeeping_with_trail_passes(self):
        """F2 M1: card file + ownership trail -> pass."""
        eng = load_hook()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wt = make_worktree(root, "TASK-901")
            write_claim(root, "TASK-901", "manual:t", wt)
            staged = [".harness/tasks/active/TASK-901.yaml"]
            ok, msg = eng.check(root, root, root / ".harness" / "runs",
                                staged)
            self.assertTrue(ok, msg)
            self.assertIn("trail", msg)

    def test_main_tree_bookkeeping_without_trail_strict_fails(self):
        """F2 M4: card file, no trail, strict -> FAIL."""
        eng = load_hook()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            staged = [".harness/tasks/active/TASK-999.yaml"]
            old_strict = os.environ.get("HARNESS_STRICT_IDENTITY")
            os.environ["HARNESS_STRICT_IDENTITY"] = "1"
            try:
                ok, msg = eng.check(root, root,
                                    root / ".harness" / "runs", staged)
            finally:
                if old_strict is None:
                    del os.environ["HARNESS_STRICT_IDENTITY"]
                else:
                    os.environ["HARNESS_STRICT_IDENTITY"] = old_strict
            self.assertFalse(ok, msg)

    def test_main_tree_active_session_passes(self):
        """F2 M2: identity owns a claimed task -> pass (any files)."""
        eng = load_hook()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wt = make_worktree(root, "TASK-901")
            write_claim(root, "TASK-901", "manual:t", wt)
            old_sid = os.environ.get("HARNESS_SESSION_ID")
            os.environ["HARNESS_SESSION_ID"] = "manual:t"
            try:
                ok, msg = eng.check(root, root, root / ".harness" / "runs",
                                    ["src/Biz.cs"])
            finally:
                if old_sid is None:
                    del os.environ["HARNESS_SESSION_ID"]
                else:
                    os.environ["HARNESS_SESSION_ID"] = old_sid
            self.assertTrue(ok, msg)
            self.assertIn("active session", msg)

    def test_main_tree_unknown_strict_fails(self):
        """F2 M4: unknown identity, no trail, strict -> FAIL."""
        eng = load_hook()
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            old_sid = os.environ.get("HARNESS_SESSION_ID")
            old_strict = os.environ.get("HARNESS_STRICT_IDENTITY")
            os.environ["HARNESS_SESSION_ID"] = "manual:stranger"
            os.environ["HARNESS_STRICT_IDENTITY"] = "1"
            try:
                ok, msg = eng.check(root, root, root / ".harness" / "runs",
                                    ["src/Biz.cs"])
            finally:
                if old_sid is None:
                    del os.environ["HARNESS_SESSION_ID"]
                else:
                    os.environ["HARNESS_SESSION_ID"] = old_sid
                if old_strict is None:
                    del os.environ["HARNESS_STRICT_IDENTITY"]
                else:
                    os.environ["HARNESS_STRICT_IDENTITY"] = old_strict
            self.assertFalse(ok, msg)


if __name__ == "__main__":
    unittest.main()
