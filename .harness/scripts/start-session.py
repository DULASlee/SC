#!/usr/bin/env python3
"""L0 手工会话入口（TASK-042）：start-session = ensure_worktree + 上下文 + 登记。

用法：
  python .harness/scripts/start-session.py TASK-XXX [--owner NAME] [--no-context]
  python .harness/scripts/start-session.py TASK-XXX --release

复用 dispatch.py 的 ensure_worktree（不另起第二套 worktree 生命周期，
v1.1 Rule 3）；归属/登记统一走 ownership.py（TASK-045 起为唯一事实源，
本脚本原 sessions/ 登记簿被其吸收）。主树定位一律用 git-common-dir 锚点
——脚本在 worktree 内副本运行时也必须写主树登记簿（P0 缺陷 B 的修复面）。
claim 序（v1.1 §13）：持锁→读卡→验无主→写 in-progress→commit→记 ownership。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HARNESS_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = HARNESS_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import ownership  # noqa: E402
from dispatch import commit_card_status, ensure_worktree, load_card  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main_root(cwd: Path | None = None) -> Path:
    """主树 = git-common-dir 的父目录（worktree 内调用同样正确）。"""
    p = subprocess.run(["git", "rev-parse", "--git-common-dir"],
                       cwd=str(cwd or Path.cwd()), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(f"git rev-parse --git-common-dir 失败：{p.stderr.strip()}")
    common = Path(p.stdout.strip()).resolve()
    return common.parent if common.name == ".git" else common.parent


def _norm(p) -> str:
    return str(Path(p).resolve()).replace("\\", "/").casefold()


def _load_cfg(root: Path) -> dict:
    """dispatch.yaml of the GIVEN root (fixture-safe: never reads the
    caller-process tree's config implicitly)."""
    import yaml
    with open(Path(root).resolve() / ".harness" / "dispatch.yaml",
              encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    for k in ("worktree_root", "runs_dir"):
        if not cfg or k not in cfg:
            raise RuntimeError(f"dispatch.yaml 缺字段：{k}")
    return cfg


def _session_id(owner: str) -> str:
    return f"manual:{owner}"


def create_session(root: Path, task_id: str, owner: str = "manual",
                   with_context: bool = True, claim_card: bool = True) -> dict:
    """claim 序（v1.1 §13）：读卡→验无主(ownership.claim 持锁)→写 in-progress
    →commit；任一步失败回滚已持 claim。"""
    root = Path(root).resolve()
    cfg = _load_cfg(root)
    card = root / ".harness" / "tasks" / "active" / f"{task_id}.yaml"
    if not card.exists():
        raise RuntimeError(f"任务卡不存在：{card}")
    status = (load_card(card).get("status") or "")
    runs_dir = (root / cfg["runs_dir"]).resolve()
    sid = _session_id(owner)
    if status not in ("ready", "in-progress"):
        raise RuntimeError(
            f"{task_id} status={status!r}，不可领取（仅 ready/in-progress）")
    if status == "in-progress":
        cur = ownership.current(runs_dir, task_id)
        if not (cur and cur.get("state") == ownership.STATE_CLAIMED
                and cur.get("owner_session_id") == sid):
            raise RuntimeError(
                f"{task_id} in-progress 且非本会话持有——拒绝接管"
                "（§7.2 防双目录执行同一任务；遗留占坑请人工释放/复位后领取）")
    wt = ensure_worktree(task_id, root, (root / cfg["worktree_root"]).resolve())
    try:
        rec = ownership.claim(runs_dir, task_id, sid, wt)
    except ownership.OwnershipConflict as exc:
        raise RuntimeError(
            f"{task_id} already claimed by another session —— 拒绝双目录执行"
            f"同一任务：{exc}")
    if status == "ready" and claim_card:
        try:
            commit_card_status(card, task_id, "in-progress",
                               "start-session claim")
        except Exception:
            ownership.release(runs_dir, task_id, sid)
            raise
    ctx_file = None
    if with_context:
        p = subprocess.run([sys.executable, str(SCRIPTS_DIR / "start-task.py"),
                            task_id], cwd=str(root), capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        if p.returncode != 0:
            raise RuntimeError(
                f"上下文生成失败（start-task.py rc={p.returncode}）："
                f"{(p.stderr or p.stdout).strip()[:300]}")
        # ctx path is relative to the tree that RAN start-task (SCRIPTS_DIR),
        # not the registration root — worktree-copy runs must not point into
        # an empty main-tree context dir.
        ctx_path = (SCRIPTS_DIR.parent / "context"
                    / f"{task_id}-context.md").resolve()
        if not ctx_path.exists():
            raise RuntimeError(f"start-task 未产出上下文：{ctx_path}")
        ctx_file = str(ctx_path).replace("\\", "/")
    reg = dict(rec)
    reg.update(context_file=ctx_file,
               registration_file=str(ownership._file(runs_dir, task_id)))
    return reg


def release_session(root: Path, task_id: str, owner: str = "manual") -> dict:
    root = Path(root).resolve()
    runs_dir = (root / _load_cfg(root)["runs_dir"]).resolve()
    return ownership.release(runs_dir, task_id, _session_id(owner))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("task_id")
    ap.add_argument("--owner", default="manual")
    ap.add_argument("--no-context", action="store_true")
    ap.add_argument("--release", action="store_true")
    args = ap.parse_args()
    try:
        root = main_root(HARNESS_DIR)
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 2
    try:
        if args.release:
            rec = release_session(root, args.task_id, owner=args.owner)
            print(f"[OK] {args.task_id} ownership 已释放（released_at="
                  f"{rec.get('released_at')}）；worktree 回收属 GC 面")
            return 0
        reg = create_session(root, args.task_id, owner=args.owner,
                             with_context=not args.no_context)
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1
    print(f"[OK] 任务已领取（owner 唯一）：task={reg['task_id']} "
          f"session={reg['owner_session_id']}")
    print(f"     worktree: {reg['owner_worktree']}")
    if reg.get("context_file"):
        print(f"     context : {reg['context_file']}")
    print(f"     归属记录 : {reg['registration_file']}")
    print(f"下一步：cd 到 worktree 后启动会话，只读上述 context。"
          f"释放：start-session.py {reg['task_id']} --owner {args.owner} --release")
    return 0


if __name__ == "__main__":
    sys.exit(main())
