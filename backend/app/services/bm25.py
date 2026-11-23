"""Okapi BM25 lexical scoring index for exact academic domain term matching."""

from __future__ import annotations

import math
from collections import Counter, defaultdict

import numpy as np

from app.core.text_cleaning import clean_text


def tokenize_for_bm25(text: str | None) -> list[str]:
    """Tokenizes text for lexical BM25 matching with stopword and punctuation removal."""
    cleaned = clean_text(
        text,
        remove_stopwords=True,
        lowercase=True,
        remove_punctuation=True,
    )
    return cleaned.split()


class BM25Index:
    """In-memory Okapi BM25 lexical index over a corpus of documents."""

    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(documents)

        self.doc_tokens: list[list[str]] = [tokenize_for_bm25(doc) for doc in documents]
        self.doc_lengths = np.array([len(tokens) for tokens in self.doc_tokens], dtype=np.float64)
        self.avgdl = float(self.doc_lengths.mean()) if self.corpus_size > 0 else 0.0

        self.idf: dict[str, float] = {}
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)

        if self.corpus_size == 0:
            return

        df: Counter[str] = Counter()
        for doc_idx, tokens in enumerate(self.doc_tokens):
            if not tokens:
                continue
            tf_counts = Counter(tokens)
            for term, freq in tf_counts.items():
                self.postings[term].append((doc_idx, freq))
                df[term] += 1

        # Standard Robertson/Lucene non-negative Okapi BM25 IDF
        for term, doc_freq in df.items():
            self.idf[term] = math.log(
                (self.corpus_size - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0
            )

    def score(self, query_text: str | None) -> np.ndarray:
        """Computes raw Okapi BM25 scores for every document in the corpus."""
        scores = np.zeros(self.corpus_size, dtype=np.float64)
        if self.corpus_size == 0 or self.avgdl == 0.0:
            return scores

        query_tokens = tokenize_for_bm25(query_text)
        if not query_tokens:
            return scores

        for term in query_tokens:
            idf = self.idf.get(term)
            if idf is None:
                continue
            for doc_idx, tf in self.postings[term]:
                dl = self.doc_lengths[doc_idx]
                denom = tf + self.k1 * (1.0 - self.b + self.b * (dl / self.avgdl))
                if denom > 0.0:
                    scores[doc_idx] += idf * ((tf * (self.k1 + 1.0)) / denom)

        return scores

    def normalized_score(self, query_text: str | None) -> np.ndarray:
        """Normalizes raw BM25 scores per query into [0.0, 1.0] via max-scaling."""
        raw = self.score(query_text)
        if raw.size == 0:
            return raw
        max_score = float(raw.max())
        if max_score > 0.0:
            return raw / max_score
        return np.zeros_like(raw)
