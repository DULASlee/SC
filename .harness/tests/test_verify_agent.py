"""P2 verify-agent tests: contract, red/green, isolation."""
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT = (Path(__file__).resolve().parent.parent / "scripts"
          / "verify-agent.py")


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace")


def make_work(tmp: str, files: dict) -> str:
    root = Path(tmp) / "work"
    root.mkdir()
    for name, content in files.items():
        (root / name).write_text(content, encoding="utf-8")
    crit = Path(tmp) / "criteria.md"
    crit.write_text("must contain done.txt\n", encoding="utf-8")
    return str(root), str(crit)


class TestVerifyAgent(unittest.TestCase):
    def test_green_passes(self):
        with TemporaryDirectory() as tmp:
            w, c = make_work(tmp, {"done.txt": "x\n"})
            out = str(Path(tmp) / "v.md")
            r = run("--work", w, "--criteria", c, "--allow", "done.txt",
                    "--out", out)
            self.assertEqual(r.returncode, 0)
            self.assertIn("verdict: PASS", Path(out).read_text(
                encoding="utf-8"))

    def test_red_outside_allow(self):
        with TemporaryDirectory() as tmp:
            w, c = make_work(tmp, {"done.txt": "x\n", "secret.txt": "y\n"})
            out = str(Path(tmp) / "v.md")
            r = run("--work", w, "--criteria", c, "--allow", "done.txt",
                    "--out", out)
            self.assertEqual(r.returncode, 0)
            body = Path(out).read_text(encoding="utf-8")
            self.assertIn("verdict: FAIL", body)
            self.assertIn("secret.txt", body)

    def test_empty_criteria_fails(self):
        with TemporaryDirectory() as tmp:
            w, _ = make_work(tmp, {"done.txt": "x\n"})
            crit = str(Path(tmp) / "empty.md")
            Path(crit).write_text("\n", encoding="utf-8")
            out = str(Path(tmp) / "v.md")
            r = run("--work", w, "--criteria", crit, "--allow", "done.txt",
                    "--out", out)
            self.assertEqual(r.returncode, 0)
            self.assertIn("verdict: FAIL", Path(out).read_text(
                encoding="utf-8"))

    def test_isolation_no_worker_session_input(self):
        import subprocess as sp
        r = sp.run([sys.executable, str(SCRIPT), "--help"],
                   capture_output=True, text=True, encoding="utf-8")
        for banned in ("--worker-session", "--context", "--reasoning"):
            self.assertNotIn(banned, r.stdout)

    def test_bad_args_exit_2(self):
        r = run("--work", "no-such-dir", "--criteria", "nope",
                "--out", "x.md")
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
