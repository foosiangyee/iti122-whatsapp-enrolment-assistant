"""Knowledge base over the Academy's PDFs: search with citations, rebuilt when the folder changes."""
from dataclasses import dataclass
from pathlib import Path

from app import config
from app.rag.bm25 import BM25, tokenize
from app.rag.ingest import Chunk, chunk_directory


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    coverage: float  # share of the question's terms found in this chunk (0 to 1)

    @property
    def citation(self) -> str:
        return self.chunk.citation


class KnowledgeBase:
    def __init__(self, directory: Path | str | None = None):
        self.directory = Path(directory) if directory else config.kb_dir()
        self._signature: tuple = ()
        self._chunks: list[Chunk] = []
        self._tokens: list[set[str]] = []
        self._bm25: BM25 | None = None
        self.refresh()

    def _scan(self) -> tuple:
        files = sorted(self.directory.glob("*.pdf"))
        return tuple((f.name, f.stat().st_mtime_ns, f.stat().st_size) for f in files)

    def refresh(self) -> bool:
        """Re-index if any PDF was added, changed or removed. Returns True when it re-indexed."""
        sig = self._scan()
        if sig == self._signature:
            return False
        self._chunks = chunk_directory(self.directory)
        docs = [tokenize(c.text) for c in self._chunks]
        self._tokens = [set(d) for d in docs]
        self._bm25 = BM25(docs)
        self._signature = sig
        return True

    @property
    def sources(self) -> list[str]:
        return [name for name, _, _ in self._signature]

    def __len__(self) -> int:
        return len(self._chunks)

    def search(self, query: str, k: int = 4) -> list[Hit]:
        self.refresh()
        q = tokenize(query)
        if not q or not self._bm25:
            return []
        scores = self._bm25.scores(q)
        qset = set(q)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        hits = []
        for i in ranked[:k]:
            if scores[i] <= 0:
                break
            cov = len(qset & self._tokens[i]) / len(qset)
            hits.append(Hit(self._chunks[i], scores[i], cov))
        return hits

    def has_answer(self, query: str, min_coverage: float | None = None) -> bool:
        """True when the best chunk contains enough of the question's terms.

        A False result is the cue to tell the learner a colleague will reply and record E3.
        """
        threshold = config.rag_min_coverage() if min_coverage is None else min_coverage
        hits = self.search(query, k=1)
        return bool(hits) and hits[0].coverage >= threshold
