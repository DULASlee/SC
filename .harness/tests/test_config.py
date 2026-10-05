import unittest
from pathlib import Path

import yaml

HARNESS_DIR = Path(__file__).resolve().parent.parent

REQUIRED_KEYS = {
    "model", "executor_argv", "concurrency",
    "max_retries", "max_tasks_per_run", "worktree_root", "runs_dir",
}


class TestDispatchConfig(unittest.TestCase):
    def test_config_has_all_required_keys(self):
        cfg = yaml.safe_load(
            (HARNESS_DIR / "dispatch.yaml").read_text(encoding="utf-8"))
        self.assertTrue(REQUIRED_KEYS.issubset(cfg.keys()), cfg.keys())

    def test_executor_argv_has_prompt_placeholder(self):
        cfg = yaml.safe_load(
            (HARNESS_DIR / "dispatch.yaml").read_text(encoding="utf-8"))
        self.assertIn("{prompt}", cfg["executor_argv"])

    def test_concurrency_is_small(self):
        cfg = yaml.safe_load(
            (HARNESS_DIR / "dispatch.yaml").read_text(encoding="utf-8"))
        self.assertLessEqual(cfg["concurrency"], 5)
        self.assertGreaterEqual(cfg["max_retries"], 1)

    def test_phase2_keys_present(self):
        cfg = yaml.safe_load(
            (HARNESS_DIR / "dispatch.yaml").read_text(encoding="utf-8"))
        for k in ("model_fallbacks", "loop_interval_seconds",
                  "prompt_budget", "pr_enabled", "skills_dir",
                  "dsh_settings"):
            self.assertIn(k, cfg, k)

    def test_phase2_key_shapes(self):
        cfg = yaml.safe_load(
            (HARNESS_DIR / "dispatch.yaml").read_text(encoding="utf-8"))
        self.assertIsInstance(cfg["model_fallbacks"], list)
        self.assertGreaterEqual(cfg["loop_interval_seconds"], 30)
        self.assertIsInstance(cfg["pr_enabled"], bool)


if __name__ == "__main__":
    unittest.main()
