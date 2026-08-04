"""
db.py — PostgreSQL storage for enrolled employees and attendance records.

Migrated from SQLite. Function names and signatures are UNCHANGED from
the SQLite version, so main.py (or app.py) needs no changes at all --
only this file and the connection config change.

Connection string comes from the DATABASE_URL environment variable,
e.g.:
    postgresql://username:password@localhost:5432/attendance

Embeddings are stored as raw float32 bytes (BYTEA) and reloaded as
numpy arrays -- same approach as before, just SQLite BLOB -> Postgres
BYTEA. Fine at POC/small-company scale (hundreds of employees); beyond
that, look at the pgvector extension for a proper vector index.
"""
import os
import psycopg2
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime, date
from supabase import create_client

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/attendance"
)

# pandas' read_sql_query wants a SQLAlchemy engine (or a sqlite3 connection)
# for full compatibility -- a raw psycopg2 connection works but throws a
# UserWarning. This engine is used only for the two pandas read queries
# below; everything else still uses plain psycopg2.
_engine = create_engine(DATABASE_URL)


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT,
            shift_start TEXT DEFAULT '09:00',
            shift_end TEXT DEFAULT '17:00',
            embedding BYTEA NOT NULL,
            enrolled_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id SERIAL PRIMARY KEY,
            employee_id INTEGER NOT NULL REFERENCES employees(id),
            date TEXT NOT NULL,
            check_in TEXT,
            check_out TEXT,
            status TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS visitors (
            id SERIAL PRIMARY KEY,
            detected_at TEXT NOT NULL,
            date TEXT NOT NULL,
            camera TEXT DEFAULT 'main gate in',
            best_similarity REAL
        )
    """)
    c.execute("ALTER TABLE visitors ADD COLUMN IF NOT EXISTS photo_path TEXT")
    conn.commit()

    # Migration: turn visitors from single-sighting rows into check-in/
    # check-out SESSIONS. A visitor's face embedding is stored only for
    # the duration of their open session (used to recognize them again
    # at check-out), matched the same way an employee is -- just against
    # a separate, temporary pool instead of the permanent employee table.
    extra_visitor_cols = {
        "embedding": "BYTEA",
        "camera_in": "TEXT DEFAULT 'main gate in'",
        "camera_out": "TEXT",
        "check_in": "TEXT",
        "check_out": "TEXT",
    }
    for col, coltype in extra_visitor_cols.items():
        c.execute(f"ALTER TABLE visitors ADD COLUMN IF NOT EXISTS {col} {coltype}")
    conn.commit()
    # Backfill: old rows only had detected_at -- treat that as their check_in
    # so existing data still shows up sensibly in the new session view.
    c.execute("UPDATE visitors SET check_in = detected_at WHERE check_in IS NULL")
    conn.commit()

    # Extended employee profile fields -- placeholders for data that, in
    # production, would sync automatically from an HR system by employee
    # ID. Postgres supports "ADD COLUMN IF NOT EXISTS" directly, so this
    # migration is simpler than the SQLite version's PRAGMA-based check.
    extra_emp_cols = {
        "national_id": "TEXT",
        "job_title": "TEXT",
        "gender": "TEXT",
        "religion": "TEXT",
        "marital_status": "TEXT",
        "birth_date": "TEXT",
        "address": "TEXT",
        "employee_status": "TEXT DEFAULT 'whitelist'",
    }
    for col, coltype in extra_emp_cols.items():
        c.execute(f"ALTER TABLE employees ADD COLUMN IF NOT EXISTS {col} {coltype}")
    conn.commit()

    c.close()
    conn.close()


def add_employee(name, department, embedding, shift_start="09:00", shift_end="17:00",
                  national_id=None, job_title=None, gender=None, religion=None,
                  marital_status=None, birth_date=None, address=None,
                  employee_status="whitelist"):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO employees (name, department, shift_start, shift_end, embedding, enrolled_at, "
        "national_id, job_title, gender, religion, marital_status, birth_date, address, employee_status) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (name, department, shift_start, shift_end,
         psycopg2.Binary(np.asarray(embedding, dtype=np.float32).tobytes()),
         datetime.now().isoformat(),
         national_id, job_title, gender, religion, marital_status, birth_date, address, employee_status)
    )
    conn.commit()
    c.close()
    conn.close()


def update_employee_profile(employee_id, **fields):
    """
    Updates any subset of an employee's profile fields. In production,
    this is the function an HR-system integration would call automatically
    (looked up by employee ID) -- for now it's called manually from the
    dashboard.
    """
    allowed = {"name", "department", "shift_start", "shift_end", "national_id", "job_title",
               "gender", "religion", "marital_status", "birth_date", "address", "employee_status"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    conn = get_conn()
    c = conn.cursor()
    set_clause = ", ".join(f"{k}=%s" for k in updates)
    c.execute(f"UPDATE employees SET {set_clause} WHERE id=%s", (*updates.values(), employee_id))
    conn.commit()
    c.close()
    conn.close()


def get_all_employees():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT id, name, department, shift_start, shift_end, embedding,
                        national_id, job_title, gender, religion, marital_status,
                        birth_date, address, employee_status
                 FROM employees""")
    rows = c.fetchall()
    c.close()
    conn.close()
    employees = []
    for r in rows:
        emb = np.frombuffer(bytes(r[5]), dtype=np.float32)
        employees.append({
            "id": r[0], "name": r[1], "department": r[2],
            "shift_start": r[3], "shift_end": r[4], "embedding": emb,
            "national_id": r[6], "job_title": r[7], "gender": r[8],
            "religion": r[9], "marital_status": r[10], "birth_date": r[11],
            "address": r[12], "employee_status": r[13],
        })
    return employees


