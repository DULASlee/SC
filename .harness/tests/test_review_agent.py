"""P3: review-agent unit tests (output contract, not live PRs)."""
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT = (Path(__file__).resolve().parent.parent / "scripts"
          / "review-agent.py")


def load():
    spec = importlib.util.spec_from_file_location("harness_review_agent",
                                                  SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestReviewAgentContract(unittest.TestCase):
    def test_vague_regex_flags_outline_words(self):
        mod = load()
        self.assertTrue(mod.VAGUE_RE.search("确认无新增红"))
        self.assertFalse(mod.VAGUE_RE.search("exit code is 0"))

    def test_report_shape(self):
        import re
        src = SCRIPT.read_text(encoding="utf-8")
        for needle in ("human sign-off", "R1 scope-agreement",
                       "R2 tests-alongside", "R3 evidence-alongside",
                       "R4 no-outline-vagueness",
                       "severity scale", "always 0"):
            self.assertIn(needle, src, needle)

    def test_exit_zero_contract(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("return 0", src)


if __name__ == "__main__":
    unittest.main()
