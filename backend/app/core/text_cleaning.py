import re
import unicodedata
from typing import Iterable, Set

#stopwords set (derived from NLTK & scikit learn standard lists)
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

    #normalizing unicode
    text = unicodedata.normalize("NFKD", text)

    #remove URLs
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)

    #remove HTML tags if present
    text = re.sub(r"<[^>]+>", " ", text)

    #stopwords to filter
    stopwords = DEFAULT_STOPWORDS
    if custom_stopwords:
        stopwords = stopwords.union(set(custom_stopwords))

    if remove_punctuation:
        #replace non alphanumeric characters (except spaces) with space
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

