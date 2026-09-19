#!/usr/bin/env python3
"""RUNS.jsonl 运行记录库（append-only 事件日志）。

记录字段：task_id, attempt, pid, worktree, branch, run_dir, model, executor,
status, started_at, finished_at, exit_code, verdict,
stage, owner, sig_history, prev_model, model_swapped。
status ∈ {running, spawning, awaiting-review, retrying, blocked, error,
done-stage, pr-open, pr-manual}
verdict ∈ {none, pass, fail-exec, fail-skill, fail-scope, fail-scale,
fail-gate}
"""

from __future__ import annotations

import json
import os
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
        full = {
            "status": "running", "started_at": _now(), "finished_at": None,
            "exit_code": None, "verdict": "none",
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

    def attempts(self, task_id: str) -> int:
        return sum(1 for r in self._read_all() if r["task_id"] == task_id)
