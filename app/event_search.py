"""Offline lexical relevance; scores describe text overlap, never market impact."""
from collections import Counter
from math import log, sqrt
import re
import unicodedata


def tokens(text):
    return re.findall(r'\w+', unicodedata.normalize('NFKC', text).casefold(), flags=re.UNICODE)


def rank(query, documents):
    """TF-IDF cosine over the complete filtered corpus, with shared query vocabulary.

    Return index, score and overlapping terms. Ties preserve input order.
    Unknown query terms contribute to the query norm; punctuation-only queries
    and documents with no shared terms produce no matches.
    """
    counts = [Counter(tokens(text)) for text in documents]
    q = Counter(tokens(query))
    if not q:
        return []
    frequency = Counter(term for document in counts for term in document)
    vocabulary = set(q) | set(frequency)
    weights = {term: 1 + log((1 + len(counts)) / (1 + frequency[term])) for term in vocabulary}
    vector = {term: count * weights[term] for term, count in q.items()}
    norm = sqrt(sum(value * value for value in vector.values()))
    results = []
    for index, document in enumerate(counts):
        shared = sorted(set(q) & set(document))
        if not shared:
            continue
        values = {term: count * weights[term] for term, count in document.items()}
        score = sum(vector[term] * values[term] for term in shared) / (norm * sqrt(sum(value * value for value in values.values())))
        results.append((index, min(1.0, score), shared))
    return sorted(results, key=lambda item: -item[1])
