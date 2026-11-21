-- SQLite schema replacing the Enrolment Tracker sheets (SOP section 3) plus memory per phone number.
-- Money columns are integer cents. Dates are ISO text (YYYY-MM-DD); timestamps are ISO date-time.
-- NRIC/FIN is stored MASKED only (SOP 13.1), e.g. S****567D.

CREATE TABLE IF NOT EXISTS leads (
    phone        TEXT PRIMARY KEY,
    name         TEXT,
    source       TEXT,
    courses      TEXT NOT NULL DEFAULT '',          -- comma-separated course codes of interest
    status       TEXT NOT NULL DEFAULT 'NEW',       -- NEW / ENGAGED / CONVERTED
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    remarks      TEXT
);

CREATE TABLE IF NOT EXISTS learners (
    phone        TEXT PRIMARY KEY,                  -- WhatsApp number identifies the learner
    name         TEXT,                              -- as in NRIC/FIN
    nric_masked  TEXT,
    dob          TEXT,
    residency    TEXT,                              -- SC / PR / pass type
    email        TEXT,
    mobile       TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS classes (               -- loaded from seed_data/class_schedule.csv
    class_id     TEXT PRIMARY KEY,
    course_code  TEXT NOT NULL,
    start_date   TEXT NOT NULL,
    end_date     TEXT NOT NULL,
    label        TEXT,
    capacity     INTEGER NOT NULL,
    seats_taken  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS certificates (          -- loaded from seed_data/certificate_register.csv
    certificate_no  TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    nric_masked     TEXT,
    course_code     TEXT NOT NULL,
    completion_date TEXT
);

CREATE TABLE IF NOT EXISTS enrolments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    phone            TEXT NOT NULL REFERENCES learners(phone),
    course_code      TEXT NOT NULL,
    class_id         TEXT REFERENCES classes(class_id),
    invoice_no       TEXT UNIQUE,
    invoice_date     TEXT,
    list_fee_cents   INTEGER,
    gst_cents        INTEGER,
    ssg_funding_cents INTEGER,
    nett_fee_cents   INTEGER,
    sfc_cents        INTEGER,                       -- SkillsFuture Credit part
    paynow_cents     INTEGER,                       -- PayNow part due
    due_date         TEXT,
    paynow_received_cents INTEGER NOT NULL DEFAULT 0,
    sfc_status       TEXT,                          -- e.g. Matched / Pending / not used
    payment_status   TEXT,
    receipt_no       TEXT,
    status           TEXT NOT NULL DEFAULT 'DETAILS_PENDING',
    remarks          TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (              -- every screenshot checked (SOP section 8)
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at    TEXT NOT NULL,
    invoice_no    TEXT,
    type          TEXT NOT NULL,                    -- PayNow / SFC claim
    reference     TEXT,                             -- transaction reference or claim ID
    amount_cents  INTEGER,
    result        TEXT NOT NULL,                    -- see app/codes.py PAYMENT_RESULTS
    remarks       TEXT
);

CREATE TABLE IF NOT EXISTS cancellations (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    request_date       TEXT NOT NULL,
    invoice_no         TEXT NOT NULL,
    name               TEXT,
    class_id           TEXT,
    reason             TEXT,
    days_before_class  INTEGER,
    credit_note_cents  INTEGER,
    paynow_received_cents INTEGER,
    refund_cents       INTEGER,
    credit_note_no     TEXT,
    credit_note_date   TEXT,
    status             TEXT NOT NULL DEFAULT 'ISSUED'
);

CREATE TABLE IF NOT EXISTS escalations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    phone       TEXT NOT NULL,
    code        TEXT NOT NULL,                      -- E1 to E6
    owner       TEXT NOT NULL,
    detail      TEXT,
    paused      INTEGER NOT NULL,                   -- 1 = automation paused for this learner
    status      TEXT NOT NULL DEFAULT 'OPEN',       -- OPEN / CLOSED
    created_at  TEXT NOT NULL,
    closed_at   TEXT
);

CREATE TABLE IF NOT EXISTS messages (               -- conversation history (memory)
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    phone      TEXT NOT NULL,
    direction  TEXT NOT NULL,                       -- in / out
    ts         TEXT NOT NULL,
    text       TEXT,
    media      TEXT,                                -- image file name, if any
    intents    TEXT,                                -- JSON, set by the intent agent
    trace_id   TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_phone ON messages(phone, id);

CREATE TABLE IF NOT EXISTS session_state (          -- slot-filling and pending-confirmation state per phone
    phone       TEXT PRIMARY KEY,
    state_json  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS counters (               -- document numbers: INV / REC / CN
    name   TEXT NOT NULL,
    year   INTEGER NOT NULL,
    value  INTEGER NOT NULL,
    PRIMARY KEY (name, year)
);
