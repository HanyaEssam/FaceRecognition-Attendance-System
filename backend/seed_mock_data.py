"""
seed_mock_data.py — generates a few weeks of *simulated* historical
attendance for already-enrolled employees, so the dashboard has enough
data to look meaningful in a demo (rather than just today's live clicks).

Run this AFTER enrolling employees with enroll.py:
    python seed_mock_data.py
"""
import random
from datetime import date, timedelta, datetime
from db import init_db, get_all_employees, get_conn

DAYS_OF_HISTORY = 21          # 3 weeks
LATE_PROBABILITY = 0.25       # 25% chance of being late on a given day
ABSENCE_PROBABILITY = 0.05    # 5% chance of no-show on a given day


def business_days(n_days):
    days = []
    d = date.today() - timedelta(days=n_days)
    while d < date.today():
        if d.weekday() < 5:  # skip Sat/Sun (adjust if your workweek differs)
            days.append(d)
        d += timedelta(days=1)
    return days


def random_time_near(hh, mm, spread_minutes, late=False):
    base = hh * 60 + mm
    if late:
        offset = random.randint(11, 60)   # 11-60 min late
    else:
        offset = random.randint(-15, 9)   # up to 15 min early, up to 9 min "on time" grace
    total = base + offset
    total = max(total, 0)
    return f"{total // 60:02d}:{total % 60:02d}:{random.randint(0,59):02d}"


def main():
    init_db()
    employees = get_all_employees()
    if not employees:
        print("No employees enrolled yet. Run enroll.py first.")
        return

    conn = get_conn()
    c = conn.cursor()
    inserted = 0

    for emp in employees:
        sh, sm = map(int, emp["shift_start"].split(":"))
        for d in business_days(DAYS_OF_HISTORY):
            if random.random() < ABSENCE_PROBABILITY:
                continue  # absent that day

            is_late = random.random() < LATE_PROBABILITY
            check_in = random_time_near(sh, sm, 15, late=is_late)
            status = "late" if is_late else "on_time"

            # check-out ~8-9 hours after check-in
            in_minutes = int(check_in[:2]) * 60 + int(check_in[3:5])
            out_minutes = in_minutes + random.randint(480, 540)
            check_out = f"{out_minutes // 60:02d}:{out_minutes % 60:02d}:{random.randint(0,59):02d}"

            c.execute(
                "INSERT INTO attendance (employee_id, date, check_in, check_out, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (emp["id"], d.isoformat(), check_in, check_out, status)
            )
            inserted += 1

    conn.commit()
    conn.close()
    print(f"Seeded {inserted} attendance records across {len(employees)} employees "
          f"over {DAYS_OF_HISTORY} days.")


if __name__ == "__main__":
    main()
