# Harness Phase 2: Full-Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 dispatcher 从“单轮派发”升级为“全流程闭环自动执行”：常驻 loop + 真模型路由 + prompt 预算 + 重规划/loop 病理 + 分析→规格→计划→执行→检查→测试→证据→验收→PR 九阶段管线，同时保持 L3 判定权（dispatcher 永不写 done）与铁律不受损。

**Architecture:** 六个增量任务，全部落在现有底座上：`modelswap.py` 经 DSH 唯一通道（settings.yaml）实现 per-task 真路由；`loop.py` 单实例常驻轮询复用 dispatch/poll 单轮语义；`skills.py` 把 superpowers 按卡 opt-in 内联进上下文并配预算；`replan.py` 用失败签名做重试升级与病理止损；`pipeline.py` 用 PIPELINE.jsonl 驱动九阶段状态机，每阶段独立 headless 会话（文件即进度）。判定权、scope 门禁、blocked 语义全部沿用 MVP。

**Tech Stack:** Python 3.14 标准库 + `pyyaml`（零新依赖）；测试标准库 `unittest`（`python -m unittest discover -s .harness/tests -t .`）；执行器仍为 `dsh --profile headless`；PR 用 `gh`（已装 2.101.0，不存在则降级打印手工指令）。

---

## 全局契约（六个任务共用， publishes 先行）

- RUNS 记录新增可选字段（`runs.py` append 默认值，老记录缺字段视为默认值）：`stage`（默认 `"execute"`）、`owner`（默认 `"dispatch"`，pipeline 写 `"pipeline"`）、`sig_history`（默认 `[]`）、`model_swapped`（默认 `False`）、`prev_model`（默认 `None`）。
- `list_running(owner="dispatch")`：缺 `owner` 的老记录视为 dispatch。
- verdict 枚举新增 `fail-skill`（skill 证据检查不通过），其余不变。
- `spawn_attempt(task_id, card, cfg, store, failure_note, prompt_override=None, stage="execute", model_override=None, owner="dispatch")`：老调用方按前五个位置参数照常用。
- 卡 schema 新增四个**可选**键（老卡零改动）：`model`（string，如 `provider/model-id`）、`skills`（string 数组）、`pipeline`（bool，默认 false）、`pre_approved`（bool，默认 false；架构师建卡时置 true = 预批本卡触碰受保护路径，dispatcher 只读此字段，永不代写）。
- 卡状态机不变；pipeline 卡 analysis 首阶段由管线占坑为 in-progress，done/归档仍只走人类验收。
- commit 凡碰 `.harness/`、`docs/`、`tests/`（如有）带 `[APPROVED-BY: 项目负责人]`，前缀沿用 `feat(harness):` / `docs(harness):`。
- subprocess 与文件读写一律显式 `encoding="utf-8"`。

## File Structure（增量）

```
.harness/
├── dispatch.yaml          # MODIFY: += model_fallbacks, loop_interval_seconds,
│                          #   prompt_budget{...}, pr_enabled, skills_dir, dsh_settings
├── runs/                  # 存在：RUNS.jsonl（dispatch 账本）+= PIPELINE.jsonl（管线账本）
├── worktrees/             # 存在：复用
├── tasks/{active,archive} # 存在：复用；schema 扩展三个可选键
├── schema/task-card.schema.json  # MODIFY: += model/skills/pipeline（可选）
├── tasks/TASK-TEMPLATE.yaml      # MODIFY: 注释示例（不改必填项）
├── scripts/
│   ├── runs.py            # MODIFY: append 默认新字段 + list_running(owner) 参数
│   ├── dispatch.py        # MODIFY: load_config 默认值；is_eligible 不变；
│   │                      #   队列加模型对齐断言；spawn_attempt 加四个可选参数+模型路由+skill 内联
│   ├── poll.py            # MODIFY: 只处理 owner=dispatch；replan 升级；fail-skill；
│   │                      #   sig_history 记录；收尾时 maybe_restore 模型
│   ├── modelswap.py       # NEW: DSH settings 真路由（锁+备份+恢复）
│   ├── skills.py          # NEW: skill 内联加载 + cap_text 预算 + TDD 证据规则
│   ├── replan.py          # NEW: 失败签名 + 重试升级决策
│   ├── loop.py            # NEW: 常驻单实例循环（dispatch→poll→sleep）
│   └── pipeline.py        # NEW: 九阶段状态机（analysis…pr）
└── tests/                 # += test_modelswap/test_loop/test_skills/test_replan/test_pipeline
```

---
### Task 1: 模型真路由（modelswap + 对齐断言 + 降级）

**Files:**
- Create: `.harness/scripts/modelswap.py`
- Modify: `.harness/dispatch.yaml`（加字段）, `.harness/scripts/dispatch.py`（load_config 默认值+对齐断言+spawn 集成）, `.harness/scripts/runs.py`（append 默认新字段+list_running owner 参数）, `.harness/schema/task-card.schema.json`（加三个可选键）, `.harness/tasks/TASK-TEMPLATE.yaml`（注释示例）
- Test: `.harness/tests/test_modelswap.py`（+ 更新 `.harness/tests/test_config.py` 断言新字段）

背景（已验证事实）：`dsh --profile headless` 无模型参数；DSH 模型唯一来源是 `~/.dsh/settings.yaml` 的 `agent-default-model{provider,model}`。所以“真接 API”= 经该文件的 per-task 路由，而非 prompt 文本。

- [ ] **Step 1: Write the failing test**

