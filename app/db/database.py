"""SQLite access for the assistant. One Database object per app; methods map to tracker sheets.

Amounts in/out of this layer are integer cents. Callers pass `now` (an ISO string) where the
scenario supplies its own clock; otherwise the current time is used.
"""
import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from app import config
from app.codes import ENROLMENT_STATUSES, ESCALATION_CODES, LEAD_STATUSES, PAYMENT_RESULTS

SCHEMA = Path(__file__).with_name("schema.sql")
_LEAD_ORDER = {s: i for i, s in enumerate(LEAD_STATUSES)}

LEARNER_FIELDS = {"name", "nric_masked", "dob", "residency", "email", "mobile"}
ENROLMENT_FIELDS = {
    "class_id", "invoice_no", "invoice_date", "list_fee_cents", "gst_cents", "ssg_funding_cents",
    "nett_fee_cents", "sfc_cents", "paynow_cents", "due_date", "paynow_received_cents",
    "sfc_status", "payment_status", "receipt_no", "status", "remarks", "course_code",
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str | Path | None = None):
        target = str(path) if path is not None else str(config.db_path())
        if target != ":memory:":
            Path(target).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(target)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.init_schema()

    # ---------- setup ----------
    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA.read_text(encoding="utf-8"))

    def reset(self) -> None:
        """Empty every table (the runner resets the app before each test case)."""
        tables = [r["name"] for r in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        with self.conn:
            self.conn.execute("PRAGMA foreign_keys = OFF")
            for t in tables:
                self.conn.execute(f"DROP TABLE IF EXISTS {t}")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.init_schema()

    def load_seed(self, directory: Path | str | None = None) -> dict:
        """Load class schedule and certificate register from the CSV files in the seed folder."""
        d = Path(directory) if directory else config.seed_dir()
        counts = {"classes": 0, "certificates": 0}
        sched = d / "class_schedule.csv"
        if sched.exists():
            with sched.open(newline="", encoding="utf-8-sig") as f, self.conn:
                for r in csv.DictReader(f):
                    self.conn.execute(
                        "INSERT OR REPLACE INTO classes VALUES (?,?,?,?,?,?,?)",
                        (r["class_id"], r["course_code"], r["start_date"], r["end_date"],
                         r.get("label"), int(r["capacity"]), int(r["seats_taken"])))
                    counts["classes"] += 1
        reg = d / "certificate_register.csv"
        if reg.exists():
            with reg.open(newline="", encoding="utf-8-sig") as f, self.conn:
                for r in csv.DictReader(f):
                    self.conn.execute(
                        "INSERT OR REPLACE INTO certificates VALUES (?,?,?,?,?)",
                        (r["certificate_no"], r["name"], r.get("nric_masked"),
                         r["course_code"], r.get("completion_date")))
                    counts["certificates"] += 1
        return counts

    # ---------- leads ----------
    def upsert_lead(self, phone: str, *, name=None, course=None, source=None, status=None,
                    remarks=None, now: str | None = None) -> dict:
        now = now or now_iso()
        row = self.conn.execute("SELECT * FROM leads WHERE phone=?", (phone,)).fetchone()
        if row is None:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO leads (phone,name,source,courses,status,first_seen,last_seen,remarks)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (phone, name, source, course or "", status or "NEW", now, now, remarks))
            return self.get_lead(phone)
        courses = [c for c in row["courses"].split(",") if c]
        if course and course not in courses:
            courses.append(course)
        new_status = row["status"]
        if status and _LEAD_ORDER[status] > _LEAD_ORDER[new_status]:  # status only moves forward
            new_status = status
        with self.conn:
            self.conn.execute(
                "UPDATE leads SET name=COALESCE(?,name), source=COALESCE(?,source), courses=?,"
                " status=?, last_seen=?, remarks=COALESCE(?,remarks) WHERE phone=?",
                (name, source, ",".join(courses), new_status, now, remarks, phone))
        return self.get_lead(phone)

    def get_lead(self, phone: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM leads WHERE phone=?", (phone,)).fetchone()
        return dict(r) if r else None

    # ---------- learners ----------
    def upsert_learner(self, phone: str, now: str | None = None, **fields) -> dict:
        bad = set(fields) - LEARNER_FIELDS
        if bad:
            raise ValueError(f"unknown learner fields: {sorted(bad)}")
        now = now or now_iso()
        if self.get_learner(phone) is None:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO learners (phone,created_at,updated_at) VALUES (?,?,?)", (phone, now, now))
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            with self.conn:
                self.conn.execute(f"UPDATE learners SET {sets}, updated_at=? WHERE phone=?",
                                  (*fields.values(), now, phone))
        return self.get_learner(phone)

    def get_learner(self, phone: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM learners WHERE phone=?", (phone,)).fetchone()
        return dict(r) if r else None

    # ---------- classes ----------
    def get_class(self, class_id: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM classes WHERE class_id=?", (class_id,)).fetchone()
        return self._class_dict(r) if r else None

    def list_classes(self, course_code: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM classes", ()
        if course_code:
            q, args = q + " WHERE course_code=?", (course_code,)
        return [self._class_dict(r) for r in self.conn.execute(q + " ORDER BY start_date", args)]

    @staticmethod
    def _class_dict(r) -> dict:
        d = dict(r)
        d["seats_left"] = d["capacity"] - d["seats_taken"]
        return d

    def adjust_seats(self, class_id: str, delta: int) -> int:
        """Take (+1) or release (-1) seats. Refuses to go below zero or above capacity."""
        c = self.get_class(class_id)
        if c is None:
            raise KeyError(class_id)
        taken = c["seats_taken"] + delta
        if not 0 <= taken <= c["capacity"]:
            raise ValueError(f"seats_taken would be {taken} for {class_id} (capacity {c['capacity']})")
        with self.conn:
            self.conn.execute("UPDATE classes SET seats_taken=? WHERE class_id=?", (taken, class_id))
        return c["capacity"] - taken

    def has_certificate(self, course_code: str, nric_masked: str | None = None, name: str | None = None) -> bool:
        """Certificate Register lookup (CSA-220 prerequisite). Match by masked NRIC, else by name."""
        if nric_masked:
            r = self.conn.execute(
                "SELECT 1 FROM certificates WHERE course_code=? AND nric_masked=?", (course_code, nric_masked)).fetchone()
            if r:
                return True
        if name:
            r = self.conn.execute(
                "SELECT 1 FROM certificates WHERE course_code=? AND lower(name)=lower(?)", (course_code, name)).fetchone()
            return r is not None
        return False

    # ---------- enrolments ----------
    def create_enrolment(self, phone: str, course_code: str, now: str | None = None, **fields) -> int:
        now = now or now_iso()
        self._check_enrolment_fields(fields)
        cols = ["phone", "course_code", "created_at", "updated_at", *fields]
        vals = [phone, course_code, now, now, *fields.values()]
        with self.conn:
            cur = self.conn.execute(
                f"INSERT INTO enrolments ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)
        return cur.lastrowid

    def update_enrolment(self, enrolment_id: int, now: str | None = None, **fields) -> dict:
        self._check_enrolment_fields(fields)
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            with self.conn:
                self.conn.execute(f"UPDATE enrolments SET {sets}, updated_at=? WHERE id=?",
                                  (*fields.values(), now or now_iso(), enrolment_id))
        return self.get_enrolment(enrolment_id)

    @staticmethod
    def _check_enrolment_fields(fields: dict) -> None:
        bad = set(fields) - ENROLMENT_FIELDS
        if bad:
            raise ValueError(f"unknown enrolment fields: {sorted(bad)}")
        if "status" in fields and fields["status"] not in ENROLMENT_STATUSES:
            raise ValueError(f"unknown enrolment status {fields['status']!r}")

    def get_enrolment(self, enrolment_id: int) -> dict | None:
        r = self.conn.execute("SELECT * FROM enrolments WHERE id=?", (enrolment_id,)).fetchone()
        return dict(r) if r else None

    def get_by_invoice(self, invoice_no: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM enrolments WHERE invoice_no=?", (invoice_no,)).fetchone()
        return dict(r) if r else None

    def find_enrolments(self, phone: str | None = None, statuses: tuple | list | None = None) -> list[dict]:
        q, args, where = "SELECT * FROM enrolments", [], []
        if phone:
            where.append("phone=?"); args.append(phone)
        if statuses:
            where.append(f"status IN ({','.join('?' * len(statuses))})"); args.extend(statuses)
        if where:
            q += " WHERE " + " AND ".join(where)
        return [dict(r) for r in self.conn.execute(q + " ORDER BY id", args)]

    def next_number(self, name: str, year: int, start: int = 1) -> int:
        """Next running number for a document series ('INV', 'REC', 'CN') in a year."""
        with self.conn:
            r = self.conn.execute("SELECT value FROM counters WHERE name=? AND year=?", (name, year)).fetchone()
            value = (r["value"] + 1) if r else start
            self.conn.execute("INSERT OR REPLACE INTO counters VALUES (?,?,?)", (name, year, value))
        return value

    # ---------- payments ----------
    def add_payment(self, invoice_no: str | None, type_: str, result: str, *, reference=None,
                    amount_cents=None, remarks=None, now: str | None = None) -> int:
        if result not in PAYMENT_RESULTS:
            raise ValueError(f"unknown payment result {result!r}")
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO payments (checked_at,invoice_no,type,reference,amount_cents,result,remarks)"
                " VALUES (?,?,?,?,?,?,?)",
                (now or now_iso(), invoice_no, type_, reference, amount_cents, result, remarks))
        return cur.lastrowid

    def reference_recorded(self, reference: str) -> bool:
        """SOP P3: has this transaction reference already been recorded?"""
        return self.conn.execute("SELECT 1 FROM payments WHERE reference=?", (reference,)).fetchone() is not None

    def list_payments(self, invoice_no: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM payments", ()
        if invoice_no:
            q, args = q + " WHERE invoice_no=?", (invoice_no,)
        return [dict(r) for r in self.conn.execute(q + " ORDER BY id", args)]

    # ---------- cancellations ----------
    def add_cancellation(self, invoice_no: str, *, request_date: str, name=None, class_id=None, reason=None,
                         days_before_class=None, credit_note_cents=None, paynow_received_cents=None,
                         refund_cents=None, credit_note_no=None, credit_note_date=None) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO cancellations (request_date,invoice_no,name,class_id,reason,days_before_class,"
                "credit_note_cents,paynow_received_cents,refund_cents,credit_note_no,credit_note_date)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (request_date, invoice_no, name, class_id, reason, days_before_class, credit_note_cents,
                 paynow_received_cents, refund_cents, credit_note_no, credit_note_date))
        return cur.lastrowid

    def list_cancellations(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM cancellations ORDER BY id")]

    # ---------- escalations ----------
    def add_escalation(self, phone: str, code: str, detail: str | None = None, now: str | None = None) -> int:
        if code not in ESCALATION_CODES:
            raise ValueError(f"unknown escalation code {code!r}")
        owner, paused = ESCALATION_CODES[code]
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO escalations (phone,code,owner,detail,paused,created_at) VALUES (?,?,?,?,?,?)",
                (phone, code, owner, detail, int(paused), now or now_iso()))
        return cur.lastrowid

    def is_paused(self, phone: str) -> bool:
        """True while an OPEN hand-off (E1, E2, E4) is pending for this learner (SOP 12.1)."""
        return self.conn.execute(
            "SELECT 1 FROM escalations WHERE phone=? AND paused=1 AND status='OPEN'", (phone,)).fetchone() is not None

    def close_escalation(self, escalation_id: int, now: str | None = None) -> None:
        with self.conn:
            self.conn.execute("UPDATE escalations SET status='CLOSED', closed_at=? WHERE id=?",
                              (now or now_iso(), escalation_id))

    def list_escalations(self, phone: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM escalations", ()
        if phone:
            q, args = q + " WHERE phone=?", (phone,)
        return [dict(r) for r in self.conn.execute(q + " ORDER BY id", args)]

    # ---------- conversation memory ----------
    def log_message(self, phone: str, direction: str, text: str | None = None, *, media=None,
                    intents=None, trace_id=None, ts: str | None = None) -> int:
        if direction not in ("in", "out"):
            raise ValueError("direction must be 'in' or 'out'")
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO messages (phone,direction,ts,text,media,intents,trace_id) VALUES (?,?,?,?,?,?,?)",
                (phone, direction, ts or now_iso(), text, media,
                 json.dumps(intents) if intents is not None else None, trace_id))
        return cur.lastrowid

    def history(self, phone: str, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE phone=? ORDER BY id DESC LIMIT ?", (phone, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def get_state(self, phone: str) -> dict:
        r = self.conn.execute("SELECT state_json FROM session_state WHERE phone=?", (phone,)).fetchone()
        return json.loads(r["state_json"]) if r else {}

    def set_state(self, phone: str, state: dict, now: str | None = None) -> None:
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO session_state VALUES (?,?,?)",
                              (phone, json.dumps(state), now or now_iso()))
