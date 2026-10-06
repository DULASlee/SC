"""isolation-revision F4: local scope resolves card by staged files.

0/>=2 ready cards no longer silently skip: exactly one covering card is
auto-used, otherwise FAIL (unless HARNESS_LENIENT_SCOPE=1)."""
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-local-scope.py"


def git(*args, cwd):
    p = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    assert p.returncode == 0, (args, p.stderr)


CARD = """id: {tid}
status: ready
approver: boss
scope:
  allow_write: [{allow}]
  deny_write: []
"""


def make_repo(tmp, cards):
    root = Path(tmp)
    git("init", cwd=root)
    git("config", "user.email", "t@t", cwd=root)
    git("config", "user.name", "t", cwd=root)
    d = root / ".harness" / "tasks" / "active"
    d.mkdir(parents=True)
    for tid, allow in cards:
        (d / f"{tid}.yaml").write_text(
            CARD.format(tid=tid, allow=allow), encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "A.cs").write_text("a", encoding="utf-8")
    (root / "src" / "B.cs").write_text("b", encoding="utf-8")
    git("add", "-A", cwd=root)
    git("commit", "-m", "init", cwd=root)
    # dirty the tree so later `git add` stages something
    (root / "src" / "A.cs").write_text("a2", encoding="utf-8")
    (root / "src" / "B.cs").write_text("b2", encoding="utf-8")
    (root / "other.txt").write_text("x", encoding="utf-8")
    return root


def run_script(root, *args):
    env = dict(os.environ)
    env.pop("HARNESS_LENIENT_SCOPE", None)
    env["HARNESS_TASKS_DIR"] = str(root / ".harness" / "tasks" / "active")
    p = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(root),
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stdout + p.stderr


class TestLocalScopeResolution(unittest.TestCase):
    def test_unique_covering_card_passes(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp, [("TASK-001", '"src/A.cs"'),
                                   ("TASK-002", '"src/B.cs"')])
            git("add", "src/A.cs", cwd=root)
            rc, out = run_script(root)
            self.assertEqual(rc, 0, out)
            self.assertIn("TASK-001", out)

    def test_ambiguous_cards_fail(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp, [("TASK-001", '"src/*"'),
                                   ("TASK-002", '"src/*"')])
            git("add", "src/A.cs", cwd=root)
            rc, out = run_script(root)
            self.assertEqual(rc, 1, out)

    def test_no_covering_card_fails(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp, [("TASK-001", '"src/A.cs"'),
                                   ("TASK-002", '"src/B.cs"')])
            (root / "other.txt").write_text("x", encoding="utf-8")
            git("add", "other.txt", cwd=root)
            rc, out = run_script(root)
            self.assertEqual(rc, 1, out)

    def test_lenient_keeps_old_skip(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(tmp, [("TASK-001", '"src/*"'),
                                   ("TASK-002", '"src/*"')])
            git("add", "src/A.cs", cwd=root)
            env = dict(os.environ, HARNESS_LENIENT_SCOPE="1")
            env["HARNESS_TASKS_DIR"] = str(
                root / ".harness" / "tasks" / "active")
            p = subprocess.run([sys.executable, str(SCRIPT)], cwd=str(root),
                               capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
