import importlib.util
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load(name):
    path = (Path(__file__).resolve().parent.parent / "scripts" / name)
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(*args, cwd):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr


class TestPoll(unittest.TestCase):
    def test_pid_alive_false_for_dead_pid(self):
        poll = load("poll.py")
        self.assertFalse(poll.pid_alive(999999))

    def test_scope_check_rejects_deny_write(self):
        poll = load("poll.py")
        card = {"scope": {"allow_write": ["mod/**"],
                          "deny_write": ["mod/secret.txt"]},
                "constraints": {"max_files_changed": 10,
                                "max_lines_changed": 300}}
        verdict, detail = poll.check_scope_and_scale(
            ["mod/a.txt", "mod/secret.txt"], {"mod/a.txt": 10}, card)
        self.assertEqual(verdict, "fail-scope")
        self.assertIn("mod/secret.txt", detail)

    def test_scope_check_rejects_overscale(self):
        poll = load("poll.py")
        card = {"scope": {"allow_write": ["mod/**"], "deny_write": []},
                "constraints": {"max_files_changed": 1,
                                "max_lines_changed": 300}}
        verdict, _ = poll.check_scope_and_scale(
            ["mod/a.txt", "mod/b.txt"], {"mod/a.txt": 10}, card)
        self.assertEqual(verdict, "fail-scale")

    def test_scope_check_passes_clean_change(self):
        poll = load("poll.py")
        card = {"scope": {"allow_write": ["mod/**"], "deny_write": []},
                "constraints": {"max_files_changed": 10,
                                "max_lines_changed": 300}}
        verdict, _ = poll.check_scope_and_scale(
            ["mod/a.txt"], {"mod/a.txt": 10}, card)
        self.assertEqual(verdict, "pass")

    def test_empty_change_is_not_pass(self):
        poll = load("poll.py")
        card = {"scope": {"allow_write": ["mod/**"], "deny_write": []},
                "constraints": {"max_files_changed": 10,
                                "max_lines_changed": 300}}
        # 零变更（含执行器在 worktree 内自行提交导致 porcelain 为空）绝不误判 pass
        verdict, _ = poll.check_scope_and_scale([], {}, card)
        self.assertNotEqual(verdict, "pass")

    def test_exitcode_missing_means_fail_exec(self):
        with TemporaryDirectory() as tmp:
            poll = load("poll.py")
            self.assertEqual(poll.read_exitcode(Path(tmp)), None)

    def test_sig_history_keep_constant(self):
        poll = load("poll.py")
        self.assertEqual(poll.SIG_HISTORY_KEEP, 20)

    def test_sig_history_capped_at_20(self):
        poll = load("poll.py")
        keep = poll.SIG_HISTORY_KEEP
        hist25 = [f"sig{i}" for i in range(25)]
        sig = "new-sig"
        capped = ((hist25 or []) + [sig])[-keep:]
        self.assertLessEqual(len(capped), 20)
        self.assertEqual(len(capped), 20)
        self.assertEqual(capped[-1], "new-sig")
        self.assertEqual(capped[0], "sig6")


if __name__ == "__main__":
    unittest.main()