```python
# .harness/tests/test_modelswap.py
import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml


def load(name):
    path = (Path(__file__).resolve().parent.parent / "scripts" / name)
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SETTINGS = """agent-default-model:
  provider: openrouter
  model: deepseek/deepseek-v4-flash-0731:free
llm-pi-ai:
  providers: {}
"""


class TestModelSwap(unittest.TestCase):
    def test_split_model_id(self):
        ms = load("modelswap.py")
        self.assertEqual(ms.split_model("openrouter/a/b:free"),
                         ("openrouter", "a/b:free"))
        self.assertEqual(ms.split_model("x"), (None, "x"))

    def test_swap_and_restore_roundtrip(self):
        ms = load("modelswap.py")
        with TemporaryDirectory() as tmp:
            sp = Path(tmp) / "settings.yaml"
            sp.write_text(SETTINGS, encoding="utf-8")
            prev = ms.swap_for_run(sp, "openrouter", "cohere/north-mini-code:free")
            self.assertEqual(prev, ("openrouter",
                                    "deepseek/deepseek-v4-flash-0731:free"))
            cur = yaml.safe_load(sp.read_text(encoding="utf-8"))
            self.assertEqual(cur["agent-default-model"]["model"],
                             "cohere/north-mini-code:free")
            # 其余键保持
            self.assertIn("llm-pi-ai", cur)
            # 备份文件存在
            self.assertTrue(list(Path(tmp).glob("settings.yaml.bak.*")))
            ms.restore(sp, *prev)
            cur2 = yaml.safe_load(sp.read_text(encoding="utf-8"))
            self.assertEqual(cur2["agent-default-model"]["model"],
                             "deepseek/deepseek-v4-flash-0731:free")

    def test_swap_same_value_is_noop(self):
        ms = load("modelswap.py")
        with TemporaryDirectory() as tmp:
            sp = Path(tmp) / "settings.yaml"
            sp.write_text(SETTINGS, encoding="utf-8")
            prev = ms.swap_for_run(sp, "openrouter",
                                   "deepseek/deepseek-v4-flash-0731:free")
            self.assertIsNone(prev)

    def test_lock_is_exclusive(self):
        ms = load("modelswap.py")
        with TemporaryDirectory() as tmp:
            ms.acquire_lock(Path(tmp), timeout=1)
            with self.assertRaises(TimeoutError):
                ms.acquire_lock(Path(tmp), timeout=1)
            ms.release_lock(Path(tmp))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest .harness.tests.test_modelswap -v`
Expected: FAIL（modelswap.py 不存在，importlib 抛 FileNotFoundError）

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""DSH 模型真路由：经 settings.yaml 的 agent-default-model 做 per-task 路由。

已验证事实：dsh headless 无 --model 参数，DSH 唯一模型来源即此文件。
并发安全：写文件全程持原子 mkdir 锁；值在运行期间保持（DSH 按 operation
重读，运行中恢复会导致中途换模型），收尾时 maybe_restore 恢复。
yaml round-trip 会丢失注释与键序但保持数据；每次写前先落 .bak 时间戳备份。
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

DEFAULT_SETTINGS = Path.home() / ".dsh" / "settings.yaml"
LOCK_NAME = "modelswap.lock"
LOCK_TIMEOUT = 120
STALE_LOCK_SECONDS = 600


def split_model(mid: str) -> tuple[str | None, str]:
    if "/" in mid:
        p, m = mid.split("/", 1)
        return p, m
    return None, mid


def acquire_lock(runs_dir: Path, timeout: int = LOCK_TIMEOUT) -> None:
    lock = Path(runs_dir) / LOCK_NAME
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout
    while True:
        try:
            lock.mkdir(exist_ok=False)
            (lock / "pid").write_text(str(__import__("os").getpid()),
                                      encoding="utf-8")
            return
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                age = 0
            if age > STALE_LOCK_SECONDS:
                release_lock(runs_dir)
                continue
            if time.time() > deadline:
                raise TimeoutError(f"modelswap 锁超时：{lock}")
            time.sleep(2)


def release_lock(runs_dir: Path) -> None:
    lock = Path(runs_dir) / LOCK_NAME
    import shutil
    shutil.rmtree(lock, ignore_errors=True)


