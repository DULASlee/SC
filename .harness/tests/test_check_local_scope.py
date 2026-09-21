"""TASK-048: check-local-scope 并行正确性测试（主树锚定 + ownership 解析 +
多卡并集模式——旧行为在这些用例上为红）。"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".harness" / "scripts"

CARD = """id: {tid}
title: "fixture {tid}"
status: {status}
created: 2026-09-21T00:00:00Z
created_by: architect
approver: architect
scope:
  allow_write:
    - {allow}
  deny_write:
    - secret/**
acceptance_tests:
  - .harness/tests/test_check_local_scope.py
done_when:
  - "ci: build"
"""


def git(*a, cwd):
    return subprocess.run(["git", *a], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def make_repo(tmp):
    root = Path(tmp)
    for d in (".harness/scripts", ".harness/tasks/active",
              ".harness/runs/ownership", ".harness/worktrees", "mod",
              "other", "secret"):
        (root / d).mkdir(parents=True)
    shutil.copytree(SCRIPTS, root / ".harness" / "scripts",
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    (root / "mod" / "a.txt").write_text("a", encoding="utf-8")
    (root / "other" / "b.txt").write_text("b", encoding="utf-8")
    (root / "secret" / "s.txt").write_text("s", encoding="utf-8")
    git("init", cwd=root)
    git("config", "user.email", "t@t", cwd=root)
    git("config", "user.name", "t", cwd=root)
    git("add", "-A", cwd=root)
    git("commit", "-m", "init", cwd=root)
    return root


def write_card(root, tid, allow, status="ready"):
    (root / ".harness" / "tasks" / "active" / f"{tid}.yaml").write_text(
        CARD.format(tid=tid, allow=allow, status=status), encoding="utf-8")


def stage(root, *paths):
    for p in paths:
        f = root / p
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "a", encoding="utf-8") as fh:
            fh.write("x\n")
        git("add", p, cwd=root)


def run_checker(cwd, *args):
    script = Path(cwd) / ".harness" / "scripts" / "check-local-scope.py"
    if not script.exists():
        script = SCRIPTS / "check-local-scope.py"
    return subprocess.run([sys.executable, str(script), *args], cwd=str(cwd),
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def make_worktree(root, tid):
    wt = root / ".harness" / "worktrees" / tid
    r = git("worktree", "add", "-B", f"feat/{tid}", str(wt), cwd=root)
    assert r.returncode == 0, r.stderr
    return wt


def claim(root, tid, wt):
    rec = {"task_id": tid, "owner_session_id": f"manual:{tid}",
           "owner_worktree": str(Path(wt).resolve()).replace("\\", "/"),
           "state": "claimed", "claimed_at": "2026-09-21T03:00:00+00:00",
           "released_at": None}
    (root / ".harness" / "runs" / "ownership" / f"{tid}.json").write_text(
        json.dumps(rec), encoding="utf-8")


class TestCheckLocalScope(unittest.TestCase):
    def test_main_tree_single_card_still_checks(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            write_card(root, "TASK-901", "mod/**")
            git("add", ".harness/tasks/active/TASK-901.yaml", cwd=root)
            git("commit", "-m", "card", cwd=root)
            stage(root, "mod/a.txt")
            r = run_checker(root)
            self.assertEqual(r.returncode, 0, r.stdout)
            stage(root, "other/b.txt")
            r2 = run_checker(root)
            self.assertNotEqual(r2.returncode, 0)
            self.assertIn("OUT-OF-SCOPE", r2.stdout)

    def test_main_tree_multi_cards_union_not_skipped(self):
        """缺陷 C：多活跃卡时旧行为 WARN+skip（红）；新行为逐文件并集判定。"""
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            write_card(root, "TASK-901", "mod/**")
            write_card(root, "TASK-902", "other/**")
            git("add", ".harness/tasks/active", cwd=root)
            git("commit", "-m", "cards", cwd=root)
            stage(root, "mod/a.txt", "other/b.txt")
            r = run_checker(root)
            self.assertEqual(r.returncode, 0, r.stdout)
            stage(root, "uncovered/u.txt")
            r2 = run_checker(root)
            self.assertNotEqual(r2.returncode, 0,
                                "uncovered file must FAIL in union mode")
            self.assertIn("uncovered/u.txt", r2.stdout)

    def test_worktree_uses_ownership_card(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            write_card(root, "TASK-901", "mod/**")
            git("add", ".harness/tasks/active/TASK-901.yaml", cwd=root)
            git("commit", "-m", "card", cwd=root)
            wt = make_worktree(root, "TASK-901")
            claim(root, "TASK-901", wt)
            stage(wt, "mod/x.txt")
            r = run_checker(wt)
            self.assertEqual(r.returncode, 0, r.stdout)
            stage(wt, "other/y.txt")
            r2 = run_checker(wt)
            self.assertNotEqual(r2.returncode, 0,
                                "worktree out-of-scope must FAIL (not skip)")
            self.assertIn("TASK-901", r2.stdout)

    def test_worktree_without_ownership_skips_with_note(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            wt = make_worktree(root, "TASK-999")
            stage(wt, "mod/x.txt")
            r = run_checker(wt)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("no ownership", r.stdout.lower())

    def test_explicit_task_id_wins(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            write_card(root, "TASK-901", "mod/**")
            write_card(root, "TASK-902", "other/**")
            git("add", ".harness/tasks/active", cwd=root)
            git("commit", "-m", "cards", cwd=root)
            stage(root, "other/b.txt")
            r = run_checker(root, "--task-id", "TASK-902")
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_no_active_cards_warns_skip(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            stage(root, "mod/a.txt")
            r = run_checker(root)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("no active task", r.stdout.lower())


if __name__ == "__main__":
    unittest.main()
