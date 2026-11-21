"""Read PDFs and split them into citable chunks.

Nothing about the documents' content is hard-coded here: any PDF dropped in the knowledge-base
folder is read the same way. Each chunk remembers its file and page so answers can cite it.
"""
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

MAX_CHARS = 1000  # soft limit for one chunk

# A section heading starts with a number and ONE space ("6.4 Class rules", "1. Introduction") or
# with "Appendix X". Table rows have several spaces after the number, so they do not match.
HEADING = re.compile(r"^(?:\d+(?:\.\d+)*\.? (?=\S)|Appendix [A-Z]\b)")


@dataclass(frozen=True)
class Chunk:
    source: str   # file name, e.g. CADC_Course_Admin_SOP_v3.0.pdf
    page: int     # 1-based page where the chunk starts
    section: str  # heading line the chunk belongs to ("" if none)
    text: str

    @property
    def citation(self) -> str:
        return f"[{self.source}, p.{self.page}]"


def _normalise(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip())


def read_pdf_pages(path: Path) -> list[str]:
    """Return the text of each page. Layout mode keeps table rows on one line."""
    reader = PdfReader(str(path))
    pages = [(p.extract_text(extraction_mode="layout") or "") for p in reader.pages]
    return _drop_repeated_lines(pages)


def _drop_repeated_lines(pages: list[str]) -> list[str]:
    """Remove running headers/footers: short lines that repeat on 2+ pages (digits ignored)."""
    if len(pages) < 2:
        return pages
    counts: Counter = Counter()
    for text in pages:
        counts.update({_normalise(l) for l in text.splitlines() if l.strip()})
    repeated = {k for k, v in counts.items() if v >= 2 and len(k) < 140}
    return ["\n".join(l for l in text.splitlines() if _normalise(l) not in repeated) for text in pages]


def _clean(line: str) -> str:
    line = line.strip()
    return re.sub(r"\s{3,}", "  |  ", line)  # table column gaps become a visible separator


def chunk_pdf(path: Path) -> list[Chunk]:
    source = path.name
    chunks: list[Chunk] = []
    buf: list[str] = []
    state = {"page": 1, "section": ""}

    def flush():
        text = "\n".join(buf).strip()
        if text:
            chunks.append(Chunk(source, state["page"], state["section"], text))
        buf.clear()

    for page_no, page_text in enumerate(read_pdf_pages(path), start=1):
        for raw in page_text.splitlines():
            line = _clean(raw)
            if not line:
                continue
            is_heading = bool(HEADING.match(line))
            too_long = sum(len(b) + 1 for b in buf) + len(line) > MAX_CHARS
            if (is_heading or too_long) and buf:
                flush()
            if not buf:
                state["page"] = page_no
            if is_heading:
                state["section"] = line[:80]
            buf.append(line)
    flush()
    return chunks


def chunk_directory(directory: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for pdf in sorted(Path(directory).glob("*.pdf")):
        chunks.extend(chunk_pdf(pdf))
    return chunks
