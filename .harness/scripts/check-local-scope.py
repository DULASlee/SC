#!/usr/bin/env python3
"""
本地 scope 检查器（git pre-commit 用；TASK-048 并行正确性收口）

检查 staged 变更是否在活动任务卡 allow_write 内、不触 deny_write、规模不超限。

并行语义（v1.1 §4.1/ADR-006，关闭 EXISTING-MAP 缺陷 B/C）：
- 卡目录一律解析到 git-common-dir 主树（worktree 内不再读分支快照卡）；
- worktree 提交：活动卡从 ownership 登记表反查（本 worktree 的 claimed task），
  无归属绑定时 skip+INFO（ownership 提交门已在上游拒绝此类提交，此为纵深防御）；
- 主树提交：唯一活跃卡 → 单卡判定；多活跃卡 → 逐文件并集覆盖判定
  （任一活跃卡 allow 覆盖且未命中该卡 deny 即过；无覆盖 = violation；
  规模按并集内最宽卡并 INFO 标注）；零活跃卡 → WARN skip（不锁死人）；
- 显式 --task-id 最优先。

用法：
  python .harness/scripts/check-local-scope.py
  python .harness/scripts/check-local-scope.py --task-id TASK-002

退出码：0 通过；1 越界/规模超限。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

HARNESS_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = HARNESS_DIR / "scripts"


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "").strip()[:200])
    return r.stdout.strip()


def main_root() -> Path | None:
    """git-common-dir 锚点：worktree 与主树都回到主树（ADR-006）。"""
    try:
        common = Path(_git("rev-parse", "--git-common-dir")).resolve()
    except Exception:
        return None
    return common.parent if common.name == ".git" else common.parent


def tasks_dir() -> Path:
    root = main_root()
    if root is not None:
        return root / ".harness" / "tasks" / "active"
    return HARNESS_DIR / "tasks" / "active"


def toplevel() -> Path | None:
    try:
        return Path(_git("rev-parse", "--show-toplevel")).resolve()
    except Exception:
        return None


def ownership_card_for_worktree(wt: Path) -> str | None:
    """主树 ownership 登记簿反查本 worktree 的 claimed task（软依赖：
    模块/登记缺失返回 None，本检查器保持可独立运行）。"""
    root = main_root()
    if root is None:
        return None
    try:
        sys.path.insert(0, str(SCRIPTS_DIR))
        import ownership
        rec = ownership.worktree_owner(
            root / ".harness" / "runs", wt)
        return str(rec["task_id"]) if rec else None
    except Exception:
        return None


def glob_to_regex(pattern: str) -> re.Pattern:
    p = re.escape(pattern)
    p = p.replace(r"\*\*/", r"(?:.*/)?")
    p = p.replace(r"\*\*", r".*")
    p = p.replace(r"\*", r"[^/]*")
    p = p.replace(r"\?", r"[^/]")
    return re.compile(f"^{p}$")


def match_any(path: str, patterns: list[str]) -> bool:
    return any(glob_to_regex(p).match(path) for p in patterns)


def get_staged_files() -> list[str]:
    try:
        out = _git("diff", "--cached", "--name-only")
    except RuntimeError:
        return []
    return [f for f in out.split("\n") if f]


def get_staged_lines() -> int:
    try:
        out = _git("diff", "--cached", "--numstat")
    except RuntimeError:
        return 0
    total = 0
    for line in out.split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            total += int(parts[0]) + int(parts[1])
    return total


def load_card(path: Path) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else None
    except (OSError, yaml.YAMLError):
        return None


def ready_cards(tdir: Path) -> list[tuple[Path, dict]]:
    out: list[tuple[Path, dict]] = []
    if not tdir.is_dir():
        return out
    for card in sorted(tdir.glob("TASK-*.yaml")):
        data = load_card(card)
        if data and data.get("status") in ("ready", "in-progress"):
            out.append((card, data))
    return out


def file_covered(path: str, card: dict) -> bool:
    scope = card.get("scope") or {}
    allow = [str(g) for g in (scope.get("allow_write") or [])]
    deny = [str(g) for g in (scope.get("deny_write") or [])]
    if match_any(path, deny):
        return False
    return match_any(path, allow)


def check_single(card_path: Path, card: dict) -> int:
    print(f"[INFO] using task card: {card_path.name} "
          f"(status: {card.get('status')})")
    allow = card["scope"]["allow_write"]
    deny = card["scope"]["deny_write"]
    max_lines = card.get("constraints", {}).get("max_lines_changed", 300)
    max_files = card.get("constraints", {}).get("max_files_changed", 10)

    files = get_staged_files()
    lines = get_staged_lines()
    if not files:
        print("[WARN] no staged changes")
        return 0

    violations = []
    for f in files:
        if match_any(f, deny):
            violations.append(f"[DENY] {f} touches deny_write")
        elif not match_any(f, allow):
            violations.append(f"[OUT-OF-SCOPE] {f} outside allow_write")
    if violations:
        _report(violations)
        return 1
    if len(files) > max_files:
        print(f"[FAIL] file count {len(files)} exceeds limit {max_files}")
        return 1
    if lines > max_lines:
        print(f"[FAIL] changed lines {lines} exceed limit {max_lines}")
        return 1
    print(f"[OK] scope check passed: {len(files)} file(s), {lines} line(s)")
    return 0


def check_union(cards: list[tuple[Path, dict]], note: str) -> int:
    files = get_staged_files()
    lines = get_staged_lines()
    if not files:
        print("[WARN] no staged changes")
        return 0
    print(f"[INFO] multi-card union mode ({len(cards)} active cards; {note})")
    violations = []
    for f in files:
        if not any(file_covered(f, c) for _, c in cards):
            violations.append(f"[NO-CARD-COVERAGE] {f} not in any active card")
    if violations:
        _report(violations)
        return 1
    max_files = max((c.get("constraints", {}).get("max_files_changed", 10)
                     for _, c in cards), default=10)
    max_lines = max((c.get("constraints", {}).get("max_lines_changed", 300)
                     for _, c in cards), default=300)
    if len(files) > max_files:
        print(f"[FAIL] file count {len(files)} exceeds widest-card "
              f"limit {max_files}")
        return 1
    if lines > max_lines:
        print(f"[FAIL] changed lines {lines} exceeds widest-card "
              f"limit {max_lines}")
        return 1
    print(f"[OK] scope check passed: {len(files)} file(s), {lines} line(s)")
    return 0


def _report(violations: list[str]) -> None:
    print(f"\n[FAIL] {len(violations)} scope violation(s):")
    for v in violations:
        print(f"  - {v}")
    print("\nFix: limit changes to the card allow_write, or open a new task card.")
    # TASK-024 C2: 受保护路径由 commit-msg hook + check_approval.py 判定
    # （覆盖卡 allow_write + 非空 approver）；SKIP_PROTECTED_CHECK 为架构师通道。
    print("Note: protected paths (.github/, tests/, .harness/, ...) are "
          "enforced by the commit-msg hook + check_approval.py: an active "
          "card whose allow_write covers the file with a non-empty approver "
          "field, or architect sets SKIP_PROTECTED_CHECK=1.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", help="显式指定任务卡 ID")
    args = parser.parse_args()

    tdir = tasks_dir()

    if args.task_id:
        card_path = tdir / f"{args.task_id}.yaml"
        card = load_card(card_path)
        if card is None:
            print(f"[FAIL] task card not found: {card_path}")
            return 1
        return check_single(card_path, card)

    root = main_root()
    top = toplevel()
    if root is not None and top is not None and top != root:
        # worktree 提交：归属反查（无归属=跳过，上游 ownership 门已拒）
        tid = ownership_card_for_worktree(top)
        if tid is None:
            print("[INFO] worktree commit with no ownership binding; scope "
                  "check skipped (ownership gate rejects such commits upstream)")
            return 0
        card_path = tdir / f"{tid}.yaml"
        card = load_card(card_path)
        if card is None:
            print(f"[WARN] ownership points to missing card {tid}; skip")
            return 0
        return check_single(card_path, card)

    cards = ready_cards(tdir)
    if len(cards) == 0:
        print("[WARN] no active task card (0 ready/in-progress), "
              "skipping scope check")
        print("       for business code commits pass --task-id TASK-XXX explicitly")
        return 0
    if len(cards) == 1:
        return check_single(*cards[0])
    return check_union(cards, "any-cover semantics; scale = widest card")


if __name__ == "__main__":
    sys.exit(main())
