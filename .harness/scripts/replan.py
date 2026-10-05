#!/usr/bin/env python3
"""Phase2 重规划与 loop 病理（纯函数，无 IO）。"""

from __future__ import annotations

import hashlib
import re

ESCALATE_PREFIX = "【策略升级】同一失败连续出现，换思路重做，不要重复上一轮做法。"
BLOCKED_REASON = "同一失败签名连续3次，判 loop 病理，停派转人工"


def sig_of(verdict, exit_code, stderr_tail) -> str:
    raw = f"{verdict}|{exit_code}|{stderr_tail or ''}"
    s = raw.lower()
    s = re.sub(r"[0-9]", "#", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s[:500]
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def _trailing_run_len(history: list) -> int:
    if not history:
        return 0
    last = history[-1]
    n = 0
    for sig in reversed(history):
        if sig == last:
            n += 1
        else:
            break
    return n


def _used_escalations(history_prefix: list) -> int:
    """统计 history_prefix 内长度>=2 的段数（已用 fallback 顺位数）。"""
    runs = 0
    i = 0
    n = len(history_prefix)
    while i < n:
        j = i + 1
        while j < n and history_prefix[j] == history_prefix[i]:
            j += 1
        if (j - i) >= 2:
            runs += 1
        i = j
    return runs


FREEZE_NOTE = "fallback 就绪但 pilot 冻结，需人工批准"


def plan_retry(history, attempts_used, max_allowed, fallbacks,
               auto_fallback: bool = True) -> dict:
    hist = list(history or [])
    tail = _trailing_run_len(hist)
    if tail >= 3:
        return {
            "action": "blocked_early",
            "model_override": None,
            "note_prefix": "",
            "reason": BLOCKED_REASON,
            "model_fallback_hit": False,
        }
    if tail == 2:
        # 冻结只冻“换模型”，不冻“重试”，更不转人工队列：
        # auto_fallback=False 时一律同模型重试（model_override=None），
        # note 保留升级前缀 + 冻结说明，RUNS 照记 model_fallback_hit=False。
        if not auto_fallback:
            return {
                "action": "retry_escalated",
                "model_override": None,
                "note_prefix": f"{ESCALATE_PREFIX}{FREEZE_NOTE}",
                "reason": "同一失败连续出现第2次，fallback 就绪但 pilot 冻结",
                "model_fallback_hit": False,
            }
        fbs = list(fallbacks or [])
        used = _used_escalations(hist[:-1])
        model = fbs[used] if used < len(fbs) else None
        return {
            "action": "retry_escalated",
            "model_override": model,
            "note_prefix": ESCALATE_PREFIX,
            "reason": "同一失败连续出现第2次，策略升级重试",
            "model_fallback_hit": model is not None,
        }
    return {
        "action": "retry_same",
        "model_override": None,
        "note_prefix": "",
        "reason": "首次失败，原样重试",
        "model_fallback_hit": False,
    }
