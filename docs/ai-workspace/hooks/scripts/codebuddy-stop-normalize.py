#!/usr/bin/env python3
# CodeBuddy Stop hook: normalize the session transcript into the shared
# episodic-memory archive so it can be indexed across IDEs.
#
# CodeBuddy pipes a JSON doc to stdin on every Stop event:
#   {"session_id": "...", "transcript_path": "...", "cwd": "...",
#    "hook_event_name": "Stop", "generation_id": "...", "stop_hook_active": true}
#
# Phase 1 (current): capture the RAW transcript + probe its real format and
# write a best-effort normalized JSONL into the shared archive. Ingestion into
# `episodic-memory` is gated behind INGEST_TO_EPISODIC until that runtime is
# installed (it currently requires a native build of better-sqlite3).
#
# Hook output (stdout/stderr) is ASCII only. Always exits 0 so a failure here
# never blocks the user's Stop.

import json
import os
import shutil
import sys
import traceback
from datetime import datetime, timezone

ARCHIVE_BASE = "F:/JQKJ/.ai-memory/episodic"
RAW_DIR = os.path.join(ARCHIVE_BASE, "raw")
NORMALIZED_DIR = os.path.join(ARCHIVE_BASE, "normalized")
PROBE_DIR = os.path.join(ARCHIVE_BASE, "probe")
ERR_LOG = os.path.join(ARCHIVE_BASE, "hook-errors.log")

# Flip to True once `episodic-memory` is installed and format is confirmed.
INGEST_TO_EPISODIC = False


def log_err(msg):
    try:
        os.makedirs(ARCHIVE_BASE, exist_ok=True)
        with open(ERR_LOG, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (datetime.now(timezone.utc).isoformat(), msg))
    except Exception:
        pass


