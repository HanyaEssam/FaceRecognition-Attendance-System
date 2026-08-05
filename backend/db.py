"""
db.py — PostgreSQL storage for enrolled employees and attendance records.

Attendance is now SESSION-based: each check-in creates a NEW row rather
than reusing/overwriting a single row per employee per day. This allows
an employee to check in/out multiple times in a day (e.g. lunch break),
with every attempt preserved as its own row instead of being overwritten.
An "open" session is a row with check_in set and check_out still NULL.
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
    c.execute("UPDATE visitors SET check_in = detected_at WHERE check_in IS NULL")
    conn.commit()

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


def get_open_session(employee_id):
    """
    Returns (session_id, check_in_time) for the most recent OPEN session
    today (check_in set, check_out still NULL) -- or (None, None) if the
    employee has no open session right now. This replaces the old
    "one row per employee per day" model: an employee can have several
    CLOSED sessions today plus at most one OPEN one.
    """
    today = date.today().isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id, check_in FROM attendance "
        "WHERE employee_id=%s AND date=%s AND check_out IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (employee_id, today)
    )
    row = c.fetchone()
    c.close()
    conn.close()
    if row is None:
        return None, None
    return row[0], row[1]


def get_today_status(employee_id):
    """
    Public wrapper, kept for compatibility with existing kiosk logic.
    Returns (check_in_str_or_None, check_out_str_or_None) describing the
    CURRENT open session only. check_out is always None here by
    definition (a session with check_out set is closed, not open) --
    kiosk logic that checks "if check_out_time is not None" simply never
    triggers anymore, which is intentional now that multiple sessions
    per day are allowed.
    """
    _, check_in_time = get_open_session(employee_id)
    return check_in_time, None


def log_check_in(employee_id, shift_start="09:00", grace_minutes=10):
    """
    Starts a NEW session for today, as long as no session is currently
    open. Only the FIRST session of the day gets an on_time/late status
    computed against the shift start -- any later session that day
    (e.g. returning from lunch) gets status "returned" instead, since
    comparing a midday re-entry against the morning shift start doesn't
    mean anything.
    """
    today = date.today().isoformat()
    now = datetime.now()

    open_session_id, _ = get_open_session(employee_id)
    if open_session_id is not None:
        return "already_checked_in"

    conn = get_conn()
    c = conn.cursor()

    c.execute(
        "SELECT COUNT(*) FROM attendance WHERE employee_id=%s AND date=%s",
        (employee_id, today)
    )
    sessions_today = c.fetchone()[0]

    if sessions_today == 0:
        sh, sm = map(int, shift_start.split(":"))
        shift_dt = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        late_cutoff = shift_dt.timestamp() + grace_minutes * 60
        status = "on_time" if now.timestamp() <= late_cutoff else "late"
    else:
        status = "returned"

    c.execute(
        "INSERT INTO attendance (employee_id, date, check_in, status) VALUES (%s, %s, %s, %s)",
        (employee_id, today, now.strftime("%H:%M:%S"), status)
    )
    conn.commit()
    c.close()
    conn.close()
    return status


def log_check_out(employee_id):
    """Closes the current open session, if one exists."""
    now = datetime.now()
    open_session_id, _ = get_open_session(employee_id)
    if open_session_id is None:
        return "no_check_in_found"
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE attendance SET check_out=%s WHERE id=%s",
              (now.strftime("%H:%M:%S"), open_session_id))
    conn.commit()
    c.close()
    conn.close()
    return "checked_out"


def get_attendance_df():
    """
    Returns every attendance SESSION as its own row (no longer collapsed
    to one row per employee per day). With the new log_check_in behavior,
    a day with multiple check-in/out cycles now naturally produces
    multiple rows here.
    """
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


def get_daily_hours_summary(start_date=None, end_date=None):
    """
    Groups attendance sessions by employee + date and sums work_hours
    across all that day's sessions -- feeds the new summary table above
    the raw logs table. Days with no completed (check_in + check_out)
    session show None rather than 0, via min_count=1.
    """
    df = get_attendance_df()
    if df.empty:
        return df
    if start_date:
        df = df[df["date"] >= start_date]
    if end_date:
        df = df[df["date"] <= end_date]
    if df.empty:
        return df

    grouped = df.groupby(
        ["employee_id", "name", "department", "date"], as_index=False
    )["work_hours"].sum(min_count=1)
    grouped = grouped.rename(columns={"work_hours": "total_work_hours"})
    grouped = grouped.sort_values(["date", "name"], ascending=[False, True])
    return grouped


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
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM attendance WHERE employee_id=%s", (employee_id,))
    c.execute("DELETE FROM employees WHERE id=%s", (employee_id,))
    conn.commit()
    c.close()
    conn.close()


def get_open_visitor_sessions():
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
        {"id": row[0], "embedding": np.frombuffer(bytes(row[1]), dtype=np.float32), "check_in": row[2]}
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
    month_prefix = date.today().isoformat()[:7]
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
    if _supabase is None:
        return None
    path = f"{date.today().isoformat()}/{session_id_hint}_{datetime.now().strftime('%H%M%S')}.jpg"
    _supabase.storage.from_(VISITOR_PHOTOS_BUCKET).upload(
        path, image_bytes, {"content-type": "image/jpeg"}
    )
    return path


def get_visitor_photo_path(visitor_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT photo_path FROM visitors WHERE id=%s", (visitor_id,))
    row = c.fetchone()
    c.close()
    conn.close()
    return row[0] if row else None


def get_visitor_photo_url(photo_path, expires_in=60):
    if _supabase is None:
        return None
    signed = _supabase.storage.from_(VISITOR_PHOTOS_BUCKET).create_signed_url(photo_path, expires_in)
    return signed.get("signedURL") or signed.get("signedUrl")