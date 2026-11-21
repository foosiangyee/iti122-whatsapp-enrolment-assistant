"""Try the knowledge base from the command line:  python scripts/ask_kb.py "can I use SFC for DA-101?" """
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.knowledge_base import KnowledgeBase  # noqa: E402

if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "What is the PayNow UEN?"
    kb = KnowledgeBase()
    print(f"{len(kb)} chunks from {len(kb.sources)} PDFs; answerable: {kb.has_answer(question)}\n")
    for h in kb.search(question, k=3):
        print(f"{h.citation}  score={h.score:.2f}  coverage={h.coverage:.2f}")
        print(h.chunk.text[:400], "\n")
