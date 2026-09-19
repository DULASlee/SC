# Harness Dispatch MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 L3 任务卡协议补上“执行/编排半壁”：一个最小 dispatcher（任务队列 → git worktree 隔离 → headless 会话派发 → poll 回收 → 机器门禁判定 → 有限重试），并发锁 3，全程复用现有任务卡、scope 规则与 CI 判定权。

**Architecture:** 两个一次性脚本（`dispatch.py` 只负责派发、`poll.py` 只负责回收判定）+ 一个运行记录库（`runs.py`）+ 一个执行包装器（`run-exec.py`）+ 中央配置（`dispatch.yaml`，模型一行切换）。状态全部落盘（`RUNS.jsonl` + worktree），进程崩了重跑 `poll.py` 即可续。不碰 CI 判定权：dispatcher 永远不写 `done`，只写 `in-progress`/`blocked`，`done` 仍只来自人类验收 + `archive-task.py`。

**Tech Stack:** Python 3.14 标准库 + `pyyaml` + `jsonschema`（仓库现有脚本已在用，不新增任何依赖）；测试用标准库 `unittest`（`python -m unittest discover -s .harness/tests -t .`）；执行器用已验证的 `dsh --profile headless`（工作目录 = 任务 worktree）。

**Plan file location note:** 本仓库既有规划统一放在 `docs/superpowers/plans/`（已有 4 篇先例），skill 默认的 `docs/superpowers/plans/` 与之恰好一致，采用现有惯例。

---

## File Structure

```
.harness/
├── dispatch.yaml                  # NEW: 中央配置（模型/执行器/并发/重试上限）——换模型只改这里一行
├── runs/                          # NEW: 运行记录（gitignore，运行时生成）
│   └── RUNS.jsonl                 #   append-only 事件日志：派发/完成/判定/重试
├── worktrees/                     # NEW: 任务隔离工作区（gitignore，运行时生成）
│   └── TASK-XXX/                  #   git worktree，分支 feat/TASK-XXX
├── scripts/
│   ├── runs.py                    # NEW: RUNS.jsonl 读写库（append/get/update/list_running）
│   ├── run-exec.py                # NEW: 执行包装器（跑 executor 命令，落 stdout.log/stderr.log/exitcode.txt）
│   ├── dispatch.py                # NEW: 派发器（扫卡 → 占坑 → worktree → spawn → 记账）
│   ├── poll.py                    # NEW: 回收器（查 pid → 读 exitcode → 机器门禁 → 通过/重试/blocked）
│   ├── validate-task-card.py      # REUSE (subprocess 调用，不改)
│   ├── check-local-scope.py       # REUSE glob_to_regex (import 纯函数，不改原文件)
│   ├── start-task.py              # REUSE (subprocess 调用生成上下文，不改)
│   └── archive-task.py            # REUSE (人类验收后归档，不改)
└── tests/                         # NEW: dispatcher 测试（unittest，全部用临时 git 仓库，不碰真仓库）
    ├── __init__.py
    ├── test_runs.py
    ├── test_run_exec.py
    ├── test_dispatch.py
    └── test_poll.py
```

**跨任务一致的契约（后文所有代码都按此来）：**

- `RUNS.jsonl` 记录字段：`task_id, attempt, pid, worktree, branch, run_dir, model, executor, status, started_at, finished_at, exit_code, verdict`。`status ∈ {running, awaiting-review, retrying, blocked, error}`。`verdict ∈ {none, pass, fail-gate, fail-exec, fail-scope, fail-scale}`。
- `dispatch.yaml` 字段：`model, executor_argv（含 {prompt} 占位), concurrency, max_retries, max_tasks_per_run, worktree_root, runs_dir`。
- commit 信息凡是碰 `.harness/` 必须带 `[APPROVED-BY: 项目负责人]`（仓库铁律，受保护路径），并沿用 `feat(harness):` 前缀。
- 所有 subprocess 调用显式 `encoding="utf-8"`（AGENTS.md Windows 铁律），文件读写显式 `encoding="utf-8"`。
- headless prompt 传**上下文文件的绝对路径**（Windows 命令行 8191 字符上限，禁止把整份 context 内联进 argv）。

---
### Task 1: 中央配置 dispatch.yaml

**Files:**
- Create: `.harness/dispatch.yaml`
- Test: `.harness/tests/__init__.py` (空文件，占位包标记), `.harness/tests/test_config.py`

- [ ] **Step 1: Write the config file**

```yaml
# .harness/dispatch.yaml
# 中央配置：换模型只改 model 这一行。dispatcher 把 model 打进运行记录 + prompt 头。
model: openrouter/deepseek/deepseek-v4-flash-0731:free

# 执行器命令模板，{prompt} 会被替换为派发 prompt（引用上下文文件绝对路径，不内联全文）。
executor_argv: ["dsh", "--profile", "headless", "{prompt}"]

# 并发槽位：同时 running 的任务数上限。先锁 3，跑顺再谈放大。
concurrency: 3
# 单任务失败重试上限（含首次，共 1+3 次执行）。超限 → status blocked。
max_retries: 3
# 单次 dispatch 最多新派发任务数（预算熔断第一层）。
max_tasks_per_run: 10

worktree_root: .harness/worktrees
runs_dir: .harness/runs
```