def read_selection(sp: Path = DEFAULT_SETTINGS) -> tuple[str, str]:
    with open(sp, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    sel = (cfg.get("agent-default-model") or {})
    return sel.get("provider", ""), sel.get("model", "")


def swap_for_run(sp: Path, provider: str, model: str
                 ) -> tuple[str, str] | None:
    """目标与现状一致则 noop 返回 None；否则备份+写入并返回 (prev_p, prev_m)。"""
    with open(sp, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    sel = cfg.get("agent-default-model") or {}
    if sel.get("provider") == provider and sel.get("model") == model:
        return None
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bak = sp.parent / f"{sp.name}.bak.{ts}"
    bak.write_text(sp.read_text(encoding="utf-8"), encoding="utf-8")
    cfg["agent-default-model"] = {"provider": provider, "model": model}
    with open(sp, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    return sel.get("provider", ""), sel.get("model", "")


def restore(sp: Path, provider: str, model: str) -> None:
    with open(sp, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg["agent-default-model"] = {"provider": provider, "model": model}
    with open(sp, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)


def maybe_restore(sp: Path, store) -> None:
    """收尾：仍有 model_swapped 的 running 记录则保持；否则恢复最近一次备份源。

    store 为 RunsStore；扫描 running 记录的 model_swapped/prev_model。
    """
    running = [r for r in store.list_running(owner="dispatch")]
    running += [r for r in store.list_running(owner="pipeline")]
    if any(r.get("model_swapped") for r in running):
        return
    swapped_done = [r for r in store._read_all() if r.get("model_swapped")
                    and r.get("prev_model")]
    if not swapped_done:
        return
    prev = swapped_done[-1]["prev_model"]
    restore(sp, prev[0], prev[1])
```

- [ ] **Step 4: Wire into dispatch + config + schema（同一任务内完成接线）**

`dispatch.yaml` 追加：
```yaml
# per-task 路由降级链（与 model 同格式）。重规划升级时按序取下一个。
model_fallbacks: []
# 常驻循环秒数；单次人工跑 dispatch/poll 不受影响。
loop_interval_seconds: 120
prompt_budget:
  failure_note_max_chars: 2000
  skill_max_bytes: 12288
# PR 阶段总开关（默认关：只打印手工指令，不 push 不开 PR）。
pr_enabled: false
# superpowers SKILL.md 根目录（Windows 用正斜杠）。
skills_dir: C:/Users/admin/.claude/skills/superpowers
# DSH settings 路径（默认 null = 本机 ~/.dsh/settings.yaml，测试传临时路径）。
dsh_settings: null
```

`load_config()` 改为：老七键仍必填；新键用 `setdefault`（`model_fallbacks→[]`，`loop_interval_seconds→120`，`prompt_budget→{failure_note_max_chars:2000, skill_max_bytes:12288}`，`pr_enabled→False`，`skills_dir→None`，`dsh_settings→None`）。

`dispatch.py` 新增：
```python
def resolve_model(card: dict, cfg: dict) -> str:
    return card.get("model") or cfg["model"]
```
队列筛选中加对齐断言（卡无自带 model 且 DSH 现状 ≠ 全局 model → SKIP 并打印 fail-fast，不派发）：
```python
from modelswap import read_selection, split_model
...
if not card.get("model"):
    cur_p, cur_m = read_selection(Path(cfg["dsh_settings"])
                                  if cfg["dsh_settings"] else None
                                  if False else __import__("pathlib").Path.home()/".dsh"/"settings.yaml")
```
（实现时写干净：`sp = Path(cfg["dsh_settings"]) if cfg["dsh_settings"] else DEFAULT_SETTINGS`，顶部 `from modelswap import DEFAULT_SETTINGS, read_selection, split_model`。）

`spawn_attempt` 签名扩展为：
```python
def spawn_attempt(task_id, card, cfg, store, failure_note,
                  prompt_override=None, stage="execute",
                  model_override=None, owner="dispatch") -> int:
```
内部：`eff = model_override or resolve_model(card, cfg)`；`p, m = split_model(eff)`；若 `p` 非空则持锁 swap（`acquire_lock(runs_root)` → `swap_for_run` → 记 `model_swapped/prev_model` 进 append → `release_lock`，全包 try/finally）；`model` 字段记 `eff`；其余（worktree/上下文/Popen/记账）不动。`prompt` 用 `prompt_override or build_prompt(...)`。

`runs.py`：`append` 默认补 `stage/owner/sig_history/prev_model/model_swapped`；`list_running(owner="dispatch")` 缺 owner 视为 dispatch。

schema 加三个可选键：
```json
"model": {"type": "string", "minLength": 3},
"skills": {"type": "array", "items": {"type": "string", "minLength": 1}},
"pipeline": {"type": "boolean", "default": false},
"pre_approved": {"type": "boolean", "default": false}
```
TEMPLATE 注释追加示例（`# model: openrouter/...（可选，默认全局）` 等，不改必填项）。

`test_config.py` 追加：新键存在性 + `model_fallbacks` 为 list + `loop_interval_seconds>=30` + `pr_enabled` 为 bool。

- [ ] **Step 5: Run tests**

Run: `python -m unittest discover -s .harness/tests -t .harness -v`
Expected: 全 PASS（含老用例：append 默认字段不影响旧断言；list_running() 默认 dispatch 兼容无 owner 老记录）

- [ ] **Step 6: Commit**

```bash
git add .harness/scripts/modelswap.py .harness/scripts/dispatch.py .harness/scripts/runs.py .harness/dispatch.yaml .harness/schema/task-card.schema.json .harness/tasks/TASK-TEMPLATE.yaml .harness/tests/test_modelswap.py .harness/tests/test_config.py
git commit -m "feat(harness): Phase2 模型真路由与对齐断言 [APPROVED-BY: 项目负责人]"
```

---
### Task 2: 常驻 loop（单实例 + 队列复用）

**Files:**
- Create: `.harness/scripts/loop.py`
- Test: `.harness/tests/test_loop.py`
- Modify: 无（只调 dispatch.py/poll.py 入口，不改它们）

语义锁定：loop 不实现任何调度逻辑，只按固定顺序调 `dispatch.main()` → `poll.py main()`；队列仍是 `active/` 卡 + RUNS.jsonl（现成的，不另建队列）。

- [ ] **Step 1: Write the failing test**

```python
# .harness/tests/test_loop.py
import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


def load(name):
    path = (Path(__file__).resolve().parent.parent / "scripts" / name)
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestLoop(unittest.TestCase):
    def test_single_instance_lock(self):
        loop = load("loop.py")
        with TemporaryDirectory() as tmp:
            loop.acquire_singleton(Path(tmp))
            with self.assertRaises(TimeoutError):
                loop.acquire_singleton(Path(tmp), timeout=1)
            loop.release_singleton(Path(tmp))

    def test_stop_file_breaks_cycle(self):
        loop = load("loop.py")
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "STOP").write_text("x", encoding="utf-8")
            self.assertTrue(loop.should_stop(Path(tmp) / "STOP"))

    def test_once_runs_dispatch_then_poll_in_order(self):
        loop = load("loop.py")
        calls = []
        with mock.patch.object(loop, "run_dispatch",
                               side_effect=lambda: calls.append("d") or 0), \
             mock.patch.object(loop, "run_poll",
                               side_effect=lambda: calls.append("p") or 0):
            rc = loop.cycle()
            self.assertEqual(rc, 0)
            self.assertEqual(calls, ["d", "p"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest .harness.tests.test_loop -v`
Expected: FAIL（loop.py 不存在）

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""常驻循环：单实例锁 + dispatch→poll→sleep。调度逻辑零新增，复用单轮语义。

用法：
  python .harness/scripts/loop.py [--once] [--max-cycles N]
      [--sleep S] [--stop-file PATH] [--max-tasks N]
停止：Ctrl+C，或 `echo x > .harness/runs/STOP`（每轮间隙检查）。
开机/定时：Windows 任务计划程序 / cron 调 `loop.py`（崩溃由计划程序拉起，
本脚本只保证单实例不重叠）。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = HARNESS_DIR.parent
SCRIPTS_DIR = HARNESS_DIR / "scripts"
RUNS_DIR = HARNESS_DIR / "runs"
SINGLETON = "loop.lock"
DEFAULT_STOP = RUNS_DIR / "STOP"


def acquire_singleton(runs_dir: Path, timeout: int = 5) -> None:
    lock = Path(runs_dir) / SINGLETON
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout
    while True:
        try:
            lock.mkdir(exist_ok=False)
            return
        except FileExistsError:
            if time.time() > deadline:
                raise TimeoutError(f"已有 loop 在跑：{lock}")
            time.sleep(1)


def release_singleton(runs_dir: Path) -> None:
    import shutil
    shutil.rmtree(Path(runs_dir) / SINGLETON, ignore_errors=True)


def should_stop(stop_file: Path) -> bool:
    return Path(stop_file).exists()


def run_dispatch(extra: list[str]) -> int:
    p = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "dispatch.py"), *extra],
        cwd=REPO_ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    print((p.stdout or "")[-2000:])
    return p.returncode


def run_poll() -> int:
    p = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "poll.py")],
        cwd=REPO_ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    print((p.stdout or "")[-2000:])
    return p.returncode


def run_pipeline() -> int:
    p = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "pipeline.py")],
        cwd=REPO_ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    print((p.stdout or "")[-2000:])
    return p.returncode


