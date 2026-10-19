DEFAULT_EMBEDDING_MODEL = "allenai-specter"
EMBEDDING_DIMENSION = 768


def build_journal_text(title: str, aims_and_scope: str) -> str:
    """Standardized text format for embedding journal scope."""
    clean_title = (title or "").strip()
    clean_scope = (aims_and_scope or "").strip()
    if clean_title and clean_scope:
        return f"{clean_title}. {clean_scope}"
    return clean_title or clean_scope
