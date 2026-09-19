import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_run_exec():
    path = Path(__file__).resolve().parent.parent / "scripts" / "run-exec.py"
    spec = importlib.util.spec_from_file_location("harness_run_exec", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestRunExec(unittest.TestCase):
    def test_run_exec_module_has_main(self):
        mod = load_run_exec()
        self.assertTrue(callable(mod.main))

    def test_success_command_writes_exitcode_zero(self):
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            code = subprocess.run(
                [sys.executable, str(
                    Path(__file__).resolve().parent.parent
                    / "scripts" / "run-exec.py"),
                 "--run-dir", str(run_dir), "--",
                 sys.executable, "-c", "print('hi-exec')"],
                capture_output=True, text=True, encoding="utf-8",
            ).returncode
            self.assertEqual(code, 0)
            self.assertEqual(
                (run_dir / "exitcode.txt").read_text(encoding="utf-8").strip(), "0")
            self.assertIn("hi-exec",
                          (run_dir / "stdout.log").read_text(encoding="utf-8"))

    def test_failed_command_writes_nonzero_exitcode(self):
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            subprocess.run(
                [sys.executable, str(
                    Path(__file__).resolve().parent.parent
                    / "scripts" / "run-exec.py"),
                 "--run-dir", str(run_dir), "--",
                 sys.executable, "-c", "import sys; sys.exit(3)"],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(
                (run_dir / "exitcode.txt").read_text(encoding="utf-8").strip(), "3")

    def test_windows_cmd_shim_real_behavior(self):
        """真 Windows 行为用例：TemporaryDirectory 建 probe.cmd，经 run-exec 拉起。"""
        if os.name != "nt":
            self.skipTest("Windows-only cmd shim test")
        with TemporaryDirectory() as tmp:
            probe = Path(tmp) / "probe.cmd"
            probe.write_text("@echo hello-cmd\n", encoding="utf-8")
            run_dir = Path(tmp) / "run"
            code = subprocess.run(
                [sys.executable, str(
                    Path(__file__).resolve().parent.parent
                    / "scripts" / "run-exec.py"),
                 "--run-dir", str(run_dir), "--",
                 str(probe)],
                capture_output=True, text=True, encoding="utf-8",
            ).returncode
            self.assertEqual(code, 0)
            self.assertEqual(
                (run_dir / "exitcode.txt").read_text(encoding="utf-8").strip(), "0")
            self.assertIn("hello-cmd",
                          (run_dir / "stdout.log").read_text(encoding="utf-8"))

    def test_direct_python_launch_no_regression(self):
        """sys.executable 直拉用例（防回归）：.exe/可直拉路径不受 shim 改道影响。"""
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            code = subprocess.run(
                [sys.executable, str(
                    Path(__file__).resolve().parent.parent
                    / "scripts" / "run-exec.py"),
                 "--run-dir", str(run_dir), "--",
                 sys.executable, "-c", "print('direct-ok')"],
                capture_output=True, text=True, encoding="utf-8",
            ).returncode
            self.assertEqual(code, 0)
            self.assertEqual(
                (run_dir / "exitcode.txt").read_text(encoding="utf-8").strip(), "0")
            self.assertIn("direct-ok",
                          (run_dir / "stdout.log").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