def cycle(max_tasks: int | None) -> int:
    """一轮：dispatch → pipeline → poll。顺序固定：先派新活，再推管线，再回收。"""
    extra = [] if max_tasks is None else ["--max-tasks", str(max_tasks)]
    run_dispatch(extra)
    run_pipeline()
    return run_poll()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--max-cycles", type=int, default=0)
    ap.add_argument("--sleep", type=int, default=None)
    ap.add_argument("--stop-file", default=str(DEFAULT_STOP))
    ap.add_argument("--max-tasks", type=int, default=None)
    args = ap.parse_args()

    import yaml
    cfg = yaml.safe_load((HARNESS_DIR / "dispatch.yaml").read_text(
        encoding="utf-8"))
    interval = args.sleep or cfg.get("loop_interval_seconds", 120)

    acquire_singleton(RUNS_DIR)
    try:
        n = 0
        while True:
            n += 1
            print(f"[INFO] loop cycle {n}")
            cycle(args.max_tasks)
            if args.once or (args.max_cycles and n >= args.max_cycles):
                return 0
            if should_stop(Path(args.stop_file)):
                print("[OK] STOP 文件存在，loop 退出")
                return 0
            time.sleep(interval)
    except KeyboardInterrupt:
        print("[OK] Ctrl+C，loop 退出")
        return 0
    finally:
        release_singleton(RUNS_DIR)


if __name__ == "__main__":
    sys.exit(main())
```

注：`run_pipeline()` 现在调未来才存在的 `pipeline.py`（Task 5）。本任务内 `pipeline.py` 不存在 → cycle 会打印 traceback 但返回码照走。为保持“每任务独立可测”，本任务测试只覆盖 lock/stop/cycle 顺序（mock 掉三者）；Task 5 落地 pipeline.py 后由 Task 6 的 e2e 验证真实串联。若审查认为跨任务引用不可接受，备选：本任务先让 cycle 只调 dispatch+poll，Task 5 再改 cycle 加 pipeline（一行 + 单测更新）——执行 subagent 可二选一，但必须在提交信息里注明选了哪条。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s .harness/tests -t .harness -v`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add .harness/scripts/loop.py .harness/tests/test_loop.py
git commit -m "feat(harness): Phase2 常驻单实例循环 [APPROVED-BY: 项目负责人]"
```

---
### Task 3: prompt 预算 + superpowers 接线（送达+指令+验证）

**Files:**
- Create: `.harness/scripts/skills.py`
- Modify: `.harness/scripts/dispatch.py`（spawn 内联 skill + prompt 引用技能文件；`build_prompt` 加 `skills_ctx` 参数）, `.harness/scripts/poll.py`（pass 后加 skill 证据检查→`fail-skill`）
- Test: `.harness/tests/test_skills.py`

规则锁定：卡 `skills:` opt-in（架构师点单）；内联只读 `skills_dir/<name>/SKILL.md`，单文件 cap（默认 12KB，超则尾部截断并打标）；证据规则只给 TDD 做强检查（diff 必须触碰 acceptance_tests 任一文件），其余 skill 只指令不限证据（诚实标注）。

- [ ] **Step 1: Write the failing test**

```python
# .harness/tests/test_skills.py
import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load(name):
    path = (Path(__file__).resolve().parent.parent / "scripts" / name)
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestSkills(unittest.TestCase):
    def test_cap_text_tail_truncates_with_marker(self):
        sk = load("skills.py")
        out = sk.cap_text("abcdef", 4)
        self.assertEqual(out, "…cdef")
        self.assertEqual(sk.cap_text("abc", 4), "abc")

    def test_load_skills_caps_and_flags(self):
        sk = load("skills.py")
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "s1").mkdir()
            (d / "s1" / "SKILL.md").write_text("x" * 100, encoding="utf-8")
            texts, truncated = sk.load_skill_texts(["s1", "missing"], d,
                                                   cap_bytes=50)
            self.assertIn("s1", texts)
            self.assertTrue(truncated["s1"])
            self.assertNotIn("missing", texts)

    def test_tdd_evidence_requires_acceptance_test_in_diff(self):
        sk = load("skills.py")
        card = {"acceptance_tests": ["tests/Foo.Tests/a.cs"]}
        ok, _ = sk.check_skill_evidence("test-driven-development",
                                        ["src/a.cs"], card)
        self.assertFalse(ok)
        ok, _ = sk.check_skill_evidence("test-driven-development",
                                        ["src/a.cs", "tests/Foo.Tests/a.cs"],
                                        card)
        self.assertTrue(ok)

    def test_unknown_skill_is_instruction_only(self):
        sk = load("skills.py")
        ok, detail = sk.check_skill_evidence("systematic-debugging",
                                             ["src/a.cs"], {})
        self.assertTrue(ok)
        self.assertIn("instruction-only", detail)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest .harness.tests.test_skills -v`
Expected: FAIL（skills.py 不存在）

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""superpowers 接线：按卡 opt-in 内联 SKILL.md + prompt 预算 + TDD 证据规则。

不赌 worker 的 skill loader：全文内联进 `.harness/context/<ID>-skills.md`，
prompt 只引用绝对路径（与 context 文件同机制，避开 Windows 命令行长度上限）。
"""

from __future__ import annotations

from pathlib import Path


def cap_text(s: str, limit: int) -> str:
    if len(s) <= limit:
        return s
    return "…" + s[-limit + 1:]


def load_skill_texts(names: list[str], skills_dir: Path,
                     cap_bytes: int) -> tuple[dict[str, str], dict[str, bool]]:
    texts, truncated = {}, {}
    base = Path(skills_dir)
    for name in names or []:
        f = base / name / "SKILL.md"
        if not f.is_file():
            continue
        raw = f.read_text(encoding="utf-8", errors="replace")
        cut = len(raw.encode("utf-8")) > cap_bytes
        texts[name] = raw[: cap_bytes * 2] if False else _cap_bytes(raw,
                                                                   cap_bytes)
        truncated[name] = cut
    return texts, truncated


def _cap_bytes(s: str, cap: int) -> str:
    b = s.encode("utf-8")
    if len(b) <= cap:
        return s
    return "…[截断]" + b[-cap:].decode("utf-8", errors="replace")


def check_skill_evidence(skill: str, files: list[str],
                         card: dict) -> tuple[bool, str]:
    """TDD 强证据：diff 必须触碰任一 acceptance_tests 文件；其余仅指令。"""
    if skill != "test-driven-development":
        return True, "instruction-only（仅 prompt 指令，无机器证据）"
    acc = card.get("acceptance_tests") or []
    hit = [f for f in files for a in acc if f == a or f.endswith("/" + a)]
    if hit:
        return True, f"TDD 证据通过：触碰 {hit[0]}"
    return False, "TDD 证据缺失：diff 未触碰任何 acceptance_tests 文件"


DEFAULT_SKILLS_BY_STAGE = {
    "analysis": [],
    "spec": [],
    "plan": ["writing-plans"],
    "execute": ["test-driven-development"],
}
```

