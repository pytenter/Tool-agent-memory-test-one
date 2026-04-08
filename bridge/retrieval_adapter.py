"""Retrieve memory snippets using a RAP-like interface with local fallbacks."""

import math
import re

from .memory_writer import load_memory_store


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text):
    return [token.lower() for token in _TOKEN_PATTERN.findall(text or "")]


def _record_text(record):
    fields = [
        record.get("Instruction", ""),
        record.get("SanitizedMemoryText", ""),
        " ".join(record.get("Actions", [])),
        record.get("SourceTool", ""),
        record.get("TargetTool", ""),
        record.get("TaskType", ""),
        record.get("ToolPreference", ""),
    ]
    return " ".join([str(field) for field in fields if field])


def _token_overlap_score(query, record):
    query_tokens = set(_tokenize(query))
    record_tokens = set(_tokenize(_record_text(record)))
    if not query_tokens or not record_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(record_tokens))
    return overlap / float(math.sqrt(len(query_tokens) * len(record_tokens)))


def _maybe_embedding_score(query, records):
    """Try sentence-transformers, else return None."""
    try:
        from sentence_transformers import SentenceTransformer
        from sentence_transformers.util import cos_sim
    except Exception:
        return None

    model = SentenceTransformer("all-MiniLM-L6-v2")
    query_embedding = model.encode([query])
    record_embeddings = model.encode([_record_text(record) for record in records])
    scores = cos_sim(query_embedding, record_embeddings)[0]
    return [float(score) for score in scores]


def retrieve_memory_snippets(
    query,
    store_path,
    top_k=3,
    min_score=0.05,
    retrieval_mode="auto",
    provenance_aware=False,
    memory_type_isolation=False,
    trusted_write_reasons=None,
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

    embedding_scores = None
    if retrieval_mode in ("auto", "embedding"):
        embedding_scores = _maybe_embedding_score(query, records)

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
