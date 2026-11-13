"""Deterministic lexical relevance over a vector-recalled candidate set."""

import math
import re
from collections import Counter


def tokens(text):
    return re.findall(r"[a-z0-9_.-]+|[\u3400-\u9fff]", text.casefold())


def rank(query, texts):
    query_terms = set(tokens(query))
    docs = [Counter(tokens(t)) for t in texts]
    avg = sum(d.total() for d in docs) / max(1, len(docs)) or 1
    df = Counter(word for d in docs for word in d)
    scored = []
    for i, doc in enumerate(docs):
        score = 0
        for term in query_terms & doc.keys():
            idf = math.log(1 + (len(docs) - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * doc[term] * 2.2 / (doc[term] + 1.2 * (0.25 + 0.75 * doc.total() / avg))
        score = score / (1 + score)
        scored.append({"index": i, "score": score})
    return sorted(scored, key=lambda r: (-r["score"], r["index"]))
