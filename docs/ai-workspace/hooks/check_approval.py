#!/usr/bin/env python3
"""受保护路径审批检查（散文授权作废）。

唯一依据：active 卡的 allow_write 覆盖 + 非空 approver 字段。
TASK-023 自生命周期例外：done/已归档卡只可覆盖自身卡文件的生命周期路径
（机器验收 commit / 归档 rename 自举），第三方路径仍一律不授权。
commit message 内容永不作为依据——本模块函数根本不接收 message 参数。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

PROTECTED_PATTERNS = [
    "tests/**",
    "contracts/**",
    ".harness/**",
    ".githooks/**",
    ".github/**",
    "Directory.Build.props",
    "Directory.Build.targets",
    "stryker-config.json",
]


def glob_to_regex(pattern: str) -> re.Pattern:
    p = re.escape(pattern)
    p = p.replace(r"\*\*/", r"(?:.*/)?")
    p = p.replace(r"\*\*", r".*")
    p = p.replace(r"\*", r"[^/]*")
    p = p.replace(r"\?", r"[^/]")
    return re.compile(f"^{p}$")


def match_any(path: str, patterns) -> bool:
    return any(glob_to_regex(p).match(path) for p in (patterns or []))


def is_protected(path: str) -> bool:
    return match_any(path, PROTECTED_PATTERNS)


def _card_approver(card: dict) -> str:
    approver = card.get("approver", "")
    if approver is None:
        return ""
    if not isinstance(approver, str):
        approver = str(approver)
    return approver.strip()


def _iter_cards(cards_dir: Path):
    if not cards_dir.is_dir():
        return
    for card_path in sorted(cards_dir.glob("TASK-*.yaml")):
        try:
            with open(card_path, encoding="utf-8") as f:
                card = yaml.safe_load(f)
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(card, dict):
            continue
        yield card_path, card


def _card_status_ok(card: dict) -> bool:
    """卡 status 必须在 ready/in-progress（其余一律不授权）。"""
    return (card.get("status") or "") in ("ready", "in-progress")


def _card_globs(card: dict, field: str) -> list:
    scope = card.get("scope") or {}
    globs = scope.get(field) or []
    if not isinstance(globs, list):
        return []
    return [str(g) for g in globs]


def _lifecycle_covers(f: str, cards_dir: Path) -> bool:
    """TASK-023 自生命周期规则。

    done/已归档卡只可覆盖「自己的卡文件」生命周期路径（卡文件提交、归档改名），
    用于机器验收 commit（pipeline accept done）与归档 rename commit 的自举。
    约束（保护范围不削弱）：
      - f 必须是 active/archive 目录下、按该卡 id 命名的卡文件；
      - 卡必须有非空 approver（人工签发，D2 禁止自动补填）；
      - deny_write 命中 f 即不覆盖（deny 优先）；
      - 自覆盖：allow_write 直接覆盖 f（active 侧），或 allow_write 某条目的
        basename == 卡文件 basename（签发时自覆盖的证据，basename 跨
        active→archive 移动稳定；archive 侧用）；
      - 第三方路径：done/已归档卡一律不覆盖（主判定仍只认 ready/in-progress）。
    """
    base = f.split("/")[-1]
    m = re.match(r"^(TASK-\d{3,})(-.+)?\.yaml$", base)
    if not m:
        return False
    task_id = m.group(1)
    fdir = f.split("/")[-2] if "/" in f else ""
    valid_dirs = {cards_dir.name, "archive"}
    if fdir not in valid_dirs:
        return False

    candidates = []
    for _, card in _iter_cards(cards_dir):
        if str(card.get("id", "")).strip() == task_id and (card.get("status") or "") == "done":
            candidates.append(card)
    for _, card in _iter_cards(cards_dir.parent / "archive"):
        if str(card.get("id", "")).strip() == task_id:
            candidates.append(card)

    for card in candidates:
        if match_any(f, _card_globs(card, "deny_write")):
            continue
        allow = _card_globs(card, "allow_write")
        self_signed = any(
            str(p).rsplit("/", 1)[-1] == base for p in allow
        )
        if (match_any(f, allow) or self_signed) and _card_approver(card):
            return True
    return False


def is_approved(staged_files: list[str], cards_dir: Path) -> tuple[bool, str]:
    """判定 staged 文件是否获批。

    - 未触碰受保护集合 -> (True, ...)。
    - 每个触碰受保护集合的文件，必须存在一张 active 卡：
      其 allow_write 覆盖该文件（glob 语义，** 递归）且卡有非空 approver，
      且卡 status 为 ready/in-progress，且该文件未命中该卡 deny_write
      （deny 优先：命中则该卡不覆盖）。
    - TASK-023 自生命周期例外：done/已归档卡可覆盖其自身卡文件的生命周期
      路径（active/archive 下按该卡 id 命名的文件），仍需非空 approver +
      自覆盖 allow_write + deny 优先；第三方路径一律不覆盖。
    - 否则 (False, ...)。commit message 永不作为依据（无此参数）。
    - TASK-024 C3：返回消息一律 ASCII（AGENTS 规则 4；不改判定语义）。
    """
    protected_hits = [f for f in (staged_files or []) if is_protected(f)]
    if not protected_hits:
        return True, "[OK] no protected path touched"
    cards = list(_iter_cards(Path(cards_dir)))
    uncovered = []
    for f in protected_hits:
        covered = False
        for _, card in cards:
            if not _card_status_ok(card):
                continue
            scope = card.get("scope") or {}
            allow = scope.get("allow_write") or []
            deny = scope.get("deny_write") or []
            if match_any(f, deny):
                continue
            if match_any(f, allow) and _card_approver(card):
                covered = True
                break
        if not covered and _lifecycle_covers(f, cards_dir):
            covered = True
        if not covered:
            uncovered.append(f)
    if uncovered:
        detail = " ".join(uncovered)
        return False, (
            "[FAIL] protected path touched, but no covering active card "
            "(non-empty approver field): " + detail
        )
    return True, "[OK] protected path covered by active card approval"


def _default_cards_dir() -> Path:
    # TASK-048: git-common-dir 主树锚点（ADR-006/缺陷 B）——worktree 提交读
    # 主树实时卡，而非分支快照卡。git 不可用时退回相对路径（行为同旧）。
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, check=True, encoding="utf-8",
        )
        common = Path(r.stdout.strip()).resolve()
        root = common.parent if common.name == ".git" else common.parent
        return root / ".harness" / "tasks" / "active"
    except (subprocess.CalledProcessError, OSError, ValueError):
        return Path(".harness") / "tasks" / "active"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true",
                        help="检查 git staged 文件")
    parser.add_argument("--cards-dir", default=None, help="active 卡目录覆盖")
    parser.add_argument("files", nargs="*", help="直接传入文件列表")
    args = parser.parse_args(argv)
    cards_dir = Path(args.cards_dir) if args.cards_dir else _default_cards_dir()
    if args.staged:
        r = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, check=True, encoding="utf-8",
        )
        staged = [f for f in r.stdout.strip().split("\n") if f]
    else:
        staged = args.files
    ok, msg = is_approved(staged, cards_dir)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
