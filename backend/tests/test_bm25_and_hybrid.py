import math
from types import SimpleNamespace

import numpy as np

from app.core.embeddings_config import EMBEDDING_DIMENSION
from app.db.models.journal import Journal
from app.services.bm25 import BM25Index, tokenize_for_bm25
from app.services.embedding import JournalEmbedder
from app.services.matching import (
    compute_relative_match_scores,
    compute_vectorized_cosine_similarity,
    normalize_cosine_for_hybrid,
    search_matching_journals,
)


def test_bm25_ignores_stopwords_and_ranks_exact_terms():
    docs = [
        "Software Engineering refactoring code smell static analysis maintainability",
        "Computer Vision object tracking correlation filters convolutional networks",
        "Distributed relational databases query optimization transaction processing",
    ]
    index = BM25Index(docs)
    raw = index.score("A survey on object tracking using correlation filters for vision.")
    norm = index.normalized_score("A survey on object tracking using correlation filters for vision.")

    assert raw.shape == (3,)
    assert raw[1] > raw[0] and raw[1] > raw[2]
    assert math.isclose(norm[1], 1.0)
    assert norm[0] == 0.0
    assert norm[2] == 0.0
    assert all(0.0 <= float(x) <= 1.0 for x in norm)


def test_bm25_handles_empty_or_unmatched_query():
    index = BM25Index(["Neural networks computer vision", "Software testing refactoring"])
    no_match = index.normalized_score("quantum chromodynamics spectroscopy")
    empty_q = index.normalized_score("the and of for")

    assert np.allclose(no_match, [0.0, 0.0])
    assert np.allclose(empty_q, [0.0, 0.0])
    assert tokenize_for_bm25("") == []


def test_vectorized_cosine_similarity_matches_exact_formula():
    doc_matrix = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [3.0, 4.0, 0.0],
        ],
        dtype=np.float64,
    )
    query = np.array([3.0, 4.0, 0.0], dtype=np.float64)

    sims = compute_vectorized_cosine_similarity(doc_matrix, query)
    assert np.allclose(sims, [0.6, 0.8, 1.0])


def test_hybrid_fusion_boosts_exact_domain_terms(db_session):
    # Two journals with nearly identical dense cosine similarity, but j_exact has exact domain terms
    v_sem1 = [0.0] * EMBEDDING_DIMENSION
    v_sem1[0] = 0.80
    v_sem1[1] = 0.60

    v_sem2 = [0.0] * EMBEDDING_DIMENSION
    v_sem2[0] = 0.79
    v_sem2[1] = math.sqrt(1.0 - 0.79**2)

    j_generic = Journal(
        journal_title="General Computing Systems",
        publisher="Pub A",
        issn="2000-0001",
        subject_category="Computing",
        aims_and_scope="Publishes papers on general computing theory and distributed systems.",
        embedding=v_sem1,
    )
    j_exact = Journal(
        journal_title="Journal of Spatiotemporal Reservoir Path Tracing",
        publisher="Pub B",
        issn="2000-0002",
        subject_category="Computer Graphics",
        aims_and_scope="Covers real-time path tracing, spatiotemporal reservoir resampling, and Monte Carlo rendering.",
        embedding=v_sem2,
    )
    db_session.add_all([j_generic, j_exact])
    db_session.flush()

    q_vec = [0.0] * EMBEDDING_DIMENSION
    q_vec[0] = 1.0

    results = search_matching_journals(
        query_vector=q_vec,
        db=db_session,
        query_text="Real-time path tracing with spatiotemporal reservoir resampling",
        limit=2,
        cosine_weight=0.7,
        bm25_weight=0.3,
    )

    assert len(results) == 2
    assert results[0].journal.journal_title == "Journal of Spatiotemporal Reservoir Path Tracing"
    assert results[0].bm25_score > results[1].bm25_score
    assert results[0].hybrid_score > results[1].hybrid_score
    assert results[0].match_tag == "Best fit"


