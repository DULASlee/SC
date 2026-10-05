"""isolation-revision F9: regression guards.

1. verify-all --approve-protected-paths must not NameError (missing
   `import os` once broke this path); runs with stubbed executor so the
   test never touches toolchains, writing only to a temp VERIFY dir.
2. .gitattributes must keep text=auto + key eol rules (line-ending
   landmine made every fresh worktree dirty)."""
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

VERIFY_ALL = (Path(__file__).resolve().parent.parent / "scripts"
              / "verify-all.py")
ROOT = Path(__file__).resolve().parents[2]


def load_verify_all():
    spec = importlib.util.spec_from_file_location("harness_verify_all",
                                                  VERIFY_ALL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestVerifyAllFlagPath(unittest.TestCase):
    def test_approve_flag_does_not_nameerror(self):
        mod = load_verify_all()
        with TemporaryDirectory() as tmp:
            mod.VERIFY_DIR = Path(tmp)
            mod.run = lambda *a, **k: (1, "", "stubbed")
            old_argv = sys.argv
            sys.argv = ["verify-all.py", "--task-id", "TASK-900",
                        "--approve-protected-paths"]
            try:
                rc = mod.main()
            finally:
                sys.argv = old_argv
                os.environ.pop("SKIP_PROTECTED_CHECK", None)
            outs = list(Path(tmp).glob("VERIFY-TASK-900-*.md"))
            self.assertEqual(rc, 1)  # stubbed checks fail -> 未通过
            self.assertEqual(len(outs), 1)


class TestLineEndingGuard(unittest.TestCase):
    def test_gitattributes_has_auto_and_key_rules(self):
        p = ROOT / ".gitattributes"
        self.assertTrue(p.is_file(), ".gitattributes missing")
        text = p.read_text(encoding="utf-8")
        for needle in ("* text=auto", ".githooks/** text eol=lf",
                       "*.py text eol=lf", "*.yaml text eol=lf"):
            self.assertIn(needle, text, needle)


if __name__ == "__main__":
    unittest.main()