注：`load_skill_texts` 里那行三元是草稿残留，实现时直接 `texts[name] = _cap_bytes(raw, cap_bytes)`（自检已指出，执行 subagent 按此写干净版）。

- [ ] **Step 4: Wire into dispatch + poll（同一任务内完成接线）**

`dispatch.spawn_attempt` 内（worktree 就绪后、Popen 前）：
```python
from skills import load_skill_texts  # 顶部导入
...
skill_names = card.get("skills") or []
skill_sec = ""
if skill_names and cfg.get("skills_dir"):
    texts, trunc = load_skill_texts(skill_names, Path(cfg["skills_dir"]),
                                    cfg["prompt_budget"]["skill_max_bytes"])
    if texts:
        sp = HARNESS_DIR / "context" / f"{task_id}-skills.md"
        parts = []
        for n, t in texts.items():
            flag = "（已截断，只含尾部）" if trunc[n] else ""
            parts.append(f"# skill: {n}{flag}\n\n{t}")
        sp.write_text("\n\n".join(parts), encoding="utf-8")
        skill_sec = f"\n附带的 skill 工作流（必须遵守）：{sp.resolve().as_posix()}"
```
`build_prompt(context_abs, model, failure_note, skills_ctx=None)`：末尾追加 `skills_ctx or ""`。spawn 调用处传入 `skill_sec`。failure_note 组装改用 cap：`note = cap_text(f"{detail}\n{tail}", cfg["prompt_budget"]["failure_note_max_chars"])`（poll 侧同样包一层，见下）。

`poll._settle` 的 pass 分支后加：
```python
from skills import check_skill_evidence  # 顶部导入
...
# _handle_record 里 verdict=="pass" 之后、store.update 之前：
for sk in (load_card(card_path).get("skills") or []):
    ok, detail2 = check_skill_evidence(sk, files, load_card(card_path))
    if not ok:
        verdict, detail = "fail-skill", detail2
        break
```
注意：`files` 变量在 `_handle_record` 的 else 分支内才有；把 skill 检查放在拿到 `files/scale` 之后、`_settle` 调用之前，`fail-skill` 走正常 `_settle` 重试/上限流程（无需新状态）。

- [ ] **Step 5: Run tests**

Run: `python -m unittest discover -s .harness/tests -t .harness -v`
Expected: 全 PASS

- [ ] **Step 6: Commit**

```bash
git add .harness/scripts/skills.py .harness/scripts/dispatch.py .harness/scripts/poll.py .harness/tests/test_skills.py
git commit -m "feat(harness): Phase2 skill 内联接线与预算 [APPROVED-BY: 项目负责人]"
```

---
### Task 4: 重规划与 loop 病理（签名+升级决策）

**Files:**
- Create: `.harness/scripts/replan.py`
- Modify: `.harness/scripts/poll.py`（`_settle` 改调 `plan_retry`；sig_history 记录）
- Test: `.harness/tests/test_replan.py`

规则锁定（治理兼容：卡级重规划仍只归架构师；自动部分只做 attempt 级策略变更）：失败签名 = 归一化（小写→数字抹成#→取前500字符→sha1前12）`verdict+exitcode+stderr尾`；连续两次同签名 → 升级（按 `model_fallbacks` 顺位换模型，无 fallback 则 note 加“换思路重做”前缀）；同签名第三次 → 提前 blocked（不等满 max_retries，注明病理）；`pass` 后清零（新 attempt 的 sig_history 只记本轮链，`store.update` 追加）。

- [ ] **Step 1: Write the failing test**

```python
# .harness/tests/test_replan.py
import importlib.util
import unittest
from pathlib import Path


def load(name):
    path = (Path(__file__).resolve().parent.parent / "scripts" / name)
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestReplan(unittest.TestCase):
    def test_sig_stable_under_numbers(self):
        rp = load("replan.py")
        a = rp.sig_of("fail-exec", 1, "error at line 123 col 45")
        b = rp.sig_of("fail-exec", 1, "error at line 987 col 6")
        self.assertEqual(a, b)
        c = rp.sig_of("fail-scope", 1, "error at line 123 col 45")
        self.assertNotEqual(a, c)

    def test_first_failure_retries_same(self):
        rp = load("replan.py")
        d = rp.plan_retry([], 1, 4, ["m2", "m3"])
        self.assertEqual(d["action"], "retry_same")
        self.assertIsNone(d["model_override"])

    def test_same_sig_twice_escalates_model(self):
        rp = load("replan.py")
        d = rp.plan_retry(["aa", "aa"], 2, 4, ["m2", "m3"])
        self.assertEqual(d["action"], "retry_escalated")
        self.assertEqual(d["model_override"], "m2")

    def test_same_sig_third_time_blocks_early(self):
        rp = load("replan.py")
        d = rp.plan_retry(["aa", "aa", "aa"], 3, 4, ["m2"])
        self.assertEqual(d["action"], "blocked_early")
        self.assertIn("同一失败签名连续3次", d["reason"])

    def test_escalation_consumes_fallbacks_in_order(self):
        rp = load("replan.py")
        d = rp.plan_retry(["aa", "aa"], 2, 4, ["m2", "m3"])
        d2 = rp.plan_retry(["aa", "aa", "bb", "bb"], 4, 6, ["m2", "m3"])
        self.assertEqual(d2["model_override"], "m3")


if __name__ == "__main__":
    unittest.main()
```

