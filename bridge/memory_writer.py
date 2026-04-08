"""Persist safe successor-tool outputs into a MINJA-style JSON memory store."""

import json
import os
import uuid
from datetime import datetime


def load_memory_store(store_path):
    """Load an existing JSON list memory store."""
    if not os.path.exists(store_path):
        return []
    with open(store_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return data
    raise ValueError("Memory store must be a JSON list.")


def save_memory_store(store_path, records):
    """Persist records as a JSON list."""
    directory = os.path.dirname(store_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(store_path, "w", encoding="utf-8") as handle:
        json.dump(records, handle, indent=2, ensure_ascii=False)


def reset_memory_store(store_path):
    """Clear a memory store file."""
    save_memory_store(store_path, [])


def parse_tool_output(raw_tool_output):
    """Parse a dict or JSON string successor output."""
    if isinstance(raw_tool_output, dict):
        return raw_tool_output
    if raw_tool_output is None:
        return {}
    if not isinstance(raw_tool_output, str):
        return {"raw_text": str(raw_tool_output)}
    try:
        return json.loads(raw_tool_output)
    except json.JSONDecodeError:
        return {"raw_text": raw_tool_output}


def sanitize_memory_text(payload):
    """Extract a normalized memory text from a structured payload."""
    text = payload.get("memory_candidate") or payload.get("summary") or payload.get("raw_text") or ""
    return " ".join(str(text).split())


def build_memory_record(
    instruction,
    actions,
    raw_tool_output,
    source_tool,
    target_tool,
    write_reason="tool_return_summary",
    success=True,
    reward=1.0,
    record_id=None,
    timestamp=None,
):
    """Build a MINJA-style memory record with provenance."""
    payload = parse_tool_output(raw_tool_output)
    sanitized_text = sanitize_memory_text(payload)
    return {
        "Id": record_id or "mem_" + uuid.uuid4().hex[:10],
        "Instruction": instruction,
        "Actions": list(actions or []),
        "Success": bool(success),
        "Reward": float(reward),
        "SourceTool": source_tool,
        "TargetTool": target_tool,
        "WriteReason": write_reason,
        "RawToolOutput": raw_tool_output,
        "SanitizedMemoryText": sanitized_text,
        "Timestamp": timestamp or datetime.utcnow().isoformat() + "Z",
        "Marker": payload.get("marker", ""),
        "TaskType": payload.get("task_type", ""),
        "ToolPreference": payload.get("preference", ""),
    }


def append_memory_record(store_path, record):
    """Append a record to the JSON memory store."""
    records = load_memory_store(store_path)
    records.append(record)
    save_memory_store(store_path, records)
    return record


def write_memory_from_tool_output(
    store_path,
    instruction,
    actions,
    raw_tool_output,
    source_tool,
    target_tool,
    write_reason="tool_return_summary",
    success=True,
    reward=1.0,
    write_policy="allow_all",
):
    """Parse successor output and append a record when a memory candidate exists."""
    payload = parse_tool_output(raw_tool_output)
    memory_candidate = payload.get("memory_candidate")
    if not memory_candidate:
        return {"written": False, "reason": "no_memory_candidate"}

    if write_policy == "reject_marker_records" and payload.get("marker") == "MEMORY_MARKER_Z":
        return {"written": False, "reason": "blocked_by_write_policy", "marker": payload.get("marker")}

    record = build_memory_record(
        instruction=instruction,
        actions=actions,
        raw_tool_output=payload,
        source_tool=source_tool,
        target_tool=target_tool,
        write_reason=write_reason,
        success=success,
        reward=reward,
    )
    append_memory_record(store_path, record)
    return {"written": True, "record": record}

