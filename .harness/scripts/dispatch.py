#!/usr/bin/env python3
"""L3 任务派发器（dispatch，只做一轮，不常驻）。

用法：
  python .harness/scripts/dispatch.py [--dry-run] [--max-tasks N]

行为：扫 ready 卡 → 占坑(in-progress+commit) → git worktree 隔离 →
start-task.py 生成上下文 → run-exec.py 拉起 headless 会话 → 记 RUNS.jsonl。
崩了重跑 poll.py 即可续，本脚本不常驻、不做守护。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

HARNESS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = HARNESS_DIR.parent
sys.path.insert(0, str(HARNESS_DIR / "scripts"))
from runs import RunsStore  # noqa: E402  (同目录库导入)
from skills import cap_text, load_skill_texts  # noqa: E402
from modelswap import (  # noqa: E402
    DEFAULT_SETTINGS, acquire_lock, read_selection, release_lock,
    split_model, swap_for_run)
from canary import is_required as canary_is_required  # noqa: E402

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
    for k in ("concurrency", "max_retries", "max_tasks_per_run"):
        if not isinstance(cfg[k], int) or cfg[k] < 1:
            print(f"[FAIL] dispatch.yaml 字段 {k} 必须为 >=1 的整数，当前：{cfg[k]!r}")
            sys.exit(2)
    cfg.setdefault("model_fallbacks", [])
    cfg.setdefault("auto_fallback", True)
    cfg.setdefault("loop_interval_seconds", 120)
    cfg.setdefault("prompt_budget",
                   {"failure_note_max_chars": 2000, "skill_max_bytes": 12288})
    cfg.setdefault("pr_enabled", False)
    cfg.setdefault("skills_dir", None)
    cfg.setdefault("dsh_settings", None)
    return cfg


def load_card(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_eligible(card: dict, repo_root: Path) -> bool:
    """ready + 依赖全部已归档（done 即归档）才可派发。"""
    if card.get("pipeline"):
        return False
    if card.get("status") != "ready":
        return False
    archive_dir = repo_root / ".harness" / "tasks" / "archive"
    for dep in card.get("depends_on") or []:
        if not (archive_dir / f"{dep}.yaml").exists():
            return False
    return True


def card_validates(card_path: Path) -> bool:
    code, out, err = run(
        [sys.executable, str(SCRIPTS_DIR / "validate-task-card.py"),
         str(card_path)], cwd=REPO_ROOT)
    if code != 0:
        # 不吞 stderr：环境故障（schema 缺失 / jsonschema 未装）≠ 卡本身非法
        tail = [l for l in (err or out).strip().splitlines()][-5:]
        print(f"[WARN] {card_path.name} 校验未通过：{' | '.join(tail)}")
    return code == 0


def resolve_model(card: dict, cfg: dict) -> str:
    """卡自带 model 优先，否则回退全局 cfg['model']。"""
    return card.get("model") or cfg["model"]


def _dsh_settings_path(cfg: dict) -> Path:
    raw = cfg.get("dsh_settings")
    return Path(raw) if raw else DEFAULT_SETTINGS


def running_count(store) -> int:
    """全量 running 计数（含 pipeline），槽位计算唯一入口。

    dispatch 默认 list_running() 只看 owner=dispatch，会漏 pipeline 占的槽；
    此处一律 owner=None 全量查询，老 store 无 owner 参数则回退无参调用。
    """
    try:
        return len(store.list_running(owner=None))
    except TypeError:
        return len(store.list_running())


def _model_aligned(card: dict, cfg: dict) -> bool:
    """无自带 model 的卡要求 DSH 现状 == 全局 model（provider+model 全比）。

    有自带 model 的卡走派发时 swap，不在此处拦截。
    """
    if card.get("model"):
        return True
    try:
        cur = read_selection(_dsh_settings_path(cfg))
    except Exception:
        cur = (None, None)
    gprov, gmodel = split_model(cfg["model"])
    return tuple(cur) == (gprov, gmodel)


def build_prompt(context_abs: Path, model: str, failure_note: str | None,
                 skills_ctx: str | None = None) -> str:
    lines = [
        f"请读取 {context_abs.as_posix()}，",
        "严格按照其中的 allow_write 范围修改代码，",
        "不要修改 deny_write 中的任何文件，",
        "不要发表'完成'声明，等待 CI 判定。",
        f"使用模型：{model}。",
    ]
    if failure_note:
        lines.append(f"上一轮失败摘要（针对性修复，不要重做已通过部分）：{failure_note}")
    if skills_ctx:
        lines.append(skills_ctx)
    return "\n".join(lines)


def write_skills_file(task_id: str, skill_names: list[str],
                      cfg: dict) -> Path | None:
    names = list(skill_names or [])
    if not names:
        return None
    if not cfg.get("skills_dir"):
        return None
    cap = cfg.get("prompt_budget", {}).get("skill_max_bytes", 12288)
    texts, truncated = load_skill_texts(names, Path(cfg["skills_dir"]), cap)
    if not texts:
        return None
    parts: list[str] = []
    for n in names:
        if n not in texts:
            continue
        flag = "（已截断，只含尾部）" if truncated.get(n) else ""
        parts.append(f"# skill: {n}{flag}\n\n{texts[n]}")
    if not parts:
        return None
    sp = HARNESS_DIR / "context" / f"{task_id}-skills.md"
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return sp


def ensure_worktree(task_id: str, repo_root: Path, wt_root: Path) -> Path:
    wt = wt_root / task_id
    if wt.exists():
        return wt
    branch = f"feat/{task_id}"
    code, _, _ = run(["git", "rev-parse", "--verify", branch], cwd=repo_root)
    if code == 0:
        rc, out, err = run(["git", "worktree", "add", str(wt), branch],
                           cwd=repo_root)
    else:
        rc, out, err = run(["git", "worktree", "add", "-b", branch, str(wt)],
                           cwd=repo_root)
    if rc != 0:
        raise RuntimeError(f"{task_id} git worktree add 失败：{err.strip()}")
    print(out.strip() or f"[OK] worktree 就绪：{wt}")
    return wt


def is_worktree_dirty(wt: Path) -> bool:
    """worktree 是否有未提交变更（porcelain 非空即脏）。"""
    p = subprocess.run(["git", "-c", "core.quotepath=off",
                        "status", "--porcelain", "-uall"],
                       cwd=wt, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(f"worktree 状态检查失败：{(p.stderr or '').strip()[:200]}")
    return bool((p.stdout or "").strip())


def reset_worktree(wt: Path) -> None:
    """复位 worktree（只动 worktree，不碰主仓）：丢弃未提交改动。"""
    run(["git", "reset", "--hard"], cwd=wt)
    run(["git", "clean", "-fd"], cwd=wt)


def check_worktree_gate(wt: Path, task_id: str, attempt: int) -> None:
    """worktree 洁净门：脏 worktree 拒绝派发。

    重试轮（attempt>1）先 reset 再复查；仍脏（或首轮即脏）抛错拒绝，
    调用方（dispatch main / poll _settle）的既有异常处理负责记 error。
    """
    if not is_worktree_dirty(wt):
        return
    if attempt > 1:
        reset_worktree(wt)
    if is_worktree_dirty(wt):
        raise RuntimeError(f"{task_id} worktree 脏（含未提交变更），拒绝派发")


def spawn_attempt(task_id: str, card: dict, cfg: dict, store: RunsStore,
                  failure_note: str | None, prompt_override: str | None = None,
                  stage: str = "execute", model_override: str | None = None,
                  owner: str = "dispatch") -> int:
    """worktree + 上下文 + 拉起 + 记账，返回 pid。

    占坑（status→in-progress + commit）由调用方保证，本函数不改卡状态，
    使 dispatch 首轮与 poll 重试轮可共用同一套 spawn 逻辑。
    """
    attempt = store.attempts(task_id) + 1
    wt = ensure_worktree(task_id, REPO_ROOT, REPO_ROOT / cfg["worktree_root"])
    check_worktree_gate(wt, task_id, attempt)
    code, _, err = run(
        [sys.executable, str(SCRIPTS_DIR / "start-task.py"), task_id],
        cwd=REPO_ROOT)
    if code != 0:
        raise RuntimeError(f"{task_id} 上下文生成失败：{err.strip()}")
    ctx = HARNESS_DIR / "context" / f"{task_id}-context.md"
    eff = model_override or resolve_model(card, cfg)
    if failure_note:
        limit = cfg.get("prompt_budget", {}).get(
            "failure_note_max_chars", 2000)
        failure_note = cap_text(failure_note, limit)
    skill_names = card.get("skills") or []
    skills_ctx: str | None = None
    if skill_names and cfg.get("skills_dir"):
        spath = write_skills_file(task_id, skill_names, cfg)
        if spath is not None:
            skills_ctx = (f"附带的 skill 工作流（必须遵守）："
                          f"{spath.resolve().as_posix()}")
    provider, model_part = split_model(eff)
    swapped = False
    # prev_model 唯一形状：[provider, model] 二元 list（读时校验长度2）
    prev_combined: list | None = None
    if provider:
        runs_dir = REPO_ROOT / cfg["runs_dir"]
        sp = _dsh_settings_path(cfg)
        acquire_lock(runs_dir)
        try:
            prev = swap_for_run(sp, provider, model_part, runs_dir)
        finally:
            release_lock(runs_dir)
        if prev is not None:
            swapped = True
            pp, pm = prev
            prev_combined = [pp, pm]
    prompt = prompt_override or build_prompt(
        ctx.resolve(), eff, failure_note, skills_ctx)
    argv = [a.replace("{prompt}", prompt) for a in cfg["executor_argv"]]
    run_dir = REPO_ROOT / cfg["runs_dir"] / task_id / f"attempt-{attempt}"
    # 原子性：先落盘(spawning)后拉起，避免 Popen 成功但 append 前崩溃的孤儿进程
    store.append({"task_id": task_id, "attempt": attempt, "pid": None,
                  "worktree": str(wt), "branch": f"feat/{task_id}",
                  "run_dir": str(run_dir), "model": eff,
                  "model_swapped": swapped, "prev_model": prev_combined,
                  "stage": stage, "owner": owner,
                  "status": "spawning",
                  "executor": " ".join(argv[:3])})
    try:
        proc = subprocess.Popen(
            [sys.executable, str(SCRIPTS_DIR / "run-exec.py"),
             "--run-dir", str(run_dir), "--", *argv],
            cwd=wt)
    except Exception:
        try:
            store.update(task_id, attempt, status="error",
                         verdict="fail-exec")
        except KeyError:
            pass
        raise
    store.update(task_id, attempt, status="running", pid=proc.pid)
    print(f"[OK] 已派发 {task_id} attempt-{attempt} pid={proc.pid} worktree={wt}")
    return proc.pid


def _set_card_status_text(card_path: Path, status: str) -> None:
    """定向替换 `status:` 行，保留架构师手写的注释与字面量格式。"""
    text = card_path.read_text(encoding="utf-8")
    new, n = re.subn(r"(?m)^status:.*$", f"status: {status}", text)
    if n == 0:
        raise RuntimeError(f"{card_path.name} 无 status 字段，拒绝改写")
    card_path.write_text(new, encoding="utf-8")


def _glob_match(pattern: str, path: str) -> bool:
    """与 check-pr-scope.py / check_approval.py 同语义：** 递归、* 单段。"""
    p = re.escape(pattern)
    p = p.replace(r"\*\*/", r"(?:.*/)?")
    p = p.replace(r"\*\*", r".*")
    p = p.replace(r"\*", r"[^/]*")
    p = p.replace(r"\?", r"[^/]")
    return re.match(f"^{p}$", path) is not None


def card_self_authorized(card: dict, rel_path: str) -> str | None:
    """TASK-023 自覆盖契约：机器状态提交前置检查（fail-fast，可操作报错）。

    卡必须：
      - approver 非空（人工签发，D2 禁止自动补填）；
      - allow_write 覆盖自身卡文件（rel_path 为仓库相对路径）。
    通过返回 None；否则返回原因字符串。hook（check_approval）仍是权威判定，
    本检查只负责在占坑/标记/机器验收时刻给出可操作错误。
    """
    approver = str((card.get("approver") or "")).strip()
    if not approver:
        return ("approver 为空（TASK-023：机器状态提交需卡含非空 approver；"
                "D2 规定 approver 人工签发，禁止自动补填）")
    allow = ((card.get("scope") or {}).get("allow_write")) or []
    if not any(_glob_match(str(p), rel_path) for p in allow):
        return f"allow_write 未覆盖自身卡文件 {rel_path}（TASK-023 自覆盖缺失）"
    return None


def commit_card_status(card_path: Path, task_id: str, status: str,
                      verb: str) -> None:
    """把卡 status 改为给定值并单独提交。

    提交用 pathspec 限定到本卡，避免把索引里无关的暂存变更扫进带
    [APPROVED-BY] 的提交；git 失败即回滚本卡文件到 HEAD 并抛错。
    治理规则：任何卡状态变更都必须落 commit。dispatch 与 poll 共用。
    """
    # TASK-023 自覆盖契约：提交前先验卡（approver + 自覆盖），不满足即拒，
    # 避免把状态文本改掉后才在 hook 层被拒、回滚路径再失败。
    rel = card_path.relative_to(REPO_ROOT).as_posix()
    pre = card_self_authorized(load_card(card_path), rel)
    if pre:
        raise RuntimeError(f"{task_id} {verb} 拒绝：{pre}")
    _set_card_status_text(card_path, status)
    rc1, _, e1 = run(["git", "add", str(card_path)], cwd=REPO_ROOT)
    rc2, _, e2 = run(
        ["git", "commit", "-m",
         f"chore(harness): {task_id} {verb} {status} "
         "[APPROVED-BY: 项目负责人]", "--", str(card_path)], cwd=REPO_ROOT)
    if rc1 or rc2:
        run(["git", "checkout", "HEAD", "--", str(card_path)], cwd=REPO_ROOT)
        raise RuntimeError(
            f"{task_id} 状态提交失败：{(e1 or e2).strip()[:400]}")


def claim_card(card_path: Path, task_id: str) -> None:
    """占坑：卡 status → in-progress 并 commit。"""
    commit_card_status(card_path, task_id, "in-progress", "dispatch 占坑")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-tasks", type=int, default=None)
    args = ap.parse_args()

    cfg = load_config()
    # preflight ① canary 门：现状与留证任一变化即整轮拒绝派发（无逃生口）。
    try:
        canary_blocked = canary_is_required(cfg)
    except Exception as exc:  # noqa: BLE001  探针环境异常按需留证处理
        print(f"[FAIL] canary 门检查异常，拒绝派发：{exc}")
        return 2
    if canary_blocked:
        print("canary_required：先跑 canary.py 留证")
        return 0
    store = RunsStore(REPO_ROOT / cfg["runs_dir"] / "RUNS.jsonl")
    cap = cfg["max_tasks_per_run"] if args.max_tasks is None else args.max_tasks

    queue: list[tuple[Path, dict]] = []
    for card_path in sorted(ACTIVE_DIR.glob("TASK-*.yaml")):
        card = load_card(card_path)
        if not is_eligible(card, REPO_ROOT):
            continue
        if not card_validates(card_path):
            print(f"[SKIP] {card['id']} 任务卡校验失败")
            continue
        if not _model_aligned(card, cfg):
            print(f"[SKIP] {card.get('id', card_path.name)} 模型未对齐 "
                  f"fail-fast：DSH 现状与全局模型 {cfg['model']} 不一致，不派发")
            continue
        queue.append((card_path, card))

    # 同轮多模型竞态收敛：按 resolve 后模型分组，同轮只派第一组模型相同的卡。
    # DSH 在进程启动瞬间读 settings.yaml，全局 swap 方案下跨轮仍有毫秒级竞态
    # 窗口（上一轮收尾 restore 与下一轮 swap 之间）；但持锁 swap 区间仅毫秒级
    # （读 + 备份 + 原子写），且同轮内已无多模型交错，故残余窗口可接受。
    round_queue: list[tuple[Path, dict]] = queue
    if queue:
        first_model = resolve_model(queue[0][1], cfg)
        round_queue = [item for item in queue
                       if resolve_model(item[1], cfg) == first_model]
        for cp, cc in queue:
            if resolve_model(cc, cfg) != first_model:
                print(f"[SKIP] {cc.get('id', cp.name)} 本轮模型 "
                      f"{resolve_model(cc, cfg)} 与已派发组不同，顺延下轮")
    slots = cfg["concurrency"] - running_count(store)
    todo = round_queue[: max(0, min(slots, cap))]
    print(f"[INFO] 可派发 {len(queue)}，空槽 {slots}，本轮派 {len(todo)}")
    if args.dry_run:
        for _, c in todo:
            print(f"[DRY] 会派发 {c['id']}: {c['title']}")
        return 0

    dispatched = 0
    for card_path, card in todo:
        tid = card["id"]
        try:
            claim_card(card_path, tid)
        except Exception as exc:  # noqa: BLE001  占坑失败已内部回滚，跳过本卡
            print(f"[FAIL] {tid} 占坑失败，跳过：{exc}")
            continue
        try:
            spawn_attempt(tid, card, cfg, store, None)
            dispatched += 1
        except Exception as exc:  # noqa: BLE001  单任务失败不影响其余派发
            print(f"[FAIL] {tid} 派发失败，回滚占坑：{exc}")
            try:
                commit_card_status(card_path, tid, "ready", "派发失败回滚")
            except Exception as exc2:  # noqa: BLE001
                print(f"[WARN] {tid} 回滚到 ready 失败，需人工处理：{exc2}")
    print(f"[OK] 本轮派发 {dispatched} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
