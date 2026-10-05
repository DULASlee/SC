#!/usr/bin/env python3
"""L2 任务归属：单一事实源（TASK-045, v1.1 §7/§13 + A3 三硬语义）。

存储：<runs>/ownership/<TASK>.json —— 取代并吸收 TASK-042 的 sessions/
登记簿（v1.1 §7.1"单一权威"：同一映射不得两处存）。

三条硬语义（A3，施工不得偏离）：
1. ownership 键 = TaskId（不是 attempt）；
2. 同任务 attempt 重试链合法复用同一 owner session（claim 幂等）；
3. OwnerSession 变更仅发生在任务释放（blocked / awaiting-review / done）后。

权限规则（§7.1）：claim 仅当无主；写状态/释放仅 owner；读人人可；
执行仅 owner。冲突必须拒绝（不是 warning）。

全部复合操作在 coord 临界区内完成（claim 的"读→验无主→写"原子）；
本模块不 import dispatch/poll（避免环依赖），runs 路径由调用方给出。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from coord import critical_section  # noqa: E402

STATE_CLAIMED = "claimed"
STATE_RELEASED = "released"


class OwnershipConflict(RuntimeError):
    """claim 冲突：已有主且非本 session。显式拒绝语义（§7.2/§13）。"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ownership_dir(runs_dir) -> Path:
    return Path(runs_dir) / "ownership"


def _file(runs_dir, task_id: str) -> Path:
    return ownership_dir(runs_dir) / f"{task_id}.json"


def _load(runs_dir, task_id: str) -> dict | None:
    f = _file(runs_dir, task_id)
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write(runs_dir, task_id: str, rec: dict) -> None:
    f = _file(runs_dir, task_id)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    os.replace(tmp, f)


def current(runs_dir, task_id: str) -> dict | None:
    """读：人人可（§7.1）。返回 None = 从未有主。"""
    return _load(runs_dir, task_id)


def claim(runs_dir, task_id: str, session_id: str, worktree: str,
          timeout: float = 300.0) -> dict:
    """claim 仅当无主；同 session 幂等（A3-2 重试链复用）。

    复合"读→验→写"整体进 coord 临界区；冲突抛 OwnershipConflict（拒绝语义）。
    """
    with critical_section(runs_dir, timeout):
        cur = _load(runs_dir, task_id)
        wt = str(Path(worktree).resolve()).replace("\\", "/")
        if cur and cur.get("state") == STATE_CLAIMED:
            if cur.get("owner_session_id") == session_id:
                cur["owner_worktree"] = wt  # 幂等刷新（同 session 合法重入）
                cur["refreshed_at"] = _now()
                _write(runs_dir, task_id, cur)
                return cur
            raise OwnershipConflict(
                f"{task_id} owned by session {cur.get('owner_session_id')}"
                f" (worktree={cur.get('owner_worktree')}) — claim rejected")
        rec = {
            "task_id": task_id,
            "owner_session_id": session_id,
            "owner_worktree": wt,
            "state": STATE_CLAIMED,
            "claimed_at": _now(),
            "released_at": None,
        }
        _write(runs_dir, task_id, rec)
        return rec


def release(runs_dir, task_id: str, session_id: str,
            timeout: float = 300.0) -> dict:
    """释放仅 owner（A3-3：释放后 session 方可更替）。非 owner 拒绝。"""
    with critical_section(runs_dir, timeout):
        cur = _load(runs_dir, task_id)
        if not cur:
            raise OwnershipConflict(f"{task_id} 无 ownership 记录，无可释放")
        if cur.get("state") == STATE_RELEASED:
            return cur
        if cur.get("owner_session_id") != session_id:
            raise OwnershipConflict(
                f"{task_id} release rejected: caller={session_id} "
                f"owner={cur.get('owner_session_id')}")
        cur["state"] = STATE_RELEASED
        cur["released_at"] = _now()
        _write(runs_dir, task_id, cur)
        return cur


def force_release(runs_dir, task_id: str, reason: str,
                  timeout: float = 300.0) -> dict | None:
    """任务终态/崩溃恢复路径的释放（poll/GC 专用：任务离开活动链即无主）。
    与 release 的区别：不要求 caller session——调用方必须是持有协调锁的
    回收流程（settle/GC），语义=任务已释放。返回 None=本无记录。"""
    with critical_section(runs_dir, timeout):
        cur = _load(runs_dir, task_id)
        if not cur or cur.get("state") == STATE_RELEASED:
            return cur
        cur["state"] = STATE_RELEASED
        cur["released_at"] = _now()
        cur["release_reason"] = reason
        _write(runs_dir, task_id, cur)
        return cur


def assert_writer(runs_dir, task_id: str, session_id: str) -> tuple[bool, str]:
    """写权限判定：仅 owner 可写任务状态（§7.1 Write state: only Owner）。
    无主任务 = 无人可写（需先 claim）。返回 (ok, 说明)。"""
    cur = _load(runs_dir, task_id)
    if not cur:
        return False, f"{task_id} unowned; claim first"
    if cur.get("state") != STATE_CLAIMED:
        return False, f"{task_id} not claimed (state={cur.get('state')})"
    if cur.get("owner_session_id") != session_id:
        return False, (f"{task_id} owned by {cur.get('owner_session_id')}; "
                       "non-owner write rejected")
    return True, "owner"


def worktree_owner(runs_dir, worktree) -> dict | None:
    """按 worktree 路径反查活动 owner（提交钩子的权威读取面）。"""
    want = str(Path(worktree).resolve()).replace("\\", "/").casefold()
    d = ownership_dir(runs_dir)
    if not d.is_dir():
        return None
    for f in sorted(d.glob("*.json")):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if rec.get("state") != STATE_CLAIMED:
            continue
        if str(rec.get("owner_worktree", "")).casefold() == want:
            return rec
    return None
