from app.core.embeddings_config import build_journal_lexical_text, build_journal_text
from app.core.text_cleaning import clean_text
from app.services.matching import build_query_text


def test_clean_text_removes_stopwords_for_bm25():
    raw = "A survey of the latest deep learning algorithms for object detection."
    cleaned = clean_text(raw, remove_stopwords=True)
    assert "survey" in cleaned
    assert "deep" in cleaned
    assert "learning" in cleaned
    assert "algorithms" in cleaned
    assert "object" in cleaned
    assert "detection" in cleaned
    assert "a" not in cleaned.split()
    assert "of" not in cleaned.split()
    assert "the" not in cleaned.split()
    assert "for" not in cleaned.split()


def test_clean_text_strips_punctuation_and_urls():
    raw = "Check this out https://example.com/paper: Fast & Accurate Transformer (v2.0)!"
    cleaned = clean_text(raw, remove_stopwords=True)
    assert "https" not in cleaned
    assert "example" not in cleaned
    assert "fast" in cleaned
    assert "accurate" in cleaned
    assert "transformer" in cleaned


def test_build_journal_text_preserves_natural_prose():
    title = "  Journal of   Computer Vision  "
    scope = "This journal covers topics in\n image processing and computer vision (e.g., SLAM)."
    res = build_journal_text(title, scope)
    assert res == (
        "Journal of Computer Vision. "
        "This journal covers topics in image processing and computer vision (e.g., SLAM)."
    )


def test_build_query_text_preserves_natural_prose():
    title = "  A Study on Quantum Computing  "
    abstract = "We present an overview of quantum gate error mitigation."
    keywords = ["Quantum", "Error Mitigation", "and Algorithms"]
    query = build_query_text(title=title, abstract=abstract, keywords=keywords)
    assert query == (
        "A Study on Quantum Computing. "
        "We present an overview of quantum gate error mitigation. "
        "Keywords: Quantum, Error Mitigation, and Algorithms"
    )


def test_build_journal_lexical_text_includes_subject():
    lexical = build_journal_lexical_text(
        title="Computer Networks",
        aims_and_scope="Publishes research on SDN and routing.",
        subject_category="Networking",
    )
    assert lexical == "Computer Networks Networking Publishes research on SDN and routing."