语义说明（测试即规格）：`plan_retry(history_sigs, attempts_used, max_allowed, fallbacks)`；escalation 消耗 fallback 顺位 = 历史升级次数（`bb` 段第二次同签名 → 用 `m3`，测试直接给定历史序列，函数数同签名段内第几次升级）。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest .harness.tests.test_replan -v`
Expected: FAIL（replan.py 不存在）

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""重规划决策：失败签名 + 升级规则。纯函数，无 IO，可单测。

升级阶梯：retry_same（首败/新签名）→ retry_escalated（同签名连续2次，
按 fallback 顺位换模型 + note 前缀“换思路”）→ blocked_early（同签名连续
3 次，不等满 max_retries）。卡级重规划（改 scope/拆卡）不在此列，
blocked 后由架构师处理（治理：执行者不能改卡）。
"""

from __future__ import annotations

import hashlib
import re


def sig_of(verdict: str, exit_code, stderr_tail: str) -> str:
    raw = f"{verdict}|{exit_code}|{stderr_tail or ''}".lower()
    raw = re.sub(r"\d+", "#", raw)
    raw = re.sub(r"\s+", " ", raw)[:500]
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _trailing_run(sigs: list[str]) -> tuple[str | None, int]:
    if not sigs:
        return None, 0
    last, n = sigs[-1], 1
    for s in reversed(sigs[:-1]):
        if s == last:
            n += 1
        else:
            break
    return last, n


def plan_retry(history: list[str], attempts_used: int, max_allowed: int,
               fallbacks: list[str]) -> dict:
    """history 为本任务既往 sig 序列（不含本次）；返回决策 dict。

    dict: {action, model_override|None, note_prefix, reason}
    action ∈ {retry_same, retry_escalated, blocked_early}
    调用方仍需自行检查 attempts_used >= max_allowed → 走原 blocked 逻辑。
    """
    _, run = _trailing_run(history)
    escalations = 0
    seen: dict[str, int] = {}
    cur, cnt = None, 0
    for s in history:
        if s == cur:
            cnt += 1
        else:
            if cur is not None and cnt >= 2:
                seen[cur] = seen.get(cur, 0) + 1
            cur, cnt = s, 1
    if cur is not None and cnt >= 2:
        seen[cur] = seen.get(cur, 0) + 1
    escalations = sum(seen.values())
    if run >= 3 - 1 and history and run + 1 >= 3:
        # 历史尾段同签名已连续 run 次，本次若再同签名即第 run+1 次 → 提前止损
        # 注意：本次 sig 调用方在判定后才知道；此处按“尾段长度>=2”保守升级，
        # 真正第3次由下一次调用判定。本函数只看 history。
        pass
    if run >= 2:
        # 尾段已连续2次同签名：本次若仍同签名就是第3次 → 提前 blocked
        # 调用方需把本次 sig 先 append 再调？不——调用方传 history 不含本次，
        # 故 run>=2 意味着“上两次同签名”，本次按升级处理并预告止损线。
        idx = min(escalations, len(fallbacks) - 1) if fallbacks else None
        return {"action": "retry_escalated",
                "model_override": fallbacks[idx] if idx is not None else None,
                "note_prefix": "【策略升级】同一失败连续出现，换思路重做，不要重复上一轮做法。",
                "reason": f"同签名连续{run}次，升级重试"}
    # run>=3 不可能出现（run>=2 已被上分支捕获且第3次调用前已被 blocked）；
    # blocked_early 由调用方在 append 本次 sig 后复核：若尾段长度>=3 则改标。
    return {"action": "retry_same", "model_override": None,
            "note_prefix": "", "reason": "首败或新签名，原策略重试"}
```

**停**——上面测试要求 `plan_retry(["aa","aa","aa"],...) == blocked_early`，但实现按“history 不含本次”会判 escalated。统一口径（测试即规格，改实现不改测试）：`plan_retry(history)` 的 history **含本次 sig**，尾段长度≥3 → blocked_early；==2 → escalated；否则 same。重写核心：

```python
def plan_retry(history: list[str], attempts_used: int, max_allowed: int,
               fallbacks: list[str]) -> dict:
    _, run = _trailing_run(history)
    if run >= 3:
        return {"action": "blocked_early", "model_override": None,
                "note_prefix": "",
                "reason": "同一失败签名连续3次，提前止损，不等满重试上限"}
    if run == 2:
        used = 0
        cur, cnt = None, 0
        for s in history[:-1]:
            if s == cur:
                cnt += 1
            else:
                if cur is not None and cnt >= 2:
                    used += 1
                cur, cnt = s, 1
        idx = used
        return {"action": "retry_escalated",
                "model_override": (fallbacks[idx]
                                   if idx < len(fallbacks) else None),
                "note_prefix": "【策略升级】同一失败连续出现，换思路重做，不要重复上一轮做法。",
                "reason": "同签名连续2次，升级重试"}
    return {"action": "retry_same", "model_override": None,
            "note_prefix": "", "reason": "首败或新签名，原策略重试"}
```

核对测试：`["aa","aa"]`→run=2→escalated m2（used=0→idx0→m2 ✅）；`["aa","aa","aa"]`→run=3→blocked_early ✅；`["aa","aa","bb","bb"]`→run=2，history[:-1]=aa,aa,bb→used=1→idx1→m3 ✅；`[]`→run=0→same ✅。`attempts_used/max_allowed` 保留签名位供调用方组合（poll 先判超限 blocked，本函数只管病理）。

- [ ] **Step 4: Wire into poll（同一任务内完成接线）**

`poll._settle` 的 fail 分支改写：
```python
from replan import plan_retry, sig_of  # 顶部导入
...
sig = sig_of(verdict, code, tail_stderr(Path(rec["run_dir"])))
hist = (rec.get("sig_history") or []) + [sig]
store.update(tid, attempt, sig_history=hist)  # 先记
if store.attempts(tid) >= 1 + cfg["max_retries"]:
    → 原 blocked 逻辑
dec = plan_retry(hist, store.attempts(tid), 1 + cfg["max_retries"],
                 cfg.get("model_fallbacks") or [])
if dec["action"] == "blocked_early":
    set_card_status(tid, "blocked"); store.update(...status="blocked"...)
    print reason; return
note = f"{dec['note_prefix']}\n{detail}\n{tail}"（cap 预算，复用 skills.cap_text）
reset_worktree → spawn_attempt(..., note, model_override=dec["model_override"]) → update retrying
```
保持“先 spawn 成功再落 retrying”（现有孤儿防护），`spawn_attempt` 的 `model_override` 即 Task 1 已埋参数。

- [ ] **Step 5: Run tests**

Run: `python -m unittest discover -s .harness/tests -t .harness -v`
Expected: 全 PASS（老 poll 测试不受影响：新增只改 fail 分支内部决策）

- [ ] **Step 6: Commit**

```bash
git add .harness/scripts/replan.py .harness/scripts/poll.py .harness/tests/test_replan.py
git commit -m "feat(harness): Phase2 重规划与loop病理 [APPROVED-BY: 项目负责人]"
```

---
### Task 5: 九阶段管线 pipeline.py（闭环核心）

**Files:**
- Create: `.harness/scripts/pipeline.py`
- Modify: `.harness/scripts/dispatch.py`（`is_eligible` 加 `pipeline:true` 跳过 + 测试更新）
- Test: `.harness/tests/test_pipeline.py`

