#!/usr/bin/env python3
"""L0 手工会话入口（TASK-042）：start-session = ensure_worktree + 上下文 + 登记。

用法：
  python .harness/scripts/start-session.py TASK-XXX [--owner NAME] [--no-context]
  python .harness/scripts/start-session.py TASK-XXX --release

复用 dispatch.py 的 ensure_worktree（不另起第二套 worktree 生命周期，
v1.1 Rule 3）；登记簿落主树 <runs>/sessions/<TASK>.json（协调根=仓库级，
A5）。主树定位一律用 git-common-dir 锚点——脚本在 worktree 内副本运行时
也必须写主树登记簿（P0 缺陷 B 的修复面）。本卡只登记不改卡状态
（claim/ownership 属 P5，v1.1 §9 "不做"边界）。
"""
from __future__ import annotations

import argparse
import json
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
from dispatch import ensure_worktree  # noqa: E402


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


def sessions_dir(root: Path, cfg: dict) -> Path:
    return (Path(root).resolve() / cfg["runs_dir"] / "sessions").resolve()


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


def _load_reg(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def create_session(root: Path, task_id: str, owner: str = "manual",
                   with_context: bool = True) -> dict:
    root = Path(root).resolve()
    cfg = _load_cfg(root)
    card = root / ".harness" / "tasks" / "active" / f"{task_id}.yaml"
    if not card.exists():
        raise RuntimeError(f"任务卡不存在：{card}")
    import yaml
    data = yaml.safe_load(card.read_text(encoding="utf-8")) or {}
    status = data.get("status") or ""
    if status not in ("ready",):
        raise RuntimeError(
            f"{task_id} status={status!r}，非 ready，拒绝登记"
            "（in-progress 视为已被派发/他人占用——claim 冲突拒绝，P5 强化）")
    sess = sessions_dir(root, cfg)
    sess.mkdir(parents=True, exist_ok=True)
    reg_file = sess / f"{task_id}.json"
    cur = _load_reg(reg_file)
    if cur and cur.get("status") == "active":
        raise RuntimeError(
            f"{task_id} already registered active "
            f"(owner={cur.get('owner')}, worktree={cur.get('worktree')})")
    wt = ensure_worktree(task_id, root, (root / cfg["worktree_root"]).resolve())
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
    reg = {
        "task_id": task_id,
        "worktree": str(Path(wt).resolve()).replace("\\", "/"),
        "branch": f"feat/{task_id}",
        "session_id": f"{task_id}.{os.getpid()}.{_now()}",
        "owner": owner,
        "status": "active",
        "created_at": _now(),
        "released_at": None,
        "context_file": ctx_file,
        "registration_file": str(reg_file),
    }
    tmp = reg_file.with_name(reg_file.name + ".tmp")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    os.replace(tmp, reg_file)
    return reg


def release_session(root: Path, task_id: str) -> dict:
    reg_file = sessions_dir(Path(root), _load_cfg(Path(root))) / f"{task_id}.json"
    cur = _load_reg(reg_file)
    if not cur:
        raise RuntimeError(f"{task_id} 无登记，无需释放")
    if cur.get("status") != "active":
        return cur
    cur["status"] = "released"
    cur["released_at"] = _now()
    reg_file.write_text(json.dumps(cur, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    return cur


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
            reg = release_session(root, args.task_id)
            print(f"[OK] {args.task_id} 登记已释放（released_at="
                  f"{reg.get('released_at')}）；worktree 回收属 P3 gc")
            return 0
        reg = create_session(root, args.task_id, owner=args.owner,
                             with_context=not args.no_context)
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1
    print(f"[OK] 会话登记完成：task={reg['task_id']} branch={reg['branch']}")
    print(f"     worktree: {reg['worktree']}")
    if reg.get("context_file"):
        print(f"     context : {reg['context_file']}")
    print(f"     登记簿   : {reg['registration_file']}")
    print(f"下一步：cd 到 worktree 后启动会话，只读上述 context；"
          f"完工前不得在主树提交。释放：start-session.py {reg['task_id']} --release")
    return 0


if __name__ == "__main__":
    sys.exit(main())
