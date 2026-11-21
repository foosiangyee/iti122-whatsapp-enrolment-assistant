import shutil
import time

from app.rag.knowledge_base import KnowledgeBase


def test_indexes_every_pdf(kb_dir):
    kb = KnowledgeBase(kb_dir)
    assert set(kb.sources) == {p.name for p in kb_dir.glob("*.pdf")}
    assert len(kb) > 20


def test_payee_uen_is_found_with_citation(kb_dir):
    kb = KnowledgeBase(kb_dir)
    hits = kb.search("What is the PayNow UEN for payment?", k=5)
    assert any("209912345K" in h.chunk.text for h in hits)
    assert all(h.citation.startswith("[") and ", p." in h.citation for h in hits)


def test_cancellation_rule_comes_from_terms_or_sop(kb_dir):
    kb = KnowledgeBase(kb_dir)
    top = kb.search("Can I cancel after the first day of class and get a refund?", k=3)
    assert any("Terms" in h.chunk.source or "SOP" in h.chunk.source for h in top)
    assert any("first day" in h.chunk.text for h in top)


def test_funding_rates_are_retrieved_not_hard_coded(kb_dir):
    kb = KnowledgeBase(kb_dir)
    hits = kb.search("SSG funding rate for WSQ courses Singapore Citizens aged 40 and above", k=3)
    assert any("70%" in h.chunk.text for h in hits)


def test_question_outside_the_documents_is_not_answerable(kb_dir):
    kb = KnowledgeBase(kb_dir)
    assert kb.has_answer("What is the PayNow UEN for payment?")
    assert not kb.has_answer("Does the Academy offer a free parking voucher for motorcycle riders?")


def test_new_pdf_is_picked_up_without_code_change(kb_dir, tmp_path):
    for p in kb_dir.glob("*.pdf"):
        shutil.copy(p, tmp_path / p.name)
    kb = KnowledgeBase(tmp_path)
    before = len(kb.sources)
    assert kb.refresh() is False  # nothing changed

    time.sleep(0.01)
    shutil.copy(kb_dir / "CADC_Joining_Instructions.pdf", tmp_path / "Fee_Notice_copy.pdf")
    assert kb.search("joining instructions", k=1)  # search triggers the re-index
    assert len(kb.sources) == before + 1
    assert "Fee_Notice_copy.pdf" in kb.sources
