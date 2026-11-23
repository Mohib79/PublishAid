"""Configuration and text formatting helpers for journal and query embeddings."""

import re

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"
EMBEDDING_DIMENSION = 768

BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


def get_query_prefix(model_name: str) -> str:
    """Returns asymmetric retrieval instruction prefix when required by the model."""
    lowered = (model_name or "").strip().lower()
    if "bge" in lowered and (
        "v1.5" in lowered
        or "bge-base-en" in lowered
        or "bge-large-en" in lowered
        or "bge-small-en" in lowered
    ):
        return BGE_QUERY_INSTRUCTION
    return ""


def normalize_whitespace(text: str | None) -> str:
    """Collapses escaped newlines and repeated whitespace while keeping natural punctuation and casing."""
    if not text:
        return ""
    unescaped = text.replace("\\r\\n", " ").replace("\\n", " ")
    return re.sub(r"\s+", " ", unescaped).strip()


def build_journal_text(title: str, aims_and_scope: str) -> str:
    """Formats natural-language journal scope text for dense transformer embedding."""
    clean_title = normalize_whitespace(title)
    clean_scope = normalize_whitespace(aims_and_scope)

    if clean_title and clean_scope:
        return f"{clean_title}. {clean_scope}"
    return clean_title or clean_scope


def build_journal_lexical_text(
    title: str,
    aims_and_scope: str,
    subject_category: str | None = None,
) -> str:
    """Combines title, subject category, and full aims & scope for BM25 lexical indexing."""
    parts = [
        normalize_whitespace(title),
        normalize_whitespace(subject_category),
        normalize_whitespace(aims_and_scope),
    ]
    return " ".join(part for part in parts if part)
