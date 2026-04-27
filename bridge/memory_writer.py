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


def _normalize_tag_value(payload):
    tag = payload.get("tag", "")
    if isinstance(tag, list):
        return ",".join([str(item).strip() for item in tag if str(item).strip()])
    return str(tag).strip()


def _normalize_semantic_targets(payload):
    values = payload.get("semantic_targets", [])
    if isinstance(values, str):
        return [values] if values.strip() else []
    return [str(item).strip() for item in values if str(item).strip()]


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
    req = str(payload.get("req") or instruction)
    resp = str(payload.get("resp") or sanitized_text or payload.get("summary") or "")
    tag = _normalize_tag_value(payload)
    semantic_targets = _normalize_semantic_targets(payload)
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
        "req": req,
        "resp": resp,
        "tag": tag,
        "semantic_targets": semantic_targets,
    }


def build_admitted_memory_record(
    instruction,
    actions,
    raw_tool_output,
    source_tool,
    target_tool,
    admitted_memory,
    write_reason="tool_return_summary",
    success=True,
    reward=1.0,
    record_id=None,
    timestamp=None,
    admission_mode="mem0_additive",
):
    """Build a record whose final memory text comes from an admission layer."""
    record = build_memory_record(
        instruction=instruction,
        actions=actions,
        raw_tool_output=raw_tool_output,
        source_tool=source_tool,
        target_tool=target_tool,
        write_reason=write_reason,
        success=success,
        reward=reward,
        record_id=record_id,
        timestamp=timestamp,
    )
    admitted_text = " ".join(str(admitted_memory.get("text", "")).split())
    record["OriginalSanitizedMemoryText"] = record.get("SanitizedMemoryText", "")
    record["OriginalResp"] = record.get("resp", "")
    record["SanitizedMemoryText"] = admitted_text
    record["resp"] = admitted_text or record.get("resp", "")
    if not admitted_memory.get("is_attack_memory", False):
        record["Marker"] = ""
        record["TaskType"] = ""
        record["ToolPreference"] = ""
    record["AttributedTo"] = str(admitted_memory.get("attributed_to") or "")
    record["LinkedMemoryIds"] = list(admitted_memory.get("linked_memory_ids") or [])
    record["AdmissionHash"] = str(admitted_memory.get("hash") or "")
    record["AdmissionMode"] = admission_mode
    record["AdmissionPassed"] = True
    record["AdmissionCategory"] = str(admitted_memory.get("category") or "")
    record["AdmissionSignals"] = dict(admitted_memory.get("signals") or {})
    record["IsAttackMemory"] = bool(admitted_memory.get("is_attack_memory", False))
    return record


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
    admission_mode="direct",
    admission_llm=None,
    admission_context=None,
    admission_custom_instructions=None,
):
    """Parse successor output and append a record when a memory candidate exists."""
    payload = parse_tool_output(raw_tool_output)
    memory_candidate = payload.get("memory_candidate")
    if not memory_candidate:
        return {"written": False, "reason": "no_memory_candidate"}

    if write_policy == "reject_marker_records" and payload.get("marker") == "MEMORY_MARKER_Z":
        return {"written": False, "reason": "blocked_by_write_policy", "marker": payload.get("marker")}

    if admission_mode == "direct":
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
        return {
            "written": True,
            "record": record,
            "admission_summary": {
                "mode": "direct",
                "extraction_non_empty": bool(record.get("SanitizedMemoryText")),
                "extracted_memory_count": 1 if record.get("SanitizedMemoryText") else 0,
                "admitted_memory_count": 1 if record.get("SanitizedMemoryText") else 0,
                "admitted_attack_memory_count": 1 if record.get("SanitizedMemoryText") else 0,
                "dropped_duplicate_count": 0,
                "dropped_non_attack_count": 0,
                "attack_rule_survival_rate": 1.0 if record.get("SanitizedMemoryText") else 0.0,
                "task_type_preservation_rate": 1.0 if record.get("TaskType") else 0.0,
                "tool_preference_preservation_rate": 1.0 if record.get("ToolPreference") else 0.0,
                "marker_preservation_rate": 1.0 if record.get("Marker") else 0.0,
                "rule_preservation_rate": 1.0 if "RULE_" in str(record.get("SanitizedMemoryText") or "").upper() else 0.0,
                "rewrite_changed_rate": 0.0,
                "rewrite_length_ratio_mean": 1.0 if record.get("SanitizedMemoryText") else 0.0,
                "category_counts": {"attack_rule": 1} if record.get("SanitizedMemoryText") else {},
            },
        }

    if admission_mode not in {"mem0_additive", "mem0_full"}:
        return {"written": False, "reason": f"unsupported_admission_mode:{admission_mode}"}

    if admission_llm is None:
        return {"written": False, "reason": "admission_llm_missing"}

    existing_records = load_memory_store(store_path)
    if admission_mode == "mem0_full":
        from .mem0_admission_adapter import admit_tool_output_full

        admission = admit_tool_output_full(
            llm=admission_llm,
            instruction=instruction,
            actions=list(actions or []),
            payload=payload,
            source_tool=source_tool,
            target_tool=target_tool,
            existing_records=existing_records,
            admission_context=admission_context,
            custom_instructions=admission_custom_instructions,
        )
        persisted_memories = admission.get("persisted_memories", [])
        admitted_memories = admission.get("admitted_memories", [])
        if not persisted_memories:
            all_extracted = admission.get("all_extracted_memories", [])
            return {
                "written": False,
                "persisted_any_memory": False,
                "reason": "no_persisted_memories_after_update" if all_extracted else "no_admitted_memories",
                "admission": admission,
                "admission_summary": {
                    "mode": admission_mode,
                    **dict(admission.get("summary") or {}),
                },
            }

        records = list(existing_records)
        deleted_ids = {
            str(operation.get("id") or "")
            for operation in admission.get("update_operations", [])
            if str(operation.get("event") or "").upper() == "DELETE"
        }
        updated_ids = {
            str(memory.get("update_id") or "")
            for memory in persisted_memories
            if str(memory.get("update_event") or "").upper() == "UPDATE"
        }
        remove_ids = {item for item in deleted_ids.union(updated_ids) if item}
        if remove_ids:
            records = [record for record in records if str(record.get("Id") or "") not in remove_ids]

        new_records = []
        existing_ids = {str(record.get("Id") or "") for record in existing_records}
        for index, admitted_memory in enumerate(persisted_memories):
            event = str(admitted_memory.get("update_event") or "ADD").upper()
            update_id = str(admitted_memory.get("update_id") or "")
            record_id = update_id if event == "UPDATE" and update_id in existing_ids else ""
            record = build_admitted_memory_record(
                instruction=instruction,
                actions=actions,
                raw_tool_output=payload,
                source_tool=source_tool,
                target_tool=target_tool,
                admitted_memory=admitted_memory,
                write_reason=write_reason,
                success=success,
                reward=reward,
                record_id=record_id or "mem_" + uuid.uuid4().hex[:10],
                admission_mode=admission_mode,
            )
            record["AdmissionIndex"] = index
            record["AdmissionSourceTool"] = source_tool
            record["AdmissionTargetTool"] = target_tool
            record["AdmissionRawOutput"] = admission.get("raw_response", "")
            record["AdmissionUpdateRawOutput"] = admission.get("update_raw_response", "")
            record["AdmissionUpdateEvent"] = event
            record["AdmissionOldMemory"] = str(admitted_memory.get("old_memory") or "")
            records.append(record)
            new_records.append(record)

        save_memory_store(store_path, records)
        attack_records = [record for record in new_records if record.get("IsAttackMemory")]
        return {
            "written": bool(attack_records),
            "persisted_any_memory": bool(new_records),
            "reason": "" if attack_records else "no_attack_memories_after_update",
            "record": attack_records[0] if attack_records else new_records[0],
            "records": new_records,
            "attack_records": attack_records,
            "admission": admission,
            "admission_summary": {
                "mode": admission_mode,
                **dict(admission.get("summary") or {}),
            },
        }

    from .mem0_admission_adapter import admit_tool_output

    admission = admit_tool_output(
        llm=admission_llm,
        instruction=instruction,
        actions=list(actions or []),
        payload=payload,
        source_tool=source_tool,
        target_tool=target_tool,
        existing_records=existing_records,
        admission_context=admission_context,
        custom_instructions=admission_custom_instructions,
    )
    admitted_memories = admission.get("admitted_memories", [])
    if not admitted_memories:
        all_admitted = admission.get("all_admitted_memories", [])
        return {
            "written": False,
            "reason": "no_attack_memories_after_filter" if all_admitted else "no_admitted_memories",
            "admission": admission,
            "admission_summary": {
                "mode": admission_mode,
                **dict(admission.get("summary") or {}),
            },
        }

    records = list(existing_records)
    new_records = []
    for index, admitted_memory in enumerate(admitted_memories):
        record = build_admitted_memory_record(
            instruction=instruction,
            actions=actions,
            raw_tool_output=payload,
            source_tool=source_tool,
            target_tool=target_tool,
            admitted_memory=admitted_memory,
            write_reason=write_reason,
            success=success,
            reward=reward,
            record_id="mem_" + uuid.uuid4().hex[:10],
            admission_mode=admission_mode,
        )
        record["AdmissionIndex"] = index
        record["AdmissionSourceTool"] = source_tool
        record["AdmissionTargetTool"] = target_tool
        record["AdmissionRawOutput"] = admission.get("raw_response", "")
        records.append(record)
        new_records.append(record)

    save_memory_store(store_path, records)
    return {
        "written": True,
        "record": new_records[0],
        "records": new_records,
        "admission": admission,
        "admission_summary": {
            "mode": admission_mode,
            **dict(admission.get("summary") or {}),
        },
    }