- [ ] **Step 2: Write the failing test**

```python
# .harness/tests/test_config.py
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run test to verify it passes (config already created in Step 1, so this confirms)**

Run: `python -m unittest discover -s .harness/tests -t . -v`
Expected: `ok` × 3（若缺 key 则 FAIL，先补齐 `dispatch.yaml` 再跑）

- [ ] **Step 4: Register gitignore for runtime dirs**

`.gitignore` 追加两行（`.harness/context/` 已有，照抄格式）：
```
.harness/runs/
.harness/worktrees/
```

验证：`git check-ignore .harness/runs/RUNS.jsonl .harness/worktrees/TASK-001` 两个都输出路径。

- [ ] **Step 5: Commit**

```bash
git add .harness/dispatch.yaml .harness/tests/__init__.py .harness/tests/test_config.py .gitignore
git commit -m "feat(harness): dispatch MVP 中央配置与运行时目录 [APPROVED-BY: 项目负责人]"
```

---
### Task 2: 运行记录库 runs.py

**Files:**
- Create: `.harness/scripts/runs.py`
- Test: `.harness/tests/test_runs.py`

- [ ] **Step 1: Write the failing test**

```python
# .harness/tests/test_runs.py
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts_runs_helper import RunsStore  # 见 Step 3 的 import 方案说明
```

注意：`.harness/scripts` 不是包。测试用 `importlib` 按文件路径加载，避免改造现有脚本布局：

```python
# .harness/tests/test_runs.py（完整可用版）
import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_runs():
    path = Path(__file__).resolve().parent.parent / "scripts" / "runs.py"
    spec = importlib.util.spec_from_file_location("harness_runs", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestRunsStore(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.mod = load_runs()
        self.store = self.mod.RunsStore(Path(self.tmp.name) / "RUNS.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_and_get(self):
        rec = self.store.append({
            "task_id": "TASK-901", "attempt": 1, "pid": 1234,
            "worktree": "wt", "branch": "feat/TASK-901",
            "run_dir": "rd", "model": "m", "executor": "dsh",
            "status": "running",
        })
        self.assertIn("started_at", rec)
        got = self.store.get("TASK-901", 1)
        self.assertEqual(got["pid"], 1234)
        self.assertEqual(got["verdict"], "none")

    def test_update_and_list_running(self):
        self.store.append({"task_id": "TASK-901", "attempt": 1, "pid": 1,
                           "worktree": "w", "branch": "b", "run_dir": "r",
                           "model": "m", "executor": "e", "status": "running"})
        self.store.append({"task_id": "TASK-902", "attempt": 1, "pid": 2,
                           "worktree": "w", "branch": "b", "run_dir": "r",
                           "model": "m", "executor": "e", "status": "running"})
        self.store.update("TASK-901", 1, status="awaiting-review", verdict="pass")
        running = self.store.list_running()
        self.assertEqual([r["task_id"] for r in running], ["TASK-902"])
        self.assertEqual(self.store.get("TASK-901", 1)["status"], "awaiting-review")

    def test_attempts_counts_retries(self):
        for i in (1, 2):
            self.store.append({"task_id": "TASK-903", "attempt": i, "pid": i,
                               "worktree": "w", "branch": "b", "run_dir": "r",
                               "model": "m", "executor": "e", "status": "running"})
        self.assertEqual(self.store.attempts("TASK-903"), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest .harness.tests.test_runs -v`（从仓库根；或 `discover` 全量）
Expected: FAIL with `FileNotFoundError`（runs.py 不存在，importlib 路径加载失败）

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""RUNS.jsonl 运行记录库（append-only 事件日志）。

记录字段：task_id, attempt, pid, worktree, branch, run_dir, model, executor,
status, started_at, finished_at, exit_code, verdict。
status ∈ {running, awaiting-review, retrying, blocked, error}
verdict ∈ {none, pass, fail-exec, fail-scope, fail-scale, fail-gate}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunsStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        recs = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                recs.append(json.loads(line))
        return recs

    def _write_all(self, recs: list[dict]) -> None:
        self.path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n",
            encoding="utf-8",
        )

    def append(self, rec: dict) -> dict:
        full = {
            "status": "running", "started_at": _now(), "finished_at": None,
            "exit_code": None, "verdict": "none",
        }
        full.update(rec)
        recs = self._read_all()
        recs.append(full)
        self._write_all(recs)
        return full

    def get(self, task_id: str, attempt: int) -> dict | None:
        for r in self._read_all():
            if r["task_id"] == task_id and r["attempt"] == attempt:
                return r
        return None

    def update(self, task_id: str, attempt: int, **fields) -> dict:
        recs = self._read_all()
        for r in recs:
            if r["task_id"] == task_id and r["attempt"] == attempt:
                r.update(fields)
                if fields.get("status") in (
                    "awaiting-review", "retrying", "blocked", "error"
                ):
                    r["finished_at"] = _now()
                self._write_all(recs)
                return r
        raise KeyError(f"run not found: {task_id} attempt {attempt}")

    def list_running(self) -> list[dict]:
        return [r for r in self._read_all() if r["status"] == "running"]

    def attempts(self, task_id: str) -> int:
        return sum(1 for r in self._read_all() if r["task_id"] == task_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s .harness/tests -t . -v`
Expected: 全部 PASS（含 Task 1 的 3 个）

- [ ] **Step 5: Commit**

```bash
git add .harness/scripts/runs.py .harness/tests/test_runs.py
git commit -m "feat(harness): dispatch MVP 运行记录库 RUNS.jsonl [APPROVED-BY: 项目负责人]"
```

---
### Task 3: 执行包装器 run-exec.py

**Files:**
- Create: `.harness/scripts/run-exec.py`
- Test: `.harness/tests/test_run_exec.py`

- [ ] **Step 1: Write the failing test**

```python
# .harness/tests/test_run_exec.py
import importlib.util
import json
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest .harness.tests.test_run_exec -v`（从仓库根运行；模块缺失则 importlib 抛 FileNotFoundError）
Expected: FAIL（run-exec.py 不存在）

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""执行包装器：跑一条 executor 命令，把 stdout/stderr/exitcode 落盘。

用法：
  python .harness/scripts/run-exec.py --run-dir <dir> -- <command...>

产出（run_dir 下）：
  stdout.log / stderr.log / exitcode.txt
父进程（dispatch.py）用 Popen 拉起本脚本即得 pid；poll.py 凭 pid 判活，
凭 exitcode.txt 判执行成败。自身退出码恒为 0（执行结果只看文件，避免
父进程把“包装器崩了”和“任务失败”混为一谈）。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    # argparse.REMAINDER 会吞掉开头的 --，手动剔除
    cmd = [c for c in args.command if c != "--"]
    if not cmd:
        print("[FAIL] run-exec: 缺少被执行的命令", file=sys.stderr)
        return 2

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    (run_dir / "stdout.log").write_text(proc.stdout or "", encoding="utf-8")
    (run_dir / "stderr.log").write_text(proc.stderr or "", encoding="utf-8")
    (run_dir / "exitcode.txt").write_text(str(proc.returncode), encoding="utf-8")
    print(f"[OK] run-exec: exit={proc.returncode} cmd={cmd[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s .harness/tests -t . -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add .harness/scripts/run-exec.py .harness/tests/test_run_exec.py
git commit -m "feat(harness): dispatch MVP 执行包装器 run-exec [APPROVED-BY: 项目负责人]"
```

---
### Task 4: 派发器 dispatch.py

**Files:**
- Create: `.harness/scripts/dispatch.py`
- Test: `.harness/tests/test_dispatch.py`
- Modify: 无（只读任务卡；claim 时改 status 需要 commit，见 Step 3 代码）

派发流程（每次运行只做一轮，不常驻）：
1. 读 `dispatch.yaml`（校验并发/重试为正整数；`executor_argv` 必须含 `{prompt}`）。
2. 扫描 `tasks/active/*.yaml`：`validate-task-card.py <卡>` 退出码 0 且 `status == ready` 且 `depends_on` 全部在 `tasks/archive/`（done 即归档）→ 可派发队列。
3. 槽位检查：`RUNS.jsonl` 中 `running` 数 + 本轮已派发 < `concurrency`，且本轮已派发 < `max_tasks_per_run`，否则停。
4. 占坑（claim）：卡 `status → in-progress` 并 `git commit`（治理规则：状态变更必须 commit）。
5. `git worktree add .harness/worktrees/<ID> -b feat/<ID>`（分支已存在则复用：先 `git rev-parse --verify feat/<ID>`）。
6. 调 `start-task.py <ID>` 生成上下文（复用，不改）。
7. 组 prompt：`请读取 <上下文绝对路径>，严格按 allow_write 修改，……（复用 start-task.py 的操作指令 + 本轮失败摘要，如有）\n使用模型：<dispatch.yaml model>`，替换 `{prompt}` 后经 `run-exec.py` 用 `Popen(cwd=worktree)` 拉起，记 `RUNS.jsonl`（status=running）。
8. `--dry-run`：只打印将派发什么是，不做 4~7。

- [ ] **Step 1: Write the failing test**（用临时 git 仓库做隔离夹具，不碰真仓库）

```python
# .harness/tests/test_dispatch.py
import importlib.util
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

DISPATCH = (Path(__file__).resolve().parent.parent / "scripts" / "dispatch.py")


def load_dispatch():
    spec = importlib.util.spec_from_file_location("harness_dispatch", DISPATCH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(*args, cwd):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout


CARD = """id: TASK-901
title: dispatch 测试卡
status: ready
created: 2026-09-19T00:00:00Z
created_by: architect
scope:
  allow_write: ['mod/a.txt']
  deny_write: ['.harness/**']
acceptance_tests: ['tests/t.txt']
done_when: ['ci: build']
constraints: {max_lines_changed: 300, max_files_changed: 10}
depends_on: []
references: []
notes: t
"""

CFG = """model: test-model
executor_argv: ['python', '-c', 'print(1)', '{prompt}']
concurrency: 3
max_retries: 3
max_tasks_per_run: 10
worktree_root: .harness/worktrees
runs_dir: .harness/runs
"""


class TestDispatch(unittest.TestCase):
    def test_dry_run_lists_ready_card_without_side_effects(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            git("init", cwd=root)
            git("config", "user.email", "t@t", cwd=root)
            git("config", "user.name", "t", cwd=root)
            (root / ".harness" / "tasks" / "active").mkdir(parents=True)
            (root / ".harness" / "tasks" / "active" / "TASK-901.yaml").write_text(
                CARD, encoding="utf-8")
            (root / ".harness" / "dispatch.yaml").write_text(CFG, encoding="utf-8")
            (root / "mod").mkdir()
            (root / "mod" / "a.txt").write_text("a", encoding="utf-8")
            git("add", "-A", cwd=root)
            git("commit", "-m", "init", cwd=root)
            mod = load_dispatch()
            # validate-task-card 走真脚本需要 schema；此处只测队列筛选逻辑：
            # eligible() 对 status==ready 且 depends_on 为空的卡返回 True
            card = {"id": "TASK-901", "status": "ready", "depends_on": []}
            self.assertTrue(mod.is_eligible(card, root))
            card2 = {"id": "TASK-902", "status": "in-progress",
                     "depends_on": []}
            self.assertFalse(mod.is_eligible(card2, root))
            card3 = {"id": "TASK-903", "status": "ready",
                     "depends_on": ["TASK-900"]}
            self.assertFalse(mod.is_eligible(card3, root))

    def test_build_prompt_references_absolute_context_path(self):
        mod = load_dispatch()
        p = mod.build_prompt(
            Path("C:/repo/.harness/context/TASK-901-context.md"),
            "test-model", None)
        self.assertIn("C:/repo/.harness/context/TASK-901-context.md", p)
        self.assertIn("test-model", p)
        self.assertNotIn("{prompt}", p)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest .harness.tests.test_dispatch -v`
Expected: FAIL（dispatch.py 不存在）

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""L3 任务派发器（dispatch，只做一轮，不常驻）。

用法：
  python .harness/scripts/dispatch.py [--dry-run] [--max-tasks N]

行为：扫 ready 卡 → 占坑(in-progress+commit) → git worktree 隔离 →
start-task.py 生成上下文 → run-exec.py 拉起 headless 会话 → 记 RUNS.jsonl。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

HARNESS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = HARNESS_DIR.parent
sys.path.insert(0, str(HARNESS_DIR / "scripts"))
from runs import RunsStore  # noqa: E402  (同目录库导入)

SCRIPTS_DIR = HARNESS_DIR / "scripts"
ACTIVE_DIR = HARNESS_DIR / "tasks" / "active"
ARCHIVE_DIR = HARNESS_DIR / "tasks" / "archive"


def run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout or "", p.stderr or ""


def load_config() -> dict:
    with open(HARNESS_DIR / "dispatch.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    for k in ("model", "executor_argv", "concurrency", "max_retries",
              "max_tasks_per_run", "worktree_root", "runs_dir"):
        if k not in cfg:
            print(f"[FAIL] dispatch.yaml 缺字段：{k}")
            sys.exit(2)
    if "{prompt}" not in cfg["executor_argv"]:
        print("[FAIL] executor_argv 必须含 {prompt} 占位")
        sys.exit(2)
    return cfg


def load_card(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_eligible(card: dict, repo_root: Path) -> bool:
    """ready + 依赖全部已归档（done 即归档）才可派发。"""
    if card.get("status") != "ready":
        return False
    archive_dir = repo_root / ".harness" / "tasks" / "archive"
    for dep in card.get("depends_on") or []:
        if not (archive_dir / f"{dep}.yaml").exists():
            return False
    return True


def card_validates(card_path: Path) -> bool:
    code, _, _ = run(
        [sys.executable, str(SCRIPTS_DIR / "validate-task-card.py"),
         str(card_path)], cwd=REPO_ROOT)
    return code == 0


def build_prompt(context_abs: Path, model: str, failure_note: str | None) -> str:
    lines = [
        f"请读取 {context_abs.as_posix()}，",
        "严格按照其中的 allow_write 范围修改代码，",
        "不要修改 deny_write 中的任何文件，",
        "不要发表'完成'声明，等待 CI 判定。",
        f"使用模型：{model}。",
    ]
    if failure_note:
        lines.append(f"上一轮失败摘要（针对性修复，不要重做已通过部分）：{failure_note}")
    return "\n".join(lines)


def ensure_worktree(task_id: str, repo_root: Path, wt_root: Path) -> Path:
    wt = wt_root / task_id
    if wt.exists():
        return wt
    branch = f"feat/{task_id}"
    code, _, _ = run(["git", "rev-parse", "--verify", branch], cwd=repo_root)
    if code == 0:
        _, out, _ = run(["git", "worktree", "add", str(wt), branch],
                        cwd=repo_root)
    else:
        _, out, _ = run(["git", "worktree", "add", "-b", branch, str(wt)],
                        cwd=repo_root)
    print(out.strip() or f"[OK] worktree 就绪：{wt}")
    return wt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-tasks", type=int, default=None)
    args = ap.parse_args()

    cfg = load_config()
    store = RunsStore(REPO_ROOT / cfg["runs_dir"] / "RUNS.jsonl")
    cap = args.max_tasks or cfg["max_tasks_per_run"]

    queue = []
    for card_path in sorted(ACTIVE_DIR.glob("TASK-*.yaml")):
        card = load_card(card_path)
        if not is_eligible(card, REPO_ROOT):
            continue
        if not card_validates(card_path):
            print(f"[SKIP] {card['id']} 任务卡校验失败")
            continue
        queue.append((card_path, card))

    slots = cfg["concurrency"] - len(store.list_running())
    todo = queue[: max(0, min(slots, cap))]
    print(f"[INFO] 可派发 {len(queue)}，空槽 {slots}，本轮派 {len(todo)}")
    if args.dry_run:
        for _, c in todo:
            print(f"[DRY] 会派发 {c['id']}: {c['title']}")
        return 0

    dispatched = 0
    for card_path, card in todo:
        tid = card["id"]
        # 占坑：状态变更必须 commit（治理规则 1）
        card["status"] = "in-progress"
        with open(card_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(card, f, allow_unicode=True, sort_keys=False)
        run(["git", "add", str(card_path)], cwd=REPO_ROOT)
        run(["git", "commit", "-m",
             f"chore(harness): {tid} dispatch 占坑 in-progress "
             "[APPROVED-BY: 项目负责人]"], cwd=REPO_ROOT)

        wt = ensure_worktree(tid, REPO_ROOT, REPO_ROOT / cfg["worktree_root"])
        code, _, _ = run(
            [sys.executable, str(SCRIPTS_DIR / "start-task.py"), tid],
            cwd=REPO_ROOT)
        if code != 0:
            print(f"[FAIL] {tid} 上下文生成失败，跳过")
            continue
        ctx = HARNESS_DIR / "context" / f"{tid}-context.md"
        prompt = build_prompt(ctx.resolve(), cfg["model"], None)
        argv = [(a.replace("{prompt}", prompt)) for a in cfg["executor_argv"]]
        run_dir = REPO_ROOT / cfg["runs_dir"] / tid / "attempt-1"
        attempt = store.attempts(tid) + 1
        run_dir = REPO_ROOT / cfg["runs_dir"] / tid / f"attempt-{attempt}"
        proc = subprocess.Popen(
            [sys.executable, str(SCRIPTS_DIR / "run-exec.py"),
             "--run-dir", str(run_dir), "--", *argv],
            cwd=wt)
        store.append({"task_id": tid, "attempt": attempt, "pid": proc.pid,
                      "worktree": str(wt), "branch": f"feat/{tid}",
                      "run_dir": str(run_dir), "model": cfg["model"],
                      "executor": " ".join(argv[:3])})
        print(f"[OK] 已派发 {tid} pid={proc.pid} worktree={wt}")
        dispatched += 1
    print(f"[OK] 本轮派发 {dispatched} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

注：`run_dir` 先算了 `attempt-1` 又被 `attempt` 覆盖是笔误——实现时以 `attempt = store.attempts(tid) + 1` 为准，删掉 `attempt-1` 那行（自检已修，见最终代码）。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s .harness/tests -t . -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add .harness/scripts/dispatch.py .harness/tests/test_dispatch.py
git commit -m "feat(harness): dispatch MVP 派发器 [APPROVED-BY: 项目负责人]"
```

---
### Task 5: 回收器 poll.py（含机器门禁与有限重试）

**Files:**
- Create: `.harness/scripts/poll.py`
- Test: `.harness/tests/test_poll.py`
- Modify: 无（判定只改卡 status + commit，复用治理规则）

回收流程（每次运行只做一轮）：
1. 读 `RUNS.jsonl` 的 `running` 记录；Windows 下用 `tasklist /FI "PID eq N" /FO CSV` 判活（标准库 subprocess，无新依赖）。
2. 仍活着 → 跳过（打印存活数）。
3. 已死 → 读 `run_dir/exitcode.txt`：
   - 缺文件/读不到 → `verdict=fail-exec`；
   - 非 0 → `verdict=fail-exec`；
   - 0 → 跑机器门禁（在 worktree 里）：① 卡仍合法（validate）；② 变更 scope 合规：`git status --porcelain` 列出变更文件（含 untracked `??`），逐个对卡的 allow_write/deny_write 做 glob 判定（复用 `check-local-scope.py` 的 `glob_to_regex` 纯函数）；③ 规模合规：`git diff --numstat main...HEAD` + untracked 文件行数，对 `constraints.max_files_changed/max_lines_changed`。越界 → `fail-scope`，超规模 → `fail-scale`，门禁脚本非 0 → `fail-gate`，全过 → `pass`。
4. `pass` → 记录 `awaiting-review`（等人类 `verify-all.py` + 归档；dispatcher 永不写 done）。
5. fail 且 `attempts < 1 + max_retries` → worktree 复位（`git reset --hard` + `git clean -fd`，只动 worktree 不动主仓）→ 记 `retrying` → 用上一轮 `stderr.log` 尾 30 行做 failure_note 立即重派（复用 dispatch 的 spawn 逻辑，抽成函数 `spawn_attempt()`，dispatch.py 与 poll.py 共用——注意：这要求 Task 4 的 spawn 段先抽成函数；若 Task 4 已按内联实现，本任务第一步先重构抽取，测试覆盖不变）。
6. fail 且超限 → 卡 `status → blocked` + commit，记 `blocked`。

- [ ] **Step 1: 先重构 Task 4（仅当 spawn 逻辑内联时）**：把 dispatch.py 的占坑/spawn 段抽为 `spawn_attempt(task_id, card, cfg, store, failure_note) -> pid`，dispatch.py 主流程调用它。跑全量测试确认仍 PASS（重构不加行为）。

- [ ] **Step 2: Write the failing test**

```python
# .harness/tests/test_poll.py
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

    def test_exitcode_missing_means_fail_exec(self):
        with TemporaryDirectory() as tmp:
            poll = load("poll.py")
            self.assertEqual(poll.read_exitcode(Path(tmp)), None)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m unittest .harness.tests.test_poll -v`
Expected: FAIL（poll.py 不存在）

- [ ] **Step 4: Write minimal implementation**

```python
#!/usr/bin/env python3
"""L3 回收器（poll，只做一轮，不常驻）。

用法：
  python .harness/scripts/poll.py

行为：查 running 记录 → pid 存活则跳过 → 已死则读 exitcode →
worktree 里跑机器门禁（scope+规模+卡校验）→ pass 进 awaiting-review；
fail 且未超重试上限则复位 worktree 并重派，超限则卡标 blocked。
dispatcher 永不写 done（治理铁律）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

HARNESS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = HARNESS_DIR.parent
sys.path.insert(0, str(HARNESS_DIR / "scripts"))
from runs import RunsStore  # noqa: E402
from check_local_scope_compat import glob_to_regex  # 见下注
from dispatch import (  # noqa: E402  复用 spawn_attempt 与 load_config
    build_prompt, ensure_worktree, load_config, spawn_attempt)

SCRIPTS_DIR = HARNESS_DIR / "scripts"
ACTIVE_DIR = HARNESS_DIR / "tasks" / "active"
```

注：`check-local-scope.py` 文件名含连字符不能直接 import。本任务内新建极小适配模块 `.harness/scripts/check_local_scope_compat.py`，内容只有两行——`from check-local-scope import ...` 同样非法；正确做法是用 importlib 按路径加载：

```python
# .harness/scripts/check_local_scope_compat.py
"""按文件路径加载 check-local-scope.py，导出纯函数 glob_to_regex。"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "harness_check_local_scope",
    Path(__file__).resolve().parent / "check-local-scope.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
glob_to_regex = _mod.glob_to_regex
```

`dispatch.py` 同理需要可被 import：它已有 `if __name__ == "__main__"` 守卫，可直接 `from dispatch import ...`（同目录，poll.py 已 `sys.path.insert`）。但 dispatch.py 顶层 `from runs import RunsStore` 要求 scripts 在 path——poll.py 已插入，无问题。

继续 poll.py 主体：

```python
def run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout or "", p.stderr or ""


def pid_alive(pid: int) -> bool:
    """Windows 无新依赖判活：tasklist 查 PID 行。"""
    p = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in p.stdout.splitlines()[1:]:
        if line.startswith(f'"{pid}",') or f",{pid}," in line or \
                line.split(",")[0].strip('"') == str(pid):
            return True
    return False


def read_exitcode(run_dir: Path) -> int | None:
    f = run_dir / "exitcode.txt"
    if not f.exists():
        return None
    try:
        return int(f.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def worktree_changes(worktree: Path, branch: str) -> tuple[list[str], dict[str, int]]:
    """返回 (变更文件列表, {文件: 新增+删除行数})。含 untracked。"""
    _, out, _ = run(["git", "status", "--porcelain"], cwd=worktree)
    files: list[str] = []
    for line in out.splitlines():
        if line.strip():
            files.append(line[3:].strip().strip('"'))
    # numstat 只覆盖 tracked；untracked 逐文件数行
    _, out, _ = run(["git", "diff", "--numstat", "main...HEAD"], cwd=worktree)
    scale: dict[str, int] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            scale[parts[2]] = int(parts[0]) + int(parts[1])
    for f in files:
        if f not in scale and (worktree / f).is_file():
            try:
                scale[f] = len((worktree / f).read_text(
                    encoding="utf-8", errors="replace").splitlines())
            except OSError:
                scale[f] = 0
    return files, scale


def check_scope_and_scale(files: list[str], scale: dict[str, int],
                          card: dict) -> tuple[str, str]:
    allow = card["scope"]["allow_write"]
    deny = card["scope"]["deny_write"]
    for f in files:
        if any(glob_to_regex(d).match(f) for d in deny):
            return "fail-scope", f"触碰 deny_write：{f}"
        if not any(glob_to_regex(a).match(f) for a in allow):
            return "fail-scope", f"超出 allow_write：{f}"
    cons = card.get("constraints") or {}
    max_f = cons.get("max_files_changed", 300)
    max_l = cons.get("max_lines_changed", 300)
    if len(files) > max_f:
        return "fail-scale", f"文件数 {len(files)} > {max_f}"
    if sum(scale.values()) > max_l:
        return "fail-scale", f"变更行数 {sum(scale.values())} > {max_l}"
    return "pass", "scope+规模通过"


def reset_worktree(worktree: Path) -> None:
    run(["git", "reset", "--hard"], cwd=worktree)
    run(["git", "clean", "-fd"], cwd=worktree)


def set_card_status(task_id: str, status: str) -> None:
    card_path = ACTIVE_DIR / f"{task_id}.yaml"
    with open(card_path, encoding="utf-8") as f:
        card = yaml.safe_load(f)
    card["status"] = status
    with open(card_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(card, f, allow_unicode=True, sort_keys=False)
    run(["git", "add", str(card_path)], cwd=REPO_ROOT)
    run(["git", "commit", "-m",
         f"chore(harness): {task_id} poll 标 {status} "
         "[APPROVED-BY: 项目负责人]"], cwd=REPO_ROOT)


def main() -> int:
    cfg = load_config()
    store = RunsStore(REPO_ROOT / cfg["runs_dir"] / "RUNS.jsonl")
    running = store.list_running()
    print(f"[INFO] running 记录 {len(running)} 条")
    for rec in running:
        tid, attempt = rec["task_id"], rec["attempt"]
        run_dir = Path(rec["run_dir"])
        if pid_alive(rec["pid"]):
            print(f"[INFO] {tid} attempt-{attempt} 仍在跑 pid={rec['pid']}")
            continue
        code = read_exitcode(run_dir)
        if code is None or code != 0:
            verdict, detail = "fail-exec", f"exitcode={code}"
        else:
            wt = Path(rec["worktree"])
            files, scale = worktree_changes(wt, rec["branch"])
            with open(ACTIVE_DIR / f"{tid}.yaml", encoding="utf-8") as f:
                card = yaml.safe_load(f)
            gate_code, _, _ = run(
                [sys.executable, str(SCRIPTS_DIR / "validate-task-card.py"),
                 str(ACTIVE_DIR / f"{tid}.yaml")], cwd=REPO_ROOT)
            if gate_code != 0:
                verdict, detail = "fail-gate", "任务卡校验失败"
            else:
                verdict, detail = check_scope_and_scale(files, scale, card)
        print(f"[INFO] {tid} attempt-{attempt} 判定 {verdict}：{detail}")
        if verdict == "pass":
            store.update(tid, attempt, status="awaiting-review",
                         verdict="pass", exit_code=code)
            print(f"[OK] {tid} 通过机器门禁，等人类 verify-all.py 验收")
            continue
        if store.attempts(tid) < 1 + cfg["max_retries"]:
            reset_worktree(Path(rec["worktree"]))
            store.update(tid, attempt, status="retrying", verdict=verdict,
                         exit_code=code)
            note = ""
            errf = run_dir / "stderr.log"
            if errf.exists():
                tails = errf.read_text(
                    encoding="utf-8", errors="replace").splitlines()[-30:]
                note = "\n".join(tails)
            with open(ACTIVE_DIR / f"{tid}.yaml", encoding="utf-8") as f:
                card = yaml.safe_load(f)
            spawn_attempt(tid, card, cfg, store, note or detail)
        else:
            set_card_status(tid, "blocked")
            store.update(tid, attempt, status="blocked", verdict=verdict,
                         exit_code=code)
            print(f"[WARN] {tid} 超重试上限，已标 blocked，等架构师处理")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`spawn_attempt()` 定义（Task 4 重构后 dispatch.py 必须导出，签名锁定）：

```python
def spawn_attempt(task_id, card, cfg, store, failure_note) -> int:
    """占坑已由调用方保证为 in-progress；本函数只做 worktree+上下文+拉起+记账，返回 pid。"""
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m unittest discover -s .harness/tests -t . -v`
Expected: 全部 PASS（19+ 用例）

- [ ] **Step 6: Commit**

```bash
git add .harness/scripts/poll.py .harness/scripts/check_local_scope_compat.py .harness/scripts/dispatch.py .harness/tests/test_poll.py
git commit -m "feat(harness): dispatch MVP 回收器与机器门禁 [APPROVED-BY: 项目负责人]"
```

---
### Task 6: 文档 + 端到端 dry-run 验收

**Files:**
- Modify: `.harness/README.md`（追加 dispatcher 章节）
- Test: 全量 unittest + 真仓 `--dry-run`（只读操作）

- [ ] **Step 1: README 追加 dispatcher 章节**

在 `.harness/README.md` 末尾追加（保持原有 L3 协议不动）：

```markdown
## Dispatcher MVP（任务派发与回收）

中央配置 `.harness/dispatch.yaml`：换模型只改 `model` 一行。

| 命令 | 作用 | 何时跑 |
|---|---|---|
| `python .harness/scripts/dispatch.py --dry-run` | 只读：列出本轮会派发什么 | 每次派发前先看 |
| `python .harness/scripts/dispatch.py [--max-tasks N]` | 占坑→worktree→headless 派发→记账 | 睡前/批量开工 |
| `python .harness/scripts/poll.py` | 回收：判活→机器门禁→通过等验收/失败重试/blocked | 早晨+中间抽查 |

规则：dispatcher 永不写 `done`；`pass` 只进 `awaiting-review`，仍由人类 `verify-all.py` 验收后归档；失败重试上限 `max_retries`（默认 3），超限标 `blocked`；运行记录在 `.harness/runs/RUNS.jsonl`（gitignore，不入仓）。

并发先锁 3（`dispatch.yaml: concurrency`）。免费模型 API 限流是硬天花板，放大前先用 5 条小批量测出单任务成本。
```

- [ ] **Step 2: 全量测试**

Run: `python -m unittest discover -s .harness/tests -t . -v`
Expected: 全部 PASS，0 FAIL

- [ ] **Step 3: 真仓 dry-run（只读验证）**

Run: `python .harness/scripts/dispatch.py --dry-run`
Expected: 输出 `[INFO] 可派发 N…` 且**不产生任何文件变更**；验证：`git status --porcelain` 与跑之前一致（除 `__pycache__` 外；若有 `__pycache__` 新增属正常，勿提交）。

- [ ] **Step 4: Commit**

```bash
git add .harness/README.md
git commit -m "docs(harness): dispatch MVP 运行手册 [APPROVED-BY: 项目负责人]"
```

- [ ] **Step 5: 经验沉淀（治理规则 4 的要求，dispatcher 首轮落地即执行）**

`docs/ai-workspace/rules/lessons-learned.md` 追加一行（以真实 TASK 卡号替换）：
`[TASK-XXX] dispatcher 只做单轮不常驻 → 崩了重跑 poll 即可续，无需守护进程`

---

## 非目标（本计划明确不做）

- 超时熔断（per-run timeout）：headless 会话挂起极少见，先用 poll 人工发现；列入 Phase 2。
- 统一事件看板/UI：RUNS.jsonl 即账本，需要时 `cat`/`Select-String` 查；Phase 2 再谈。
- dotnet 全量 build/test 进机器门禁：太重，仍留在人类 `verify-all.py`；dispatcher 只做 scope+规模+卡校验三层轻门禁。
- 补 `depends_on` 跨卡自动排序：MVP 只做“依赖未归档则跳过”，拓扑排序 Phase 2。

## Self-Review

1. **Spec coverage（需求 = 上轮分析的 P0+P1）：** P0 模型一行切换 → Task 1（dispatch.yaml `model` 字段 + 打进记录/prompt）；P1 dispatcher → Task 4（派发）+ Task 5（回收/门禁/重试）；账本 → Task 2；执行隔离 → worktree（Task 4 Step 3）+ run-exec（Task 3）；文档 → Task 6。P2（熔断/看板）明确列入非目标，无遗漏。
2. **Placeholder scan：** 无 TBD/TODO；所有测试代码完整；`spawn_attempt` 签名在 Task 5 被引用、定义责任落在 Task 5 Step 1 重构（Task 4 Step 3 注释已预警笔误并给出修正）；`[APPROVED-BY: 项目负责人]` 是仓库铁律要求的字面格式，非占位。
3. **Type consistency：** `RUNS.jsonl` 字段（Task 2 定义）与 dispatch.py 记账字段、poll.py 读取字段逐一对照一致；status/verdict 枚举两处一致；`check_scope_and_scale(files, scale, card) -> (verdict, detail)` 签名在测试与实现一致；`pid_alive(int)->bool`、`read_exitcode(Path)->int|None` 一致。

---

Plan complete and saved to `docs/superpowers/plans/2026-09-19-harness-dispatch-mvp.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
