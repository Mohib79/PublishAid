from app.core.text_cleaning import clean_text, DEFAULT_STOPWORDS
from app.core.embeddings_config import build_journal_text
from app.services.matching import build_query_text


def test_clean_text_removes_stopwords():
    raw = "A survey of the latest deep learning algorithms for object detection."
    cleaned = clean_text(raw, remove_stopwords=True)
    assert "survey" in cleaned
    assert "deep" in cleaned
    assert "learning" in cleaned
    assert "algorithms" in cleaned
    assert "object" in cleaned
    assert "detection" in cleaned
    # stopwords removed:
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


def test_build_journal_text_with_cleaning():
    title = "Journal of Computer Vision"
    scope = "This journal covers topics in image processing and computer vision."
    res = build_journal_text(title, scope, clean=True)
    assert "journal computer vision" in res
    assert "covers topics image processing computer vision" in res


def test_build_query_text_with_cleaning():
    title = "A Study on Quantum Computing"
    abstract = "We present an overview of quantum gate error mitigation."
    keywords = ["Quantum", "Error Mitigation", "and Algorithms"]
    query = build_query_text(title=title, abstract=abstract, keywords=keywords, clean=True)
    assert "study quantum computing" in query
    assert "present overview quantum gate error mitigation" in query
    assert "Keywords: quantum, error mitigation, algorithms" in query

