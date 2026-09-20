#!/usr/bin/env python3
"""
L3 PR scope 检查器 v3.1

检查当前分支的所有变更是否在任务卡 allow_write 范围内，且未触碰 deny_write。

v3 修复（TASK-017）：
  1. 支持多任务卡：PR 描述中“声明为本次交付”的所有 TASK-XXX，
     allow_write 取并集、deny_write 取并集
  2. 只识别交付声明（Markdown 标题 / Closes / Refs / 任务卡 等关键词引导），
     不把正文里引用、对比、“未改动”的历史卡号当授权卡（避免其 deny 污染并集）
  3. 仅 ready/in_progress 状态的卡可作为 PR 授权卡（draft/done 显式拒绝）
  4. allow/deny 重叠不再静默判死：先判 allow，再判 deny；某文件同时命中 allow 与 deny 时
     报 [CONFIG-CONFLICT]（按铁律 deny 仍然优先、判失败），并指出需要修复任务卡
  5. 规模限制（max_lines_changed / max_files_changed）按多卡求和
  6. --task-id 支持逗号分隔多个卡

v3.1 修复（TASK-029 配套）：
  7. 任务卡按卡内容 id 字段提取稳定 TaskId，不再要求严格文件名 TASK-XXX.yaml；
     带人类可读后缀的卡（如 TASK-021-base-url-domain-error.yaml）正常命中。
     同 id 双卡并存时显式报冲突，不静默取一。

用法（在 CI 中）：
  PR_DESCRIPTION="Closes TASK-001 ..." python .harness/scripts/check-pr-scope.py --base origin/main

用法（本地）：
  python .harness/scripts/check-pr-scope.py --task-id TASK-001 --base origin/develop
  python .harness/scripts/check-pr-scope.py --task-id TASK-001,TASK-002 --base origin/main

退出码：
  0 - 通过
  1 - 越界、违规或卡配置冲突
  2 - 参数错误
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

HARNESS_DIR = Path(__file__).resolve().parent.parent
TASKS_DIR = HARNESS_DIR / "tasks" / "active"


def glob_to_regex(pattern):
    """将 glob 转为正则，支持 ** 递归匹配。"""
    p = re.escape(pattern)
    p = p.replace(r"\*\*/", r"(?:.*/)?")
    p = p.replace(r"\*\*", r".*")
    p = p.replace(r"\*", r"[^/]*")
    p = p.replace(r"\?", r"[^/]")
    return re.compile(f"^{p}$")


def match_patterns(path, patterns):
    """返回 path 命中的所有 pattern（保持传入顺序）。"""
    hits = []
    for p in patterns:
        if glob_to_regex(p).match(path):
            hits.append(p)
    return hits


def get_changed_files(base_ref):
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        capture_output=True, text=True, check=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def get_changed_lines(base_ref):
    result = subprocess.run(
        ["git", "diff", "--numstat", f"{base_ref}...HEAD"],
        capture_output=True, text=True, check=True,
    )
    total = 0
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            total += int(parts[0]) + int(parts[1])
    return total


# 整词关键词（避免匹配到 tasks/ 这类路径片段）；英文不区分大小写
DECLARATION_RE = re.compile(
    r"(?i)"
    r"(?:\bcloses?(?:d)?\b|\bfix(?:es|ed)?\b|\bresolves?(?:d)?\b"
    r"|\brefs?\b|\brelated to\b|\bdelivers?\b|\bimplements?\b"
    r"|任务卡|关联任务|交付任务|任务[：:])"
)
# Markdown 标题行（## TASK-014: ... —— 历史 PR 的标准声明格式）
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+.*?(?:TASK-\d{3,}.*)$")
NEGATION_RE = re.compile(
    r"(?i)\b(?:not|excluding|except|without|other than)\b"
    r"|未改动|未纳入|不在|不包含|排除|除外",
)


def extract_task_ids(text):
    """提取文本中“声明为本次交付”的 TASK-XXX（去重、保序）。

    v3：只认真正的交付声明，不把正文里“引用/对比/未改动”的历史卡号当授权卡，
    否则这些卡的 deny_write 会错误参与并集（如 draft TASK-001 deny .harness/**）。

    两类声明（均兼容中英）：
      1. 标题声明：Markdown 标题行中的 TASK-XXX，如 ``## TASK-014: ...``
         —— 已合并 PR #2/#3/#4/#6 的标准格式。
      2. 关键词引导：行内 ``Closes TASK-009, TASK-010`` / ``任务卡: TASK-009``，
         只取关键词之后出现的卡号（关键词之前的不算）。

    被否定/排除语境（not / excluding / 未改动 / 未纳入 / 不在）所在行不作为声明来源。
    """
    if not text:
        return []
    ids = []

    def add(m):
        if m not in ids:
            ids.append(m)

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or NEGATION_RE.search(line):
            continue
        # 1) Markdown 标题声明：取标题行内全部卡号
        if HEADING_RE.match(line):
            for m in re.findall(r"TASK-\d{3,}", line):
                add(m)
            continue
        # 2) 关键词引导：每个关键词之后到行尾的卡号
        for kw in DECLARATION_RE.finditer(line):
            for m in re.findall(r"TASK-\d{3,}", line[kw.end():]):
                add(m)
    return ids


# 只有这些状态的卡才有资格作为 PR 的授权卡
DELIVERABLE_STATUSES = {"ready", "in_progress"}


def load_task_card(task_id):
    """按卡内容 id 字段提取稳定 TaskId，查找 active 卡（v3.1，TASK-029）。

    文件名可带人类可读后缀（TASK-021-base-url-domain-error.yaml），
    以卡内 `id` 字段为唯一稳定标识；glob 仅做候选收窄，内容不符即排除。

    返回 (card | None, err | None)：
      - 恰好 1 张匹配 → (card, None)
      - 0 张 → (None, None)，由调用方报"任务卡不存在"
      - 多张同 id → (None, err)，治理缺陷显式暴露，不静默取一
    """
    matches = []
    for path in sorted(TASKS_DIR.glob(f"{task_id}*.yaml")):
        try:
            with open(path, encoding="utf-8") as f:
                card = yaml.safe_load(f)
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(card, dict):
            continue
        if str(card.get("id", "")).strip() == task_id:
            matches.append((path, card))
    if len(matches) > 1:
        names = ", ".join(p.name for p, _ in matches)
        return None, (f"active/ 下存在 {len(matches)} 张同 id {task_id} 的任务卡"
                      f"（{names}），同 id 冲突需先消解")
    if not matches:
        return None, None
    return matches[0][1], None


def main():
    parser = argparse.ArgumentParser(description="L3 PR scope 检查器 v2")
    parser.add_argument("--task-id", help="显式指定任务卡 ID，支持逗号分隔多个")
    parser.add_argument("--base", default="origin/develop", help="对比的基线分支")
    args = parser.parse_args()

    # 架构师 §二 补全 3：origin/develop 可能不存在（首次 push 前 / 本地无 GitHub remote）
    # 检查 ref 是否存在；不存在则降级为 HEAD~1（仍能跑通，PR 阶段会被 GitHub Actions 覆盖）
    ref_check = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", args.base],
        capture_output=True, text=True,
    )
    if ref_check.returncode != 0:
        warn_msg = f"基线 {args.base} 不存在，降级为 HEAD~1（首次 push 前 / 本地无 GitHub remote）"
        print(f"[WARN] {warn_msg}")
        if args.base == "origin/develop":
            args.base = "HEAD~1"

    # 1. 确定任务 ID 列表
    if args.task_id:
        task_ids = [t.strip() for t in args.task_id.split(",") if t.strip()]
    else:
        task_ids = extract_task_ids(os.environ.get("PR_DESCRIPTION", ""))
    if not task_ids:
        print("[FAIL] 未找到 TASK-XXX。请在 PR 描述中写 'Closes TASK-XXX' 或用 --task-id 指定。")
        sys.exit(1)
    print(f"[INFO] Task IDs: {', '.join(task_ids)}")

    # 2. 加载任务卡（缺失即失败，不静默跳过；非交付状态的卡不能作为 PR 授权卡）
    cards = []
    for tid in task_ids:
        card, card_err = load_task_card(tid)
        if card_err:
            print(f"[FAIL] {card_err}")
            sys.exit(1)
        if not card:
            print(f"[FAIL] 任务卡不存在：.harness/tasks/active/ 下无 id 为 {tid} 的卡"
                  f"（按 id 字段查找，文件名可带后缀）")
            sys.exit(1)
        status = str(card.get("status", "")).strip().lower()
        if status not in DELIVERABLE_STATUSES:
            print(
                f"[FAIL] 任务卡 {tid} 状态为 '{status or '未知'}'，"
                f"不能作为 PR 授权卡（仅 {'/'.join(sorted(DELIVERABLE_STATUSES))} 可声明）。"
                "正文中引用历史卡请使用普通叙述，不要用 '## TASK-XXX' 标题或 "
                "Closes/Refs/任务卡 等交付声明。"
            )
            sys.exit(1)
        cards.append(card)

    # 3. 合并 scope：allow / deny 取并集（记录 pattern 归属卡，用于报错信息）
    allow = []
    deny = []
    allow_owner = {}
    deny_owner = {}
    for card in cards:
        tid = str(card.get("id", "?"))
        for p in card["scope"]["allow_write"]:
            if p not in allow:
                allow.append(p)
                allow_owner[p] = tid
        for p in card["scope"]["deny_write"]:
            if p not in deny:
                deny.append(p)
                deny_owner[p] = tid

    # 规模限制按多卡求和（多卡 PR 合理共享总预算）
    max_lines = 0
    max_files = 0
    for card in cards:
        constraints = card.get("constraints") or {}
        max_lines += constraints.get("max_lines_changed", 300)
        max_files += constraints.get("max_files_changed", 10)

    # 4. 获取变更
    try:
        changed_files = get_changed_files(args.base)
        changed_lines = get_changed_lines(args.base)
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] git diff 失败：{e.stderr if e.stderr else e}")
        sys.exit(1)

    if not changed_files:
        print("[WARN] 无变更文件")
        sys.exit(0)

    # 5. 逐文件检查：先 allow，后 deny（deny 仍优先，但重叠必须显式暴露）
    violations = []
    conflicts = []
    for f in changed_files:
        allow_hits = match_patterns(f, allow)
        deny_hits = match_patterns(f, deny)
        if deny_hits:
            if allow_hits:
                conflicts.append(
                    f"[CONFIG-CONFLICT] {f} 同时命中 "
                    f"allow({allow_owner[allow_hits[0]]}: {allow_hits[0]}) 与 "
                    f"deny({deny_owner[deny_hits[0]]}: {deny_hits[0]})；"
                    f"按铁律 deny 优先判失败。请修复任务卡消除 allow/deny 重叠"
                )
            else:
                violations.append(
                    f"[DENY] {f} 触碰了 deny_write({deny_owner[deny_hits[0]]}: {deny_hits[0]})"
                )
        elif not allow_hits:
            violations.append(f"[OUT-OF-SCOPE] {f} 不在 allow_write 范围内")

    if conflicts:
        print(f"\n[FAIL] 发现 {len(conflicts)} 处任务卡 allow/deny 配置冲突：")
        for c in conflicts:
            print(f"  - {c}")
    if violations:
        print(f"\n[FAIL] 发现 {len(violations)} 处 scope 违规：")
        for v in violations:
            print(f"  - {v}")
    if conflicts or violations:
        print("\n修复方式：将变更限制在任务卡 allow_write 范围内，或申请新任务卡。")
        sys.exit(1)

    # 6. 检查规模
    if len(changed_files) > max_files:
        print(f"[FAIL] 文件数 {len(changed_files)} 超过限制 {max_files}（各卡 constraints 求和）。请拆分任务。")
        sys.exit(1)
    if changed_lines > max_lines:
        print(f"[FAIL] 变更行数 {changed_lines} 超过限制 {max_lines}（各卡 constraints 求和）。请拆分任务。")
        sys.exit(1)

    print(f"[OK] scope 检查通过：{len(task_ids)} 张卡，{len(changed_files)} 文件，{changed_lines} 行变更")
    sys.exit(0)


if __name__ == "__main__":
    main()