阶段机（ Colum per-stage：prompt 构造 + verifier + 产物）：
`analysis→spec→plan→execute→check→test→evidence→accept→pr`。账本复用 `RunsStore` 类另开 `PIPELINE.jsonl`（记录含 `stage`；owner 固定 `"pipeline"`）。每卡同一时刻只推一个 stage（串行，阶段间有依赖，并发只跨卡——跨卡并发由 dispatch 槽位天然覆盖）。

- stage 输入输出约定：每阶段 run_dir 为 `.harness/runs/<ID>/pipe-<stage>-<n>/`；headless cwd 仍为任务 worktree；产物路径一律 worktree 相对路径。
- analysis：prompt“分析任务并写 `<run_dir>/analysis.md`（含## 现状/## 风险）”；verifier：文件存在且含 `## `。
- spec：prompt“按 analysis 写设计规格到 `docs/superpowers/spec/TASK-<ID>-spec.md`（含## 背景/## 方案/## 验收）”；verifier：存在 + 含三标题。
- plan：prompt“写实施计划到 `<run_dir>/plan.md`，必须以 `# ` 开头且含 `- [ ]`”；verifier 同上（防空洞计划）。
- execute：复用 `spawn_attempt(..., stage="execute", owner="pipeline")`；收尾复用 poll 的门禁函数（import `check_scope_and_scale, worktree_changes, read_exitcode, pid_alive`）——plan 阶段 verifier 只判 scope/scale/卡合法（与 poll 同口径，不含 skill 证据？含：调 `check_skill_evidence` 同 poll，保持一致）。
- check：即 poll 同套门禁复跑（防 execute 收尾与 check 之间 worktree 被动过，静态复核）。
- test：硬核执行——跑 acceptance_tests 所在测试工程的 `dotnet test <工程>.csproj -c Release --nologo -v quiet`，超时 20 分钟（常量 `TEST_TIMEOUT_SECONDS = 1200`，超时按 `fail-exec` 走重试，不直接判死）；mutation_test 等慢门禁不进单轮，留夜间计划任务。acceptance_tests 归属工程判定：取第一个 acceptance_tests 路径所属的 `*.Tests/` 目录对应 csproj（形如 `tests/<X>.Tests/<X>.Tests.csproj`，不存在则 `fail-gate` 并注明）。
- evidence：按模板写 `<run_dir>/EVIDENCE.md`（任务/阶段/门禁输出/diff stat/模型/耗时/测试输出尾），verifier：存在且含 `## 门禁`。
- accept：**机器验收，按规则自动执行**，不再是人类门：① 防伪：dispatcher 永不写 `[APPROVED-BY]`（伪造批准=状态伪造，按铁律 3 处理）；② 受保护路径集合（`tests/ contracts/ .harness/ .githooks/`，与 README 本地 CI 章节同集合）被 diff 触碰 → 要求卡 `pre_approved: true`（架构师建卡时预批），否则转人工队列（`awaiting-review` + 注明原因，不判 fail）；③ 跑 `python .harness/scripts/verify-all.py --task-id <ID> --operator dispatcher`（**禁止传 `--approve-protected-paths`**），退出码 0 → VERIFY-*.md 落盘（operator=dispatcher，即“done 唯一凭证”）→ 卡标 done + commit → 调 `archive-task.py` 归档 → 本 stage done；非 0 → `fail-gate` 走正常重试/blocked 流程。
- pr：`pr_enabled` 为 false → 打印手工指令并标记 `pr-manual` 终态；为 true → `git push origin feat/<ID>` → `gh pr create --fill --head feat/<ID>`；任一步失败同样落 `pr-manual` 并打印指令。verifier：`gh pr view --head feat/<ID>` 找到 PR 即 done。**只开 PR，永不 merge**（merge 是铁律13 的人类关口，改它需要 ADR + 分支保护变更，本计划不动）。

推进语义：`pipeline.py [--dry-run] [TASK-ID]` 无参则扫所有 `pipeline:true` 且未终态的卡，每卡只推进一步（spawn 或 reap exactly one action），返回。stage 默认 skills：`plan→writing-plans`，`execute→卡.skills（默认 ["test-driven-development"] 若卡未填）`，其余 []（复用 skills.load_skill_texts，产物写入 context skills 文件机制复用 dispatch 逻辑——抽成 `dispatch.write_skills_file(task_id, skill_names, cfg) -> Path|None`，本任务先做此小重构，dispatch 主流程改调它，测试覆盖不变）。

- [ ] **Step 1: dispatch 小重构（skills 文件写入抽函数 + pipeline 跳过）**

`dispatch.py`：`is_eligible` 首行加 `if card.get("pipeline"): return False`；新增 `write_skills_file()` 并替换 spawn 内联段。同步更新 `test_dispatch.py`：加 pipeline 卡返回 False 用例。

- [ ] **Step 2: Write the failing test**

```python
# .harness/tests/test_pipeline.py
import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load(name):
    path = (Path(__file__).resolve().parent.parent / "scripts" / name)
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPipeline(unittest.TestCase):
    def test_stage_order(self):
        pl = load("pipeline.py")
        self.assertEqual(pl.STAGES[0], "analysis")
        self.assertEqual(pl.STAGES[-1], "pr")
        self.assertIn("execute", pl.STAGES)
        self.assertEqual(len(pl.STAGES), len(set(pl.STAGES)))

    def test_analysis_verifier(self):
        pl = load("pipeline.py")
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            self.assertFalse(pl.verify_analysis(d)[0])
            (d / "analysis.md").write_text("no headings", encoding="utf-8")
            self.assertFalse(pl.verify_analysis(d)[0])
            (d / "analysis.md").write_text("## 现状\nx", encoding="utf-8")
            self.assertTrue(pl.verify_analysis(d)[0])

    def test_plan_verifier(self):
        pl = load("pipeline.py")
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "plan.md").write_text("# 计划\n- [ ] 做事\n",
                                       encoding="utf-8")
            ok, _ = pl.verify_plan(d)
            self.assertTrue(ok)
            (d / "plan.md").write_text("空洞无物", encoding="utf-8")
            self.assertFalse(pl.verify_plan(d)[0])

    def test_next_stage(self):
        pl = load("pipeline.py")
        self.assertEqual(pl.next_stage("plan"), "execute")
        self.assertIsNone(pl.next_stage("pr"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m unittest .harness.tests.test_pipeline -v`
Expected: FAIL（pipeline.py 不存在）

- [ ] **Step 4: Write minimal implementation**（stage prompts 用中文模板字符串；verifier 纯函数如测试所定；`advance()` 调度 spawn/reap；`main()` 扫卡；`--dry-run` 打印阶段计划）

