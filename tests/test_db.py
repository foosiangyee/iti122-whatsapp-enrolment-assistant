import pytest

from app.db.database import Database
from app.db.export import export_state
from app.money import to_cents


@pytest.fixture
def db(seed_dir):
    d = Database(":memory:")
    d.load_seed(seed_dir)
    return d


def test_seed_loads_classes_and_register(db):
    assert len(db.list_classes()) == 20
    assert db.get_class("DA101-2611A")["seats_left"] == 10
    assert db.has_certificate("DA-101", name="Abdul Rahim bin Salleh")
    assert not db.has_certificate("DA-101", name="Nobody Here")


def test_lead_status_only_moves_forward(db):
    db.upsert_lead("+6590000001", course="DA-101", status="ENGAGED")
    db.upsert_lead("+6590000001", course="IPC-110", status="CONVERTED")
    lead = db.upsert_lead("+6590000001", status="NEW")
    assert lead["status"] == "CONVERTED"
    assert lead["courses"] == "DA-101,IPC-110"


def test_enrolment_lifecycle_and_seats(db):
    db.upsert_learner("+6590000002", name="Test Learner", nric_masked="S****567D", residency="SC")
    eid = db.create_enrolment("+6590000002", "DA-101", class_id="DA101-2611A")
    n = db.next_number("INV", 2026)
    e = db.update_enrolment(eid, invoice_no=f"INV-2026-{n:04d}", status="INVOICED",
                            nett_fee_cents=to_cents("654.00"))
    assert e["status"] == "INVOICED" and e["nett_fee_cents"] == 65400
    assert db.adjust_seats("DA101-2611A", +1) == 9
    assert db.adjust_seats("DA101-2611A", -1) == 10
    assert db.next_number("INV", 2026) == n + 1
    with pytest.raises(ValueError):
        db.update_enrolment(eid, status="PAID")
    with pytest.raises(ValueError):
        db.adjust_seats("DA101-2610B", +1)  # class is full


def test_payment_reference_check_and_result_codes(db):
    db.add_payment("INV-2026-0001", "PayNow", "MATCHED", reference="SCB123", amount_cents=15400)
    assert db.reference_recorded("SCB123")
    assert not db.reference_recorded("SCB999")
    with pytest.raises(ValueError):
        db.add_payment("INV-2026-0001", "PayNow", "PAID")


def test_escalation_pauses_only_for_hand_off_codes(db):
    db.add_escalation("+6590000003", "E3", "unknown question")
    assert not db.is_paused("+6590000003")
    e2 = db.add_escalation("+6590000003", "E2", "overpaid")
    assert db.is_paused("+6590000003")
    db.close_escalation(e2)
    assert not db.is_paused("+6590000003")


def test_memory_per_phone(db):
    db.log_message("+6590000004", "in", "hi")
    db.log_message("+6590000004", "out", "hello")
    db.log_message("+6590000005", "in", "other learner")
    assert [m["text"] for m in db.history("+6590000004")] == ["hi", "hello"]
    db.set_state("+6590000004", {"course": "DA-101"})
    assert db.get_state("+6590000004") == {"course": "DA-101"}
    assert db.get_state("+6590000005") == {}


def test_export_converts_cents_to_dollars_and_reset_empties(db):
    db.upsert_learner("+6590000006", name="X")
    db.create_enrolment("+6590000006", "DA-101", nett_fee_cents=65400)
    out = export_state(db)
    assert out["enrolments"][0]["nett_fee"] == 654.0
    db.reset()
    db.load_seed()
    assert export_state(db)["enrolments"] == []