def _today_row(employee_id, today):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id, check_in, check_out FROM attendance WHERE employee_id=%s AND date=%s",
        (employee_id, today)
    )
    row = c.fetchone()
    c.close()
    conn.close()
    return row


def get_today_status(employee_id):
    """Public wrapper: returns (check_in_str_or_None, check_out_str_or_None) for today."""
    today = date.today().isoformat()
    row = _today_row(employee_id, today)
    if row is None:
        return None, None
    return row[1], row[2]


def log_check_in(employee_id, shift_start="09:00", grace_minutes=10):
    """Logs a check-in for today if one doesn't already exist. Returns a status string."""
    today = date.today().isoformat()
    now = datetime.now()
    existing = _today_row(employee_id, today)
    if existing and existing[1]:
        return "already_checked_in"

    sh, sm = map(int, shift_start.split(":"))
    shift_dt = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
    late_cutoff = shift_dt.timestamp() + grace_minutes * 60
    status = "on_time" if now.timestamp() <= late_cutoff else "late"
    conn = get_conn()
    c = conn.cursor()
    if existing:
        c.execute("UPDATE attendance SET check_in=%s, status=%s WHERE id=%s",
                   (now.strftime("%H:%M:%S"), status, existing[0]))
    else:
        c.execute(
            "INSERT INTO attendance (employee_id, date, check_in, status) VALUES (%s, %s, %s, %s)",
            (employee_id, today, now.strftime("%H:%M:%S"), status)
        )
    conn.commit()
    c.close()
    conn.close()
    return status


def log_check_out(employee_id):
    today = date.today().isoformat()
    now = datetime.now()
    existing = _today_row(employee_id, today)
    if not existing or not existing[1]:
        return "no_check_in_found"
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE attendance SET check_out=%s WHERE id=%s",
              (now.strftime("%H:%M:%S"), existing[0]))
    conn.commit()
    c.close()
    conn.close()
    return "checked_out"


def get_attendance_df():
    df = pd.read_sql_query("""
        SELECT e.id AS employee_id, e.name, e.department, a.date,
               a.check_in, a.check_out, a.status
        FROM attendance a JOIN employees e ON a.employee_id = e.id
        ORDER BY a.date DESC, a.check_in DESC
    """, _engine)

    if not df.empty:
        def work_hours(row):
            if pd.isna(row["check_in"]) or pd.isna(row["check_out"]):
                return None
            fmt = "%H:%M:%S"
            t_in = datetime.strptime(row["check_in"], fmt)
            t_out = datetime.strptime(row["check_out"], fmt)
            delta = (t_out - t_in).total_seconds() / 3600
            return round(delta, 2) if delta >= 0 else None
        df["work_hours"] = df.apply(work_hours, axis=1)

    return df


def get_today_summary():
    """Returns (total_employees, attended_today, absent_today)."""
    today = date.today().isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM employees")
    total = c.fetchone()[0]
    c.execute(
        "SELECT COUNT(DISTINCT employee_id) FROM attendance WHERE date=%s AND check_in IS NOT NULL",
        (today,)
    )
    attended = c.fetchone()[0]
    c.close()
    conn.close()
    return total, attended, max(total - attended, 0)


def delete_employee(employee_id):
    """
    Deletes an employee AND their attendance history. This is a hard,
    permanent delete -- there's no undo. Attendance rows are removed too
    (rather than left orphaned), since an orphaned row would silently
    disappear from get_attendance_df() anyway (its JOIN would just drop
    it), which is worse than being upfront that deleting an employee
    deletes their history.
    """
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM attendance WHERE employee_id=%s", (employee_id,))
    c.execute("DELETE FROM employees WHERE id=%s", (employee_id,))
    conn.commit()
    c.close()
    conn.close()


