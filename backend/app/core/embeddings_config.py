from app.core.text_cleaning import clean_text

DEFAULT_EMBEDDING_MODEL = "allenai-specter"
EMBEDDING_DIMENSION = 768


def build_journal_text(title: str, aims_and_scope: str, clean: bool = True) -> str:
    """Standardized text format for embedding journal scope."""
    raw_title = (title or "").strip()
    raw_scope = (aims_and_scope or "").strip()

    if clean:
        c_title = clean_text(raw_title, remove_stopwords=True)
        c_scope = clean_text(raw_scope, remove_stopwords=True)
        if c_title and c_scope:
            return f"{c_title}. {c_scope}"
        return c_title or c_scope

    if raw_title and raw_scope:
        return f"{raw_title}. {raw_scope}"
    return raw_title or raw_scope