def flatten_content(content):
    """Return plain text from a Claude/Codex-style content field."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                # type: text | thinking | tool_use | tool_result | reasoning ...
                if "text" in block:
                    parts.append(str(block["text"]))
                elif "content" in block:
                    parts.append(flatten_content(block["content"]))
                elif block.get("type") == "tool_use":
                    parts.append("[tool_use %s]" % block.get("name", ""))
                elif block.get("type") == "tool_result":
                    parts.append("[tool_result]")
        return "\n".join(p for p in parts if p)
    return str(content)


def extract_role_content(obj):
    """Map a single transcript record to (role, text)."""
    role = obj.get("role") or obj.get("type") or ""
    # CodeBuddy nested form: {role, message: "<json string>", extra, createdAt}
    if "message" in obj and isinstance(obj["message"], str):
        try:
            inner = json.loads(obj["message"])
            role = inner.get("role") or role
            return role, flatten_content(inner.get("content"))
        except Exception:
            return role, obj["message"]
    return role, flatten_content(obj.get("content"))


def normalize_text(transcript_text):
    """Best-effort normalize arbitrary transcript text to JSONL records."""
    text = transcript_text.strip()
    if not text:
        return []
    records = []
    # Try JSONL (Claude/Codex format): one JSON object per line.
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if lines:
        parsed_any = False
        for ln in lines:
            try:
                obj = json.loads(ln)
                parsed_any = True
                role, content = extract_role_content(obj)
                if role or content:
                    records.append({"role": role, "content": content})
            except Exception:
                continue
        if parsed_any and records:
            return records
    # Try a single JSON object (CodeBuddy nested message).
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            role, content = extract_role_content(obj)
            if role or content:
                return [{"role": role, "content": content}]
    except Exception:
        pass
    # Fallback: store raw as a single note.
    return [{"role": "unknown", "content": text[:50000]}]


def detect_format(transcript_text, is_dir):
    if is_dir:
        return "codebuddy-message-dir"
    text = transcript_text.strip()
    if not text:
        return "empty"
    if "\n" in text:
        first = text.splitlines()[0].strip()
        try:
            json.loads(first)
            return "jsonl"
        except Exception:
            return "single-json-or-text"
    try:
        json.loads(text)
        return "single-json"
    except Exception:
        return "text"


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(NORMALIZED_DIR, exist_ok=True)
    os.makedirs(PROBE_DIR, exist_ok=True)

    raw = ""
    try:
        raw = sys.stdin.read()
    except Exception as e:
        log_err("stdin read failed: %s" % e)
        return 0

    try:
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        event = {}

    session_id = event.get("session_id") or "unknown"
    transcript_path = event.get("transcript_path") or ""
    hook_event = event.get("hook_event_name") or "Stop"

    if not transcript_path or not os.path.exists(transcript_path):
        log_err("session=%s no transcript_path or missing file: %r"
                % (session_id, transcript_path))
        print("codebuddy-stop-normalize: skip session=%s (no transcript)" % session_id)
        return 0

    is_dir = os.path.isdir(transcript_path)
    ext = "" if is_dir else os.path.splitext(transcript_path)[1] or ".bin"

    # 1) Archive the raw transcript verbatim (provenance).
    raw_dst = os.path.join(RAW_DIR, "%s_raw%s" % (session_id, ext))
    try:
        if is_dir:
            if os.path.exists(raw_dst):
                shutil.rmtree(raw_dst)
            shutil.copytree(transcript_path, raw_dst)
        else:
            shutil.copy2(transcript_path, raw_dst)
    except Exception as e:
        log_err("raw copy failed session=%s: %s" % (session_id, e))

    # 2) Read content (directory -> concatenate message files sorted by mtime).
    transcript_text = ""
    if is_dir:
        blobs = []
        for root, _dirs, files in os.walk(transcript_path):
            for fn in files:
                if fn.endswith(".json"):
                    p = os.path.join(root, fn)
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            blobs.append(f.read())
                    except Exception:
                        pass
        transcript_text = "\n".join(blobs)
    else:
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                transcript_text = f.read()
        except Exception as e:
            log_err("transcript read failed session=%s: %s" % (session_id, e))
            print("codebuddy-stop-normalize: read error session=%s" % session_id)
            return 0

    fmt = detect_format(transcript_text, is_dir)

    # 3) Probe report (first 1500 chars of raw) for format inspection.
    probe_path = os.path.join(PROBE_DIR, "%s.probe.txt" % session_id)
    try:
        with open(probe_path, "w", encoding="utf-8") as f:
            f.write("session_id: %s\n" % session_id)
            f.write("hook_event: %s\n" % hook_event)
            f.write("transcript_path: %s\n" % transcript_path)
            f.write("is_dir: %s\n" % is_dir)
            f.write("detected_format: %s\n" % fmt)
            f.write("size_bytes: %d\n" % len(transcript_text.encode("utf-8")))
            f.write("first_1500_chars:\n")
            f.write(transcript_text[:1500])
            f.write("\n")
    except Exception as e:
        log_err("probe write failed session=%s: %s" % (session_id, e))

    # 4) Normalize -> JSONL archive.
    records = normalize_text(transcript_text)
    norm_path = os.path.join(NORMALIZED_DIR, "%s.jsonl" % session_id)
    try:
        with open(norm_path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        log_err("normalize write failed session=%s: %s" % (session_id, e))

    # 5) Optional ingestion into episodic-memory (disabled until installed).
    if INGEST_TO_EPISODIC:
        try:
            import subprocess
            env = dict(os.environ)
            env["EPISODIC_MEMORY_CONFIG_DIR"] = ARCHIVE_BASE
            r = subprocess.run(
                ["episodic-memory", "import", norm_path],
                capture_output=True, text=True, timeout=50, env=env,
            )
            if r.returncode != 0:
                log_err("episodic import failed session=%s: %s"
                        % (session_id, r.stderr[:500]))
        except Exception as e:
            log_err("episodic import error session=%s: %s" % (session_id, e))

    print("codebuddy-stop-normalize: ok session=%s format=%s records=%d"
          % (session_id, fmt, len(records)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log_err("unexpected: %s" % traceback.format_exc())
        print("codebuddy-stop-normalize: unexpected error")
        sys.exit(0)
