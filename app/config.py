"""Runtime configuration. Values come from environment variables (.env), never from code.

Paths are resolved relative to the repo root unless absolute. Functions (not constants) are
used so tests can override environment variables per test.
"""
import os
from pathlib import Path

try:  # python-dotenv is optional at import time
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

ROOT = Path(__file__).resolve().parent.parent
if load_dotenv:
    load_dotenv(ROOT / ".env")


def _path(name: str, default: str) -> Path:
    p = Path(os.getenv(name) or default)
    return p if p.is_absolute() else ROOT / p


def kb_dir() -> Path:
    return _path("KNOWLEDGE_BASE_DIR", "knowledge_base")


def seed_dir() -> Path:
    return _path("SEED_DATA_DIR", "seed_data")


def templates_dir() -> Path:
    return _path("TEMPLATES_DIR", "templates")


def results_dir() -> Path:
    return _path("RESULTS_DIR", "results")


def db_path() -> Path:
    return _path("DB_PATH", "data/app.db")


def rag_min_coverage() -> float:
    """Share of query terms the best chunk must contain before we treat a question as answerable.

    Tune against scenario S12 (a question the documents cannot answer, which must raise E3).
    """
    return float(os.getenv("RAG_MIN_COVERAGE") or 0.5)
