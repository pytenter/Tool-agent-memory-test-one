"""Retrieve memory snippets using a MINJA/RAP-like semantic retrieval path."""

import math
import os
import re
from typing import Dict, List, Optional, Tuple

from .memory_writer import load_memory_store


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")
_DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_EMBEDDING_MODEL_CACHE: Dict[str, object] = {}
_STORE_EMBEDDING_CACHE: Dict[Tuple[str, float, str, int], Dict[str, object]] = {}


def _tokenize(text):
    return [token.lower() for token in _TOKEN_PATTERN.findall(text or "")]


def _record_text(record):
    fields = [
        record.get("req", ""),
        record.get("resp", ""),
        record.get("tag", ""),
        " ".join(record.get("semantic_targets", [])),
        record.get("Instruction", ""),
        record.get("SanitizedMemoryText", ""),
        " ".join(record.get("Actions", [])),
        record.get("SourceTool", ""),
        record.get("TargetTool", ""),
        record.get("TaskType", ""),
        record.get("ToolPreference", ""),
    ]
    return " ".join([str(field) for field in fields if field])


def _instruction_text(record):
    return str(record.get("req") or record.get("Instruction", "") or "")


def _memory_text(record):
    return str(record.get("resp") or record.get("SanitizedMemoryText", "") or "")


def _tag_text(record):
    tag = record.get("tag", "")
    return str(tag or "")


def _semantic_target_text(record):
    targets = record.get("semantic_targets", [])
    if isinstance(targets, str):
        return targets
    return " ".join([str(item) for item in targets if item])


def _actions_text(record):
    return " ".join([str(step) for step in record.get("Actions", []) if step])


def _token_overlap_score(query, record):
    query_tokens = set(_tokenize(query))
    record_tokens = set(_tokenize(_record_text(record)))
    if not query_tokens or not record_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(record_tokens))
    return overlap / float(math.sqrt(len(query_tokens) * len(record_tokens)))


def _get_embedding_model(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except Exception:
        return None

    if model_name not in _EMBEDDING_MODEL_CACHE:
        _EMBEDDING_MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _EMBEDDING_MODEL_CACHE[model_name]


def _get_store_cache_key(store_path: str, records: List[Dict], model_name: str) -> Tuple[str, float, str, int]:
    try:
        mtime = os.path.getmtime(store_path)
    except OSError:
        mtime = -1.0
    return (os.path.abspath(store_path), mtime, model_name, len(records))


def _build_semantic_embeddings(records: List[Dict], model_name: str, store_path: str) -> Optional[Dict[str, object]]:
    model = _get_embedding_model(model_name)
    if model is None:
        return None

    cache_key = _get_store_cache_key(store_path, records, model_name)
    cached = _STORE_EMBEDDING_CACHE.get(cache_key)
    if cached is not None:
        return cached

    instruction_texts = [_instruction_text(record) for record in records]
    memory_texts = [_memory_text(record) for record in records]
    tag_texts = [_tag_text(record) for record in records]
    semantic_target_texts = [_semantic_target_text(record) for record in records]
    action_texts = [_actions_text(record) for record in records]
    full_texts = [_record_text(record) for record in records]

    payload = {
        "instruction": model.encode(instruction_texts, convert_to_tensor=True, normalize_embeddings=True),
        "memory": model.encode(memory_texts, convert_to_tensor=True, normalize_embeddings=True),
        "tags": model.encode(tag_texts, convert_to_tensor=True, normalize_embeddings=True),
        "targets": model.encode(semantic_target_texts, convert_to_tensor=True, normalize_embeddings=True),
        "actions": model.encode(action_texts, convert_to_tensor=True, normalize_embeddings=True),
        "full": model.encode(full_texts, convert_to_tensor=True, normalize_embeddings=True),
    }
    _STORE_EMBEDDING_CACHE[cache_key] = payload
    return payload


def _maybe_embedding_score(query, records, store_path, embedding_model_name):
    """Prefer semantic retrieval over lexical overlap when embeddings are available."""
    try:
        from sentence_transformers.util import cos_sim
    except Exception:
        return None

    model = _get_embedding_model(embedding_model_name)
    if model is None:
        return None

    embedding_bank = _build_semantic_embeddings(records, embedding_model_name, store_path)
    if embedding_bank is None:
        return None

    query_embedding = model.encode([query], convert_to_tensor=True, normalize_embeddings=True)
    instruction_scores = cos_sim(query_embedding, embedding_bank["instruction"])[0]
    memory_scores = cos_sim(query_embedding, embedding_bank["memory"])[0]
    tag_scores = cos_sim(query_embedding, embedding_bank["tags"])[0]
    target_scores = cos_sim(query_embedding, embedding_bank["targets"])[0]
    action_scores = cos_sim(query_embedding, embedding_bank["actions"])[0]
    full_scores = cos_sim(query_embedding, embedding_bank["full"])[0]

    # We now favor query-shaped request fields and semantic target aliases, which makes
    # the record behave more like an experience entry rather than a plain rule snippet.
    scores = (
        0.30 * instruction_scores
        + 0.25 * target_scores
        + 0.20 * memory_scores
        + 0.10 * tag_scores
        + 0.05 * action_scores
        + 0.10 * full_scores
    )
    return [float(score) for score in scores]


def retrieve_memory_snippets(
    query,
    store_path,
    top_k=3,
    min_score=0.05,
    retrieval_mode="embedding",
    provenance_aware=False,
    memory_type_isolation=False,
    trusted_write_reasons=None,
    embedding_model_name=None,
):
    """Return top-k memory hits plus provenance metadata."""
    records = load_memory_store(store_path)
    if not records:
        return {"hits": [], "retrieval_mode": retrieval_mode, "flagged_records": 0}

    flagged_records = 0
    if memory_type_isolation:
        trusted = trusted_write_reasons or ["user_confirmed_fact"]
        filtered = []
        for record in records:
            if record.get("WriteReason") in trusted:
                filtered.append(record)
            else:
                flagged_records += 1
        records = filtered
        if not records:
            return {"hits": [], "retrieval_mode": retrieval_mode, "flagged_records": flagged_records}

    embedding_model_name = embedding_model_name or os.getenv("MEMORY_EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL)
    embedding_scores = None
    if retrieval_mode in ("auto", "embedding", "semantic"):
        embedding_scores = _maybe_embedding_score(
            query=query,
            records=records,
            store_path=store_path,
            embedding_model_name=embedding_model_name,
        )

    hits = []
    for index, record in enumerate(records):
        score = _token_overlap_score(query, record)
        mode_used = "token"
        if embedding_scores is not None:
            score = embedding_scores[index]
            mode_used = "embedding"

        provenance_flag = False
        if provenance_aware and record.get("SourceTool") not in ("USER", "TrustedMemoryWriter"):
            provenance_flag = True
            flagged_records += 1
            score *= 0.2

        if score < min_score:
            continue

        hits.append(
            {
                "record": record,
                "score": round(score, 4),
                "mode": mode_used,
                "provenance_flag": provenance_flag,
                "snippet": record.get("SanitizedMemoryText", ""),
            }
        )

    hits.sort(key=lambda item: item["score"], reverse=True)
    return {
        "hits": hits[:top_k],
        "retrieval_mode": "embedding" if embedding_scores is not None else "token",
        "flagged_records": flagged_records,
    }
