#!/usr/bin/env python3
"""Machine authorization policy reader (P1).

Rules (strict by default):
- path under allow -> "allow"
- path under forbid -> "forbid"
- anything else -> "escalate" (human decides)

Card level:
- any allow_write path forbidden -> "forbid"
- all allow_write paths allowed -> "allow"
- otherwise -> "escalate"
"""
from __future__ import annotations

import fnmatch
from pathlib import Path

import yaml

POLICY_FILE = Path(__file__).resolve().parent.parent / "policy.yaml"


def load_policy(path: Path | None = None) -> dict:
    p = Path(path) if path else POLICY_FILE
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {"allow": data.get("allow") or [],
            "forbid": data.get("forbid") or []}


def _hit(patterns: list[str], path: str) -> bool:
    return any(fnmatch.fnmatchcase(path, p) for p in patterns)


def action_for(path: str, policy: dict | None = None) -> str:
    pol = policy if policy is not None else load_policy()
    if _hit(pol["forbid"], path):
        return "forbid"
    if _hit(pol["allow"], path):
        return "allow"
    return "escalate"


def card_action(card: dict, policy: dict | None = None) -> str:
    pol = policy if policy is not None else load_policy()
    allow = ((card.get("scope") or {}).get("allow_write")) or []
    if any(action_for(p, pol) == "forbid" for p in allow):
        return "forbid"
    if allow and all(action_for(p, pol) == "allow" for p in allow):
        return "allow"
    return "escalate"
