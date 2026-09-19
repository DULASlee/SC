import importlib.util
import shutil
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

MODELSWAP = (Path(__file__).resolve().parent.parent / "scripts" / "modelswap.py")
DISPATCH = (Path(__file__).resolve().parent.parent / "scripts" / "dispatch.py")


def load_modelswap():
    spec = importlib.util.spec_from_file_location("harness_modelswap", MODELSWAP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_dispatch():
    spec = importlib.util.spec_from_file_location("harness_dispatch", DISPATCH)
    mod = importlib.util.module_from_spec(spec)
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


class TestSwapRestore(unittest.TestCase):
    def test_swap_restore_roundtrip(self):
        mod = load_modelswap()
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            runs_dir.mkdir()
            sp = Path(tmp) / "settings.yaml"
            sp.write_text(SETTINGS, encoding="utf-8")
            prev = mod.swap_for_run(
                sp, "openrouter", "cohere/north-mini-code:free", runs_dir)
            self.assertEqual(
                prev, ("openrouter", "deepseek/deepseek-v4-flash-0731:free"))
            # 备份落在 runs_dir/modelswap-bak，不再污染 ~/.dsh/
            bak_dir = runs_dir / "modelswap-bak"
            self.assertTrue(bak_dir.is_dir())
            bak = list(bak_dir.glob("*.bak.*"))
            self.assertTrue(len(bak) >= 1, bak)
            import yaml
            data = yaml.safe_load(sp.read_text(encoding="utf-8"))
            self.assertEqual(data["agent-default-model"]["provider"], "openrouter")
            self.assertEqual(
                data["agent-default-model"]["model"], "cohere/north-mini-code:free")
            # 其他键保留
            self.assertIn("ui-onboarding", data)
            self.assertIn("llm-pi-ai", data)
            mod.restore(sp, prev[0], prev[1])
            data2 = yaml.safe_load(sp.read_text(encoding="utf-8"))
            self.assertEqual(data2["agent-default-model"]["provider"], "openrouter")
            self.assertEqual(
                data2["agent-default-model"]["model"],
                "deepseek/deepseek-v4-flash-0731:free")
            self.assertIn("ui-onboarding", data2)

    def test_swap_same_value_noop(self):
        mod = load_modelswap()
        with TemporaryDirectory() as tmp:
            sp = Path(tmp) / "settings.yaml"
            sp.write_text(SETTINGS, encoding="utf-8")
            ret = mod.swap_for_run(
                sp, "openrouter", "deepseek/deepseek-v4-flash-0731:free")
            self.assertIsNone(ret)

    def test_backup_prune_keeps_five(self):
        # swap 7 次 → 备份目录只剩最近 5 个
        mod = load_modelswap()
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            runs_dir.mkdir()
            sp = Path(tmp) / "settings.yaml"
            sp.write_text(SETTINGS, encoding="utf-8")
            for i in range(7):
                mod.swap_for_run(sp, "openrouter", f"cohere/model-{i}:free",
                                 runs_dir)
                time.sleep(0.02)  # 保证 mtime 可排序
            bak = list((runs_dir / "modelswap-bak").glob("*.bak.*"))
            self.assertEqual(len(bak), 5, bak)


class TestLock(unittest.TestCase):
    def test_lock_mutex(self):
        mod = load_modelswap()
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            mod.acquire_lock(runs_dir, timeout=5)
            try:
                with self.assertRaises(TimeoutError):
                    mod.acquire_lock(runs_dir, timeout=1)
            finally:
                mod.release_lock(runs_dir)

    def test_release_foreign_lock_keeps(self):
        # 手写别人的锁（ чужой pid）：release 不得删除
        mod = load_modelswap()
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            lock = runs_dir / mod.LOCK_NAME
            lock.mkdir(parents=False, exist_ok=False)
            (lock / "pid").write_text("999999999", encoding="utf-8")
            mod.release_lock(runs_dir)
            self.assertTrue(lock.exists())
            shutil.rmtree(lock, ignore_errors=True)

    def test_release_own_lock_removes(self):
        mod = load_modelswap()
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            mod.acquire_lock(runs_dir, timeout=5)
            mod.release_lock(runs_dir)
            self.assertFalse((runs_dir / mod.LOCK_NAME).exists())


class _FakeStore:
    """ mimics RunsStore：默认只看 dispatch，全量需 owner=None。"""

    def __init__(self, recs):
        self.recs = recs
        self.path = "fake-RUNS.jsonl"

    def list_running(self, owner="dispatch"):
        if owner is None:
            return [r for r in self.recs if r.get("status") == "running"]
        return [r for r in self.recs
                if r.get("status") == "running"
                and r.get("owner", "dispatch") == owner]


class _OldStore:
    """老 store：list_running 无 owner 参数，无参即全量。"""

    def __init__(self, recs):
        self.recs = recs
        self.path = "old-RUNS.jsonl"

    def list_running(self):
        return [r for r in self.recs if r.get("status") == "running"]


class TestRunningCount(unittest.TestCase):
    def test_pipeline_visible_only_in_full_query(self):
        dispatch = load_dispatch()
        modelswap = load_modelswap()
        recs = [
            {"task_id": "TASK-1", "status": "running", "owner": "dispatch"},
            {"task_id": "TASK-2", "status": "running", "owner": "pipeline"},
            {"task_id": "TASK-3", "status": "awaiting-review",
             "owner": "dispatch"},
        ]
        store = _FakeStore(recs)
        default = store.list_running()
        self.assertEqual([r["task_id"] for r in default], ["TASK-1"])
        full = store.list_running(owner=None)
        self.assertEqual(sorted(r["task_id"] for r in full),
                         ["TASK-1", "TASK-2"])
        # 槽位计算函数返回全量数
        self.assertEqual(dispatch.running_count(store), 2)
        # _all_records 回退分支同样查全量
        self.assertEqual(
            sorted(r["task_id"] for r in modelswap._all_records(store)),
            ["TASK-1", "TASK-2"])

    def test_old_store_fallback(self):
        dispatch = load_dispatch()
        modelswap = load_modelswap()
        recs = [
            {"task_id": "TASK-1", "status": "running", "owner": "dispatch"},
            {"task_id": "TASK-2", "status": "running", "owner": "pipeline"},
        ]
        store = _OldStore(recs)
        self.assertEqual(dispatch.running_count(store), 2)
        self.assertEqual(len(modelswap._all_records(store)), 2)


class TestMaybeRestore(unittest.TestCase):
    def _write_settings(self, sp, model):
        sp.write_text(
            SETTINGS.replace("deepseek/deepseek-v4-flash-0731:free", model),
            encoding="utf-8")

    def test_restore_from_just_finished(self):
        mod = load_modelswap()
        import yaml
        with TemporaryDirectory() as tmp:
            sp = Path(tmp) / "settings.yaml"
            self._write_settings(sp, "cohere/north-mini-code:free")
            store = _FakeStore([])
            just = [{"task_id": "TASK-1", "status": "awaiting-review",
                     "model_swapped": True,
                     "prev_model": ["openrouter", "orig-model:free"]}]
            ret = mod.maybe_restore(sp, store, just)
            self.assertEqual(ret, ("openrouter", "orig-model:free"))
            data = yaml.safe_load(sp.read_text(encoding="utf-8"))
            self.assertEqual(data["agent-default-model"]["model"],
                             "orig-model:free")

    def test_running_swapped_keeps(self):
        mod = load_modelswap()
        with TemporaryDirectory() as tmp:
            sp = Path(tmp) / "settings.yaml"
            self._write_settings(sp, "cohere/north-mini-code:free")
            before = sp.read_text(encoding="utf-8")
            store = _FakeStore([
                {"task_id": "T1", "status": "running", "owner": "pipeline",
                 "model_swapped": True,
                 "prev_model": ["openrouter", "orig-model:free"]}])
            just = [{"task_id": "T0", "status": "awaiting-review",
                     "model_swapped": True,
                     "prev_model": ["openrouter", "older:free"]}]
            self.assertIsNone(mod.maybe_restore(sp, store, just))
            self.assertEqual(sp.read_text(encoding="utf-8"), before)

    def test_bad_shape_skipped(self):
        # str 型旧形状非法：跳过并 WARN，不恢复
        mod = load_modelswap()
        with TemporaryDirectory() as tmp:
            sp = Path(tmp) / "settings.yaml"
            self._write_settings(sp, "cohere/north-mini-code:free")
            before = sp.read_text(encoding="utf-8")
            store = _FakeStore([])
            just = [{"task_id": "T1", "status": "awaiting-review",
                     "model_swapped": True,
                     "prev_model": "openrouter/orig-model:free"}]
            self.assertIsNone(mod.maybe_restore(sp, store, just))
            self.assertEqual(sp.read_text(encoding="utf-8"), before)

    def test_empty_just_finished_noop(self):
        mod = load_modelswap()
        with TemporaryDirectory() as tmp:
            sp = Path(tmp) / "settings.yaml"
            self._write_settings(sp, "cohere/north-mini-code:free")
            store = _FakeStore([])
            self.assertIsNone(mod.maybe_restore(sp, store, []))
            self.assertIsNone(mod.maybe_restore(sp, store))


if __name__ == "__main__":
    unittest.main()