def get_open_visitor_sessions():
    """
    Returns currently checked-in visitors whose sessions are still open.

    Each result contains:
      - id: visitor session ID
      - embedding: the stored float32 face embedding
      - check_in: the visitor check-in time

    The kiosk needs check_in to decide whether enough time has passed
    before treating another sighting as a visitor check-out.
    """
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT id, embedding, check_in
        FROM visitors
        WHERE check_in IS NOT NULL
          AND check_out IS NULL
          AND embedding IS NOT NULL
    """)

    rows = c.fetchall()

    c.close()
    conn.close()

    return [
        {
            "id": row[0],
            "embedding": np.frombuffer(bytes(row[1]), dtype=np.float32),
            "check_in": row[2],
        }
        for row in rows
    ]


def log_visitor_check_in(embedding, camera="main gate in", best_similarity=None, photo_path=None):
    now = datetime.now()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO visitors (detected_at, date, camera, camera_in, check_in, best_similarity, embedding, photo_path) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (now.strftime("%H:%M:%S"), date.today().isoformat(), camera, camera,
         now.strftime("%H:%M:%S"), best_similarity,
         psycopg2.Binary(np.asarray(embedding, dtype=np.float32).tobytes()),
         photo_path)
    )
    conn.commit()
    c.close()
    conn.close()


def log_visitor_check_out(session_id, camera="main gate out"):
    """Closes an open visitor session. Returns the duration in minutes."""
    now = datetime.now()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT check_in FROM visitors WHERE id=%s", (session_id,))
    row = c.fetchone()
    if row is None or row[0] is None:
        c.close()
        conn.close()
        return None

    check_in_time = datetime.strptime(row[0], "%H:%M:%S")
    duration_minutes = round((now - datetime.combine(now.date(), check_in_time.time())).total_seconds() / 60, 1)

    c.execute("UPDATE visitors SET check_out=%s, camera_out=%s WHERE id=%s",
              (now.strftime("%H:%M:%S"), camera, session_id))
    conn.commit()
    c.close()
    conn.close()
    return duration_minutes


def get_visitors_df():
    df = pd.read_sql_query(
        "SELECT id, date, check_in, check_out, camera_in, camera_out, best_similarity, photo_path "
        "FROM visitors ORDER BY date DESC, check_in DESC", _engine
    )
    if not df.empty:
        def duration(row):
            if pd.isna(row["check_in"]) or pd.isna(row["check_out"]):
                return None
            fmt = "%H:%M:%S"
            t_in = datetime.strptime(row["check_in"], fmt)
            t_out = datetime.strptime(row["check_out"], fmt)
            delta = (t_out - t_in).total_seconds() / 60
            return round(delta, 1) if delta >= 0 else None
        df["duration_minutes"] = df.apply(duration, axis=1)
    return df


def get_visitor_count_this_month():
    conn = get_conn()
    c = conn.cursor()
    month_prefix = date.today().isoformat()[:7]  # 'YYYY-MM'
    c.execute("SELECT COUNT(*) FROM visitors WHERE date LIKE %s", (f"{month_prefix}%",))
    count = c.fetchone()[0]
    c.close()
    conn.close()
    return count


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
_supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

VISITOR_PHOTOS_BUCKET = "visitor-photos"


def upload_visitor_photo(image_bytes: bytes, session_id_hint: str) -> str | None:
    """Uploads a visitor photo to Supabase Storage, returns the storage path (not a public URL, bucket is private)."""
    if _supabase is None:
        return None
    path = f"{date.today().isoformat()}/{session_id_hint}_{datetime.now().strftime('%H%M%S')}.jpg"
    _supabase.storage.from_(VISITOR_PHOTOS_BUCKET).upload(
        path, image_bytes, {"content-type": "image/jpeg"}
    )
    return path


def get_visitor_photo_path(visitor_id):
    """Looks up the stored Supabase Storage path for a visitor's photo, if one was saved."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT photo_path FROM visitors WHERE id=%s", (visitor_id,))
    row = c.fetchone()
    c.close()
    conn.close()
    return row[0] if row else None


def get_visitor_photo_url(photo_path, expires_in=60):
    """Generates a short-lived signed URL for a private-bucket photo. Returns None if storage isn't configured."""
    if _supabase is None:
        return None
    signed = _supabase.storage.from_(VISITOR_PHOTOS_BUCKET).create_signed_url(photo_path, expires_in)
    return signed.get("signedURL") or signed.get("signedUrl")
