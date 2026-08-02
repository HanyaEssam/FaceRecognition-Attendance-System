"""
db.py — SQLite storage for enrolled employees and attendance records.

Embeddings are stored as raw float32 bytes (BLOB) and reloaded as numpy
arrays. This is fine at POC scale (tens of employees); if this ever grows
to hundreds+, swap this for a proper vector store (e.g. FAISS or a
Postgres + pgvector table).
"""
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, date

DB_PATH = "attendance.db"


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department TEXT,
            shift_start TEXT DEFAULT '09:00',
            embedding BLOB NOT NULL,
            enrolled_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            check_in TEXT,
            check_out TEXT,
            status TEXT,
            FOREIGN KEY(employee_id) REFERENCES employees(id)
        )
    """)
    conn.commit()

    # Migration: add wore_mask column if it doesn't exist yet (safe for
    # both brand-new databases and existing attendance.db files).
    c.execute("PRAGMA table_info(attendance)")
    existing_cols = [row[1] for row in c.fetchall()]
    if "wore_mask" not in existing_cols:
        c.execute("ALTER TABLE attendance ADD COLUMN wore_mask INTEGER DEFAULT 0")
        conn.commit()

    # Migration: extended employee profile fields. These are placeholders
    # for data that, in production, would sync automatically from an HR
    # system by employee ID -- for now they're just editable here.
    c.execute("PRAGMA table_info(employees)")
    emp_cols = [row[1] for row in c.fetchall()]
    extra_emp_cols = {
        "national_id": "TEXT",
        "job_title": "TEXT",
        "gender": "TEXT",
        "religion": "TEXT",
        "marital_status": "TEXT",
        "birth_date": "TEXT",
        "address": "TEXT",
        "employee_status": "TEXT DEFAULT 'whitelist'",
        "shift_end": "TEXT DEFAULT '17:00'", 
    }
    for col, coltype in extra_emp_cols.items():
        if col not in emp_cols:
            c.execute(f"ALTER TABLE employees ADD COLUMN {col} {coltype}")
    conn.commit()

    # New table: visitors (guests) -- anyone detected who does NOT match
    # an enrolled employee gets logged here instead of blocked/errored.
    c.execute("""
        CREATE TABLE IF NOT EXISTS visitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detected_at TEXT NOT NULL,
            date TEXT NOT NULL,
            camera TEXT DEFAULT 'main gate in',
            best_similarity REAL
        )
    """)
    conn.commit()

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
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, department, shift_start, shift_end,
         np.asarray(embedding, dtype=np.float32).tobytes(),
         datetime.now().isoformat(),
         national_id, job_title, gender, religion, marital_status, birth_date, address, employee_status)
    )
    conn.commit()
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
    set_clause = ", ".join(f"{k}=?" for k in updates)
    c.execute(f"UPDATE employees SET {set_clause} WHERE id=?", (*updates.values(), employee_id))
    conn.commit()
    conn.close()


def get_all_employees():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT id, name, department, shift_start, shift_end, embedding,
                        national_id, job_title, gender, religion, marital_status,
                        birth_date, address, employee_status
                 FROM employees""")
    rows = c.fetchall()
    conn.close()
    employees = []
    for r in rows:
        emb = np.frombuffer(r[5], dtype=np.float32)
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
        "SELECT id, check_in, check_out FROM attendance WHERE employee_id=? AND date=?",
        (employee_id, today)
    )
    row = c.fetchone()
    conn.close()
    return row


def get_today_status(employee_id):
    """Public wrapper: returns (check_in_str_or_None, check_out_str_or_None) for today."""
    today = date.today().isoformat()
    row = _today_row(employee_id, today)
    if row is None:
        return None, None
    return row[1], row[2]


def log_check_in(employee_id, shift_start="09:00", grace_minutes=10, wore_mask=False):
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
    mask_val = 1 if wore_mask else 0

    conn = get_conn()
    c = conn.cursor()
    if existing:
        c.execute("UPDATE attendance SET check_in=?, status=?, wore_mask=? WHERE id=?",
                   (now.strftime("%H:%M:%S"), status, mask_val, existing[0]))
    else:
        c.execute(
            "INSERT INTO attendance (employee_id, date, check_in, status, wore_mask) VALUES (?, ?, ?, ?, ?)",
            (employee_id, today, now.strftime("%H:%M:%S"), status, mask_val)
        )
    conn.commit()
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
    c.execute("UPDATE attendance SET check_out=? WHERE id=?",
              (now.strftime("%H:%M:%S"), existing[0]))
    conn.commit()
    conn.close()
    return "checked_out"


def get_attendance_df():
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT e.id AS employee_id, e.name, e.department, a.date,
               a.check_in, a.check_out, a.status,
               CASE WHEN a.wore_mask=1 THEN 'Yes' ELSE 'No' END AS wore_mask
        FROM attendance a JOIN employees e ON a.employee_id = e.id
        ORDER BY a.date DESC, a.check_in DESC
    """, conn)
    conn.close()

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
        "SELECT COUNT(DISTINCT employee_id) FROM attendance WHERE date=? AND check_in IS NOT NULL",
        (today,)
    )
    attended = c.fetchone()[0]
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
    c.execute("DELETE FROM attendance WHERE employee_id=?", (employee_id,))
    c.execute("DELETE FROM employees WHERE id=?", (employee_id,))
    conn.commit()
    conn.close()


def log_visitor(camera="main gate in", best_similarity=None):
    """Logs a sighting of a face that did NOT match any enrolled employee."""
    now = datetime.now()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO visitors (detected_at, date, camera, best_similarity) VALUES (?, ?, ?, ?)",
        (now.strftime("%H:%M:%S"), date.today().isoformat(), camera, best_similarity)
    )
    conn.commit()
    conn.close()


def get_visitors_df():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT date, detected_at AS time, camera, best_similarity FROM visitors "
        "ORDER BY date DESC, detected_at DESC", conn
    )
    conn.close()
    return df


def get_visitor_count_this_month():
    conn = get_conn()
    c = conn.cursor()
    month_prefix = date.today().isoformat()[:7]  # 'YYYY-MM'
    c.execute("SELECT COUNT(*) FROM visitors WHERE date LIKE ?", (f"{month_prefix}%",))
    count = c.fetchone()[0]
    conn.close()
    return count
