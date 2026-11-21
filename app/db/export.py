"""State export for GET /admin/export.

PROVISIONAL: the exact shape is fixed by export_schema.json, which was not in the received kit.
Keep this a thin mapping over the tables so only this file changes when the schema arrives.
"""
from app.db.database import Database
from app.money import to_dollars

_MONEY_SUFFIX = "_cents"


def _dollars(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if k.endswith(_MONEY_SUFFIX):
            out[k[: -len(_MONEY_SUFFIX)]] = to_dollars(v)
        else:
            out[k] = v
    return out


def export_state(db: Database) -> dict:
    q = lambda sql: [_dollars(dict(r)) for r in db.conn.execute(sql)]  # noqa: E731
    return {
        "leads": q("SELECT * FROM leads ORDER BY first_seen, phone"),
        "learners": q("SELECT * FROM learners ORDER BY phone"),
        "enrolments": q("SELECT * FROM enrolments ORDER BY id"),
        "payments": q("SELECT * FROM payments ORDER BY id"),
        "cancellations": q("SELECT * FROM cancellations ORDER BY id"),
        "escalations": q("SELECT * FROM escalations ORDER BY id"),
    }
