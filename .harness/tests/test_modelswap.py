"""modelswap 会话覆盖测试（TASK-044）+ 退役缺席守卫（TASK-047）。

历史用例 TestSwapRestore/TestLock/TestMaybeRestore 断言的是 ADR-008/010
明令废止的"改全局配置实现模型切换"链——随 API 删除而转换为下方的
缺席守卫（回归锁：任何复活即红）。转换而非静默删除，四要件记录于
TASK-047 卡 notes 与 docs/testing/red/TASK-047/。"""
import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

MODELSWAP = (Path(__file__).resolve().parent.parent / "scripts" / "modelswap.py")
DISPATCH = (Path(__file__).resolve().parent.parent / "scripts" / "dispatch.py")
POLL = (Path(__file__).resolve().parent.parent / "scripts" / "poll.py")


def load_modelswap():
    spec = importlib.util.spec_from_file_location("harness_modelswap", MODELSWAP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_dispatch():
    spec = importlib.util.spec_from_file_location("harness_dispatch", DISPATCH)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(DISPATCH.parent))
    spec.loader.exec_module(mod)
    return mod


SETTINGS = """ui-onboarding:
  welcomeNoticeVersion: 2026-08-13.1
agent-default-model:
  provider: openrouter
  model: deepseek/deepseek-v4-flash-0731:free
llm-pi-ai:
  providers: {}
"""


class TestSplitModel(unittest.TestCase):
    def test_split_with_provider(self):
        mod = load_modelswap()
        self.assertEqual(
            mod.split_model("openrouter/a/b:free"), ("openrouter", "a/b:free"))

    def test_split_without_slash(self):
        mod = load_modelswap()
        self.assertEqual(mod.split_model("somemodel"), (None, "somemodel"))


class TestSessionOverride(unittest.TestCase):
    """TASK-044：会话覆盖构造器（评审报告 §7 机制的离线断言面）。"""

    def _base(self, tmp):
        sp = Path(tmp) / "settings.yaml"
        sp.write_text(SETTINGS, encoding="utf-8")
        return sp

    def test_copy_preserves_namespaces_and_swaps_selection(self):
        mod = load_modelswap()
        import hashlib
        import yaml
        with TemporaryDirectory() as tmp:
            sp = self._base(tmp)
            before = hashlib.sha256(sp.read_bytes()).hexdigest()
            tokens = mod.build_session_override(
                sp, Path(tmp) / "run1", "openrouter", "cohere/x:free")
            data = yaml.safe_load(
                (Path(tmp) / "run1" / "settings.yaml").read_text(
                    encoding="utf-8"))
            self.assertEqual(data["agent-default-model"],
                             {"provider": "openrouter", "model": "cohere/x:free"})
            self.assertIn("ui-onboarding", data)
            self.assertIn("llm-pi-ai", data)
            self.assertEqual(
                hashlib.sha256(sp.read_bytes()).hexdigest(), before)
            self.assertEqual(tokens[0], "--patch")

    def test_patch_redirects_settings_with_watch_false(self):
        mod = load_modelswap()
        with TemporaryDirectory() as tmp:
            sp = self._base(tmp)
            mod.build_session_override(sp, Path(tmp) / "r2", "p1", "m1")
            patch = (Path(tmp) / "r2" / "model.patch.yml").read_text(
                encoding="utf-8")
            self.assertIn("- id: settings", patch)
            self.assertIn("watch: false", patch)
            self.assertIn("settings.yaml", patch)

    def test_two_sessions_isolated_baseline_untouched(self):
        mod = load_modelswap()
        import hashlib
        import yaml
        with TemporaryDirectory() as tmp:
            sp = self._base(tmp)
            before = hashlib.sha256(sp.read_bytes()).hexdigest()
            mod.build_session_override(sp, Path(tmp) / "A", "prov-a",
                                       "model-a")
            mod.build_session_override(sp, Path(tmp) / "B", "prov-b",
                                       "model-b")
            a = yaml.safe_load((Path(tmp) / "A" / "settings.yaml").read_text(
                encoding="utf-8"))
            b = yaml.safe_load((Path(tmp) / "B" / "settings.yaml").read_text(
                encoding="utf-8"))
            self.assertEqual(a["agent-default-model"]["model"], "model-a")
            self.assertEqual(b["agent-default-model"]["model"], "model-b")
            self.assertEqual(
                hashlib.sha256(sp.read_bytes()).hexdigest(), before)


class TestRetiredChainAbsent(unittest.TestCase):
    """TASK-047 缺席守卫：废止链任何复活即红（ADR-008/010 回归锁）。"""

    RETIRED = ("swap_for_run", "restore", "acquire_lock", "release_lock",
               "maybe_restore", "verify_selection", "snapshot",
               "read_selection", "_all_records", "_bak_dir",
               "_prune_backups")

    def test_modelswap_api_absent(self):
        mod = load_modelswap()
        for name in self.RETIRED:
            self.assertFalse(hasattr(mod, name),
                             f"retired API resurrected: modelswap.{name}")

    def test_poll_finalize_absent_and_source_clean(self):
        poll = POLL.read_text(encoding="utf-8")
        self.assertNotIn("finalize_model_restore", poll)
        self.assertNotIn("maybe_restore", poll)
        self.assertNotIn("from modelswap import", poll)

    def test_dispatch_source_has_no_global_swap_call(self):
        src = DISPATCH.read_text(encoding="utf-8")
        self.assertNotIn("swap_for_run", src)
        self.assertNotIn("acquire_lock", src)
        self.assertIn("build_session_override", src)


class TestRunningCount(unittest.TestCase):
    def test_full_query_includes_pipeline(self):
        dispatch = load_dispatch()
        runs = importlib.util.spec_from_file_location(
            "harness_runs_ms", DISPATCH.parent / "runs.py")
        rm = importlib.util.module_from_spec(runs)
        runs.loader.exec_module(rm)
        with TemporaryDirectory() as tmp:
            st = rm.RunsStore(Path(tmp) / "RUNS.jsonl")
            st.append({"task_id": "T1", "attempt": 1})
            st.append({"task_id": "T2", "attempt": 1, "status": "spawning"})
            st.append({"task_id": "T3", "attempt": 1, "owner": "pipeline"})
            self.assertEqual(dispatch.running_count(st), 3)


if __name__ == "__main__":
    unittest.main()
