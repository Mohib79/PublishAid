"""
Journal Matching Similarity Script:
Takes a manuscript abstract and a journal's aims & scope as input, applies the
text preprocessing pipeline, encodes both using the ALLENAI SPECTER transformer
model ('allenai-specter'), and outputs the raw cosine similarity score without
any clipping or score normalization.

Requirements:
    pip install sentence-transformers torch

Usage (input asked for abstract and journal aims and scope):
    python journal_similarity.py

Usage (Command-line arguments):
    python journal_similarity.py --abstract "Your abstract..." --aims-and-scope "Journal scope..."
"""

import argparse
import math
import re
import sys
import unicodedata
from typing import Iterable, Optional, Set

DEFAULT_EMBEDDING_MODEL = "allenai-specter"
EMBEDDING_DIMENSION = 768

#standard English stopwords set (derived from NLTK & scikit-learn standard lists)
DEFAULT_STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "almost", "also", "am", "among",
    "an", "and", "any", "are", "aren't", "arent", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "cannot", "cant", "could", "couldn't",
    "couldnt", "did", "didn't", "didnt", "do", "does", "doesn't", "doesnt", "doing", "don't",
    "dont", "down", "during", "each", "eg", "et", "al", "etc", "few", "for", "from", "further",
    "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's",
    "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "ie", "if", "in", "into", "is", "isn't", "isnt", "it", "it's",
    "its", "itself", "just", "let's", "me", "more", "most", "mustn't", "my", "myself", "no",
    "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
    "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's",
    "should", "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their",
    "theirs", "them", "themselves", "then", "there", "there's", "these", "they", "they'd",
    "they'll", "they're", "they've", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't",
    "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's",
    "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll",
    "you're", "you've", "your", "yours", "yourself", "yourselves",
}


def clean_text(
    text: str | None,
    remove_stopwords: bool = True,
    lowercase: bool = True,
    remove_punctuation: bool = True,
    custom_stopwords: Iterable[str] | None = None,
) -> str:
    """
    Cleans raw text for NLP processing and embedding generation.
    - Strips leading/trailing and excess whitespace
    - Normalizes Unicode characters (NFKD)
    - Strips URLs and HTML-like tags
    - Removes punctuation (optional)
    - Lowers case (optional)
    - Removes English stopwords (optional)
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)

    stopwords = DEFAULT_STOPWORDS
    if custom_stopwords:
        stopwords = stopwords.union(set(custom_stopwords))

    if remove_punctuation:
        text = re.sub(r"[^\w\s]", " ", text)

    tokens = text.split()

    cleaned_tokens: list[str] = []
    for token in tokens:
        token_clean = token.lower() if lowercase else token
        check_val = token.lower()
        if remove_stopwords and check_val in stopwords:
            continue
        if len(token_clean.strip()) > 1 or token_clean.isalnum():
            cleaned_tokens.append(token_clean)

    return " ".join(cleaned_tokens)


def build_query_text(abstract: str, clean: bool = True) -> str:
    """Prepares manuscript abstract using the project's query preprocessing pipeline."""
    clean_abstract = (abstract or "").strip()
    if clean:
        clean_abstract = clean_text(clean_abstract, remove_stopwords=True)
    return clean_abstract


def build_journal_text(aims_and_scope: str, clean: bool = True) -> str:
    """Prepares journal aims and scope using the project's journal preprocessing pipeline."""
    raw_scope = (aims_and_scope or "").strip()
    if clean:
        return clean_text(raw_scope, remove_stopwords=True)
    return raw_scope


class SpecterEmbedder:
    """Standalone wrapper around SentenceTransformer ('allenai-specter')."""

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL, device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._is_loaded = False

    def load(self) -> None:
        if self._is_loaded:
            return

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError(
                "sentence-transformers is not installed. Run: pip install sentence-transformers torch"
            ) from e

        self._model = SentenceTransformer(self.model_name, device=self.device)
        if hasattr(self._model, "get_embedding_dimension"):
            dim = self._model.get_embedding_dimension()
        else:
            dim = self._model.get_sentence_embedding_dimension()

        if dim != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Model dimension {dim} does not match expected dimension {EMBEDDING_DIMENSION}"
            )

        self._is_loaded = True

    def embed(self, text: str) -> list[float]:
        if not self._is_loaded or self._model is None:
            self.load()

        embedding = self._model.encode(text, show_progress_bar=False)
        if hasattr(embedding, "tolist"):
            return embedding.tolist()
        return list(embedding)


def raw_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Computes exact raw cosine similarity: (A · B) / (||A|| * ||B||).
    """
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def compute_similarity(
    abstract: str,
    aims_and_scope: str,
    clean: bool = True,
    embedder: Optional[SpecterEmbedder] = None,
) -> float:
    """Preprocesses inputs, generates SPECTER embeddings, and returns raw cosine similarity."""
    processed_abstract = build_query_text(abstract, clean=clean)
    processed_scope = build_journal_text(aims_and_scope, clean=clean)

    if not processed_abstract or not processed_scope:
        raise ValueError("Both abstract and journal aims & scope must contain valid text.")

    model = embedder or SpecterEmbedder()
    abstract_vec = model.embed(processed_abstract)
    scope_vec = model.embed(processed_scope)

    return raw_cosine_similarity(abstract_vec, scope_vec)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute raw SPECTER cosine similarity between an abstract and a journal's aims & scope."
    )
    parser.add_argument("--abstract", type=str, help="Manuscript abstract text")
    parser.add_argument("--aims-and-scope", type=str, help="Journal aims and scope text")
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Inference device ('cpu' or 'cuda', default: 'cpu')",
    )
    args = parser.parse_args()

    abstract = args.abstract
    aims_and_scope = args.aims_and_scope

    if not abstract:
        abstract = input("Enter Manuscript Abstract:\n> ").strip()
    if not aims_and_scope:
        aims_and_scope = input("\nEnter Journal Aims and Scope:\n> ").strip()

    if not abstract or not aims_and_scope:
        print("Error: Both Manuscript Abstract and Journal Aims and Scope are required.", file=sys.stderr)
        sys.exit(1)

    print(f"\nLoading '{DEFAULT_EMBEDDING_MODEL}' model on '{args.device}'...", file=sys.stderr)
    embedder = SpecterEmbedder(device=args.device)
    embedder.load()

    score = compute_similarity(
        abstract=abstract,
        aims_and_scope=aims_and_scope,
        clean=True,
        embedder=embedder,
    )

    print(f"\nRaw Cosine Similarity Score: {score}")


if __name__ == "__main__":
    main()