"""A small BM25 ranking function plus the tokenizer that feeds it (no external dependency)."""
import math
import re
from collections import Counter

STOPWORDS = frozenset(
    "a an and are as at be by can do does for from has have how i if in is it its me my of on or "
    "so than that the their them then there these they this to us was we what when where which who "
    "will with would you your".split()
)

_WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def tokenize(text: str) -> list[str]:
    """Lower-case words. Hyphenated codes such as 'da-101' also yield 'da' and '101'."""
    out: list[str] = []
    for w in _WORD.findall(text.lower()):
        parts = w.split("-") if "-" in w else []
        for t in [w, *parts]:
            if t in STOPWORDS:
                continue
            if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
                t = t[:-1]  # crude plural handling: fees -> fee
            out.append(t)
    return out


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = [len(d) for d in docs]
        self.avg = (sum(self.len) / len(docs)) if docs else 0.0
        df: Counter = Counter()
        for c in self.tf:
            df.update(c.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> list[float]:
        result = []
        for tf, dl in zip(self.tf, self.len):
            s = 0.0
            for t in set(query):
                f = tf.get(t, 0)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self.avg or 1))
                s += self.idf[t] * f * (self.k1 + 1) / denom
            result.append(s)
        return result
