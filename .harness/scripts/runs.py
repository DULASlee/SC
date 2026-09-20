#!/usr/bin/env python3
"""RUNS.jsonl 运行记录库（append-only 事件日志）。

记录字段：task_id, attempt, pid, worktree, branch, run_dir, model, executor,
status, started_at, finished_at, exit_code, verdict, upstream_fault,
upstream_streak, stage, owner, sig_history, prev_model, model_swapped。
status ∈ {running, spawning, awaiting-review, retrying, blocked, error,
done-stage, pr-open, pr-manual}
verdict ∈ {none, pass, fail-exec, fail-skill, fail-scope, fail-scale,
fail-gate}
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from coord import critical_section, is_held, touch  # noqa: E402  (同目录协调锁)


class _NullSection:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunsStore:
    """追加式账本。lock_dir 非空时：单条写自动进协调临界区（B5：含
    append 路径）；复合"读→检查→写"须由调用方 with store.critical_section()
    显式包裹（同线程可重入，不双锁）。"""

    def __init__(self, path: Path, lock_dir: Path | None = None):
        self.path = Path(path)
        self.lock_dir = Path(lock_dir) if lock_dir is not None else None
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def critical_section(self, timeout: float = 120.0):
        """复合原子块入口；无锁配置时为空操作。"""
        if self.lock_dir is None:
            return _NullSection()
        return critical_section(self.lock_dir, timeout)

    def _guard(self):
        """写操作自保护：外层已持锁则刷新 mtime 后放行（心跳），否则独立临界区。"""
        if self.lock_dir is None:
            return _NullSection()
        if is_held(self.lock_dir):
            touch(self.lock_dir)
            return _NullSection()
        return critical_section(self.lock_dir)

    def _read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        recs = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                recs.append(json.loads(line))
        return recs

    def _write_all(self, recs: list[dict]) -> None:
        # 原子重写：先写临时文件并 fsync，再 os.replace 覆盖，消除
        # "文件被截断但未写回" 的崩溃窗口（保护"重跑 poll 即可续"承诺）。
        tmp = self.path.with_name(self.path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def append(self, rec: dict) -> dict:
        with self._guard():
            return self._append_inner(rec)

    def _append_inner(self, rec: dict) -> dict:
        full = {
            "status": "running", "started_at": _now(), "finished_at": None,
            "exit_code": None, "verdict": "none", "upstream_fault": False,
            "upstream_streak": 0,
            "stage": "execute", "owner": "dispatch", "sig_history": [],
            "prev_model": None, "model_swapped": False,
        }
        full.update(rec)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # 真追加：单行 O(1) 写入 + fsync，崩溃最多丢最后一行且不会污染历史。
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(full, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return full

    def get(self, task_id: str, attempt: int) -> dict | None:
        for r in self._read_all():
            if r["task_id"] == task_id and r["attempt"] == attempt:
                return r
        return None

    def update(self, task_id: str, attempt: int, **fields) -> dict:
        with self._guard():
            return self._update_inner(task_id, attempt, **fields)

    def _update_inner(self, task_id: str, attempt: int, **fields) -> dict:
        recs = self._read_all()
        terminal = fields.get("status") in (
            "awaiting-review", "retrying", "blocked", "error"
        )
        found = None
        for r in recs:
            # 更新全部匹配记录，避免重复 (task_id, attempt) 时残留陈旧 running 副本
            if r["task_id"] == task_id and r["attempt"] == attempt:
                r.update(fields)
                if terminal:
                    r["finished_at"] = _now()
                if found is None:
                    found = r
        if found is None:
            raise KeyError(f"run not found: {task_id} attempt {attempt}")
        self._write_all(recs)
        return found

    def list_running(self, owner: str | None = "dispatch") -> list[dict]:
        recs = self._read_all()
        if owner is None:
            return [r for r in recs if r["status"] == "running"]
        return [r for r in recs
                if r["status"] == "running"
                and r.get("owner", "dispatch") == owner]

    def list_active(self, owner: str | None = None) -> list[dict]:
        """占额度活动记录：running + 在途 spawning（落盘未回填 pid）。
        TASK-043：槽位计数改用它，堵住"已 append 未 running 不计数"的超发窗口。
        """
        recs = self._read_all()
        out = [r for r in recs if r.get("status") in ("running", "spawning")]
        if owner is None:
            return out
        return [r for r in out if r.get("owner", "dispatch") == owner]

    def attempts(self, task_id: str) -> int:
        return sum(1 for r in self._read_all() if r["task_id"] == task_id)

    def budget_attempts(self, task_id: str) -> int:
        """预算计数：只计 upstream_fault 非真的记录数。

        上游故障（无健康上游 / provider 错误等短语命中）不消耗重试预算。
        上游连续计数另由 upstream_streak 字段跟踪（见 poll）。
        """
        return sum(1 for r in self._read_all()
                   if r["task_id"] == task_id
                   and not r.get("upstream_fault"))
