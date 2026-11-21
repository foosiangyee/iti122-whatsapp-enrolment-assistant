import pytest

from app import config


@pytest.fixture
def kb_dir():
    d = config.kb_dir()
    if not list(d.glob("*.pdf")):
        pytest.skip(f"no PDFs in {d}; copy the Data Kit knowledge_base/ here or set KNOWLEDGE_BASE_DIR")
    return d


@pytest.fixture
def seed_dir():
    d = config.seed_dir()
    if not (d / "class_schedule.csv").exists():
        pytest.skip(f"no seed CSVs in {d}; copy the Data Kit seed_data/ here or set SEED_DATA_DIR")
    return d