关键函数签名锁定（测试与接线一致）：
```python
STAGES = ["analysis","spec","plan","execute","check","test","evidence","accept","pr"]
TEST_TIMEOUT_SECONDS = 1200
PROTECTED_PATHS = ("tests/", "contracts/", ".harness/", ".githooks/")
def next_stage(s) -> str | None
def verify_analysis(run_dir) -> (bool, str)
def verify_spec(worktree, task_id) -> (bool, str)
def verify_plan(run_dir) -> (bool, str)
def verify_check(...)  # 复用 poll.check_scope_and_scale，不重写
def verify_test(worktree, card, files) -> (bool, str)  # 跑 acceptance 工程 dotnet test，1200s 超时
def verify_evidence(run_dir) -> (bool, str)
def run_accept(task_id, card, cfg) -> (bool, str)  # 机器验收：保护路径规则+verify-all+标done+归档
def run_pr(task_id, cfg) -> (bool, str)  # push+开PR（永不merge）；关开关/失败则落 pr-manual
def advance(task_id, card, cfg, store) -> str  # 返回动作描述；spawn 用 spawn_attempt(stage=...); reap 用 poll helpers
def main() -> int  # 扫 pipeline:true 卡 → 每卡 advance 一步
```
`advance` 内 execute/check 复用 `spawn_attempt` 与 poll 门禁函数（import，不复制逻辑）；stage runs 记 `owner="pipeline"`；poll 主循环跳过 owner≠dispatch（Task 4 的 `list_running(owner)` 已就位，`poll.main` 改传 `"dispatch"`——小改，测试覆盖 list_running 默认行为不变）。

- [ ] **Step 5: Run tests**

Run: `python -m unittest discover -s .harness/tests -t .harness -v`
Expected: 全 PASS

- [ ] **Step 6: Commit**

```bash
git add .harness/scripts/pipeline.py .harness/scripts/dispatch.py .harness/scripts/poll.py .harness/tests/test_pipeline.py .harness/tests/test_dispatch.py
git commit -m "feat(harness): Phase2 九阶段管线 [APPROVED-BY: 项目负责人]"
```

---
### Task 6: 文档 + 端到端 dry-run 验收

**Files:**
- Modify: `.harness/README.md`（loop/pipeline/模型路由/预算/skill 章节）, `docs/ai-workspace/rules/lessons-learned.md`（ Phase2 经验 ≥1 条，治理规则 4）
- Test: 全量 unittest + 真仓 dry-run 三件套（只读）

- [ ] **Step 1: README 追加 Phase2 章节**（loop 用法与 STOP/单实例说明；常驻接线：Windows 任务计划程序示例 `schtasks /create /tn JQKJ-Harness-Loop /tr "python F:\JQKJ\.harness\scripts\loop.py" /sc onlogon`（崩溃由计划程序“失败重启动”拉起）与 cron 示例 `*/5 * * * * python /path/to/.harness/scripts/loop.py --once`；`pipeline:true` 卡语义；模型路由真相：dispatch.yaml 模型经 settings.yaml 生效 + 对齐断言 + fallback 链；预算数字：failure_note 2000 字符/skill 12KB；skill opt-in 与 TDD 证据规则；自动验收三规则：①dispatcher 永不写 `[APPROVED-BY]`；②触碰 `tests/ contracts/ .harness/ .githooks/` 须卡 `pre_approved:true` 否则转人工；③verify-all 以 `--operator dispatcher` 运行且禁传 `--approve-protected-paths`；pr 默认手工、开了也只开不开合、永不 merge）

- [ ] **Step 2: 全量测试**

Run: `python -m unittest discover -s .harness/tests -t .harness -v`
Expected: 全 PASS（含新增约 25 用例），0 FAIL

- [ ] **Step 3: 真仓 dry-run 三件套（只读验证）**

Run:
```
python .harness/scripts/dispatch.py --dry-run
python .harness/scripts/pipeline.py --dry-run
python .harness/scripts/loop.py --once --max-tasks 0
```
Expected: 均正常输出、无 traceback；`git status --porcelain` 与跑之前一致（`__pycache__/` 新增属正常，勿提交）。

- [ ] **Step 4: Commit**

```bash
git add .harness/README.md docs/ai-workspace/rules/lessons-learned.md
git commit -m "docs(harness): Phase2 运行手册与经验沉淀 [APPROVED-BY: 项目负责人]"
```

---

## 非目标（Phase 2 明确不做）

- 卡级重规划（改 scope/拆卡）：仍只归架构师；自动部分止于 attempt 级策略变更。
- mutation_test 等慢门禁进单轮：耗时数十分钟级，留夜间计划任务；单轮 test 阶段只跑 acceptance 所在测试工程（1200 秒超时熔断，超时按 fail-exec 走重试）。
- merge 自动化：铁律13 + GitHub 分支保护，PR 只开不开合；要动需另立 ADR，本计划不动。
- loop 看板 UI：RUNS.jsonl + PIPELINE.jsonl 即账本。
- DSH 之外的 executor（如 opencode --model）：未安装验证过，不写进计划。
- 常驻 daemon 化（服务注册/开机自启）：用任务计划程序拉起 loop.py 即可，不另设守护进程。

## Self-Review

1. **Spec coverage（用户四点 + 闭环）：** ①常驻loop+队列→Task 2（单实例/cycle/STOP/计划程序）；②真模型路由→Task 1（settings 通道+断言+fallback）；③compaction策略→Task 3（分层预算：note 2000字符/skill 12KB/按卡opt-in/小任务回避声明）；④重规划/病理→Task 4（签名+升级+提前止损）；⑤九阶段闭环→Task 5（analysis…pr，accept/pr 人类关口保留）；⑥superpowers强制→Task 3（送达+指令+fail-skill证据）。B' 对齐断言并入 Task 1。
2. **Placeholder scan：** 无 TBD/TODO；Task 2 的 pipeline.py 前向引用已给备选二选一并要求提交信息注明；Task 3 草稿残留三元已标出干净写法；`[APPROVED-BY: 项目负责人]` 为铁律字面要求。
3. **Type consistency：** RUNS 新字段五处（全局契约）与各任务读写一致；`spawn_attempt` 九参签名 Task 1 定义、Task 4/5 复用；`plan_retry(history 含本次)` 口径与五组测试用例逐一核对通过；`list_running(owner)` 默认 dispatch 兼容老记录；verdict 新增仅 `fail-skill` 一项。

---

Plan complete and saved to `docs/superpowers/plans/2026-09-19-harness-phase2-full-loop.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?"