def test_long_scope_chunking_splits_over_512_tokens():
    class FakeTokenizer:
        def encode(self, text, add_special_tokens=False):
            return text.split()

        def decode(self, token_ids, skip_special_tokens=True):
            return " ".join(token_ids)

    encoded_calls = []

    class FakeSentenceTransformer:
        max_seq_length = 512
        tokenizer = FakeTokenizer()

        def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
            if isinstance(texts, str):
                encoded_calls.append([texts])
                vec = np.zeros(EMBEDDING_DIMENSION, dtype=np.float64)
                vec[0] = 1.0
                return vec
            encoded_calls.append(list(texts))
            vecs = []
            for idx, _ in enumerate(texts):
                vec = np.zeros(EMBEDDING_DIMENSION, dtype=np.float64)
                vec[idx % 4] = 1.0
                vecs.append(vec)
            return np.asarray(vecs, dtype=np.float64)

    embedder = JournalEmbedder(model_name="BAAI/bge-base-en-v1.5")
    embedder._model = FakeSentenceTransformer()
    embedder._is_loaded = True

    long_words = [f"token{i}" for i in range(650)]
    long_scope = "Computational Intelligence. " + " ".join(long_words)

    emb = embedder.embed_document(long_scope, title="Computational Intelligence")

    assert len(emb) == EMBEDDING_DIMENSION
    assert math.isclose(np.linalg.norm(emb), 1.0, rel_tol=1e-5)
    assert len(encoded_calls) == 1
    assert len(encoded_calls[0]) >= 2  # Split into overlapping chunks instead of truncated
    # Second chunk keeps journal title anchor
    assert encoded_calls[0][1].startswith("Computational Intelligence.")


def test_normalize_cosine_for_hybrid_handles_wide_and_narrow_pools():
    wide = np.array([-0.10, 0.15, 0.40], dtype=np.float64)
    norm_wide = normalize_cosine_for_hybrid(wide, min_span=0.25)
    assert np.allclose(norm_wide, [0.0, 0.5, 1.0])

    narrow = np.array([0.78, 0.80, 0.82], dtype=np.float64)
    norm_narrow = normalize_cosine_for_hybrid(narrow, min_span=0.25)
    assert math.isclose(float(norm_narrow[2]), 1.0)
    assert float(norm_narrow[0]) > 0.80  # Not stretched down to 0.0 when gap is tiny
    assert norm_narrow[0] < norm_narrow[1] < norm_narrow[2]


def test_compute_relative_match_scores_anchors_to_cosine_strength():
    # Strong in-domain match (max_cos = 0.38) -> 75..88%
    strong_hyb = np.array([0.92, 0.65, 0.30], dtype=np.float64)
    strong_cos = np.array([0.38, 0.25, 0.08], dtype=np.float64)
    strong_scores = compute_relative_match_scores(strong_hyb, strong_cos)
    assert 75 <= strong_scores[0] <= 88
    assert strong_scores[0] > strong_scores[1] > strong_scores[2]

    # Cross-domain / partial overlap (max_cos = 0.29) -> 50..65%
    cross_hyb = np.array([0.90, 0.60, 0.20], dtype=np.float64)
    cross_cos = np.array([0.29, 0.20, 0.05], dtype=np.float64)
    cross_scores = compute_relative_match_scores(cross_hyb, cross_cos)
    assert 50 <= cross_scores[0] <= 65
    assert cross_scores[0] > cross_scores[1] > cross_scores[2]

    # Truly off-topic query (max_cos = 0.12) -> < 25%
    off_hyb = np.array([0.85, 0.50, 0.10], dtype=np.float64)
    off_cos = np.array([0.12, 0.06, -0.02], dtype=np.float64)
    off_scores = compute_relative_match_scores(off_hyb, off_cos)
    assert off_scores[0] < 25
    assert off_scores[0] > off_scores[1] > off_scores[2]

    # Synthetic unit vector >= 0.99 maps to 100
    synth_hyb = np.array([0.95, 0.50], dtype=np.float64)
    synth_cos = np.array([1.0, 0.40], dtype=np.float64)
    synth_scores = compute_relative_match_scores(synth_hyb, synth_cos)
    assert synth_scores[0] == 100
