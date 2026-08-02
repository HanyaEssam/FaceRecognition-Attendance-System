"""
mock_employees.py — inserts a handful of fake employees directly into the
database, with random (not real-face) embeddings, so you have data to
work with without needing a webcam for each person.

These employees will show up in the dashboard, Employees page, and can
have attendance history backfilled by seed_mock_data.py -- but they will
NEVER match a real face during Check In/Out (their embeddings are random
noise, not from an actual photo), so they won't cause false positives on
your live camera.

Run this BEFORE seed_mock_data.py:
    python mock_employees.py
    python seed_mock_data.py
"""
import random
import numpy as np
from db import init_db, add_employee, get_all_employees

# SFace (face_recognition_sface_2021dec.onnx) outputs a 128-dim embedding.
# Matches that shape so comparisons don't blow up during Check In/Out.
EMBED_DIM = 128

MOCK_EMPLOYEES = [
    {"name": "Sara Ahmed",       "department": "Engineering", "shift_start": "09:00", "shift_end": "17:00"},
    {"name": "Omar Khaled",      "department": "Engineering", "shift_start": "09:00"},
    {"name": "Nourhan Fathy",    "department": "HR",          "shift_start": "08:30"},
    {"name": "Mostafa Hassan",   "department": "Operations",  "shift_start": "07:00"},
    {"name": "Yasmin Adel",      "department": "Finance",     "shift_start": "09:30"},
    {"name": "Karim Tarek",      "department": "Operations",  "shift_start": "07:00"},
    {"name": "Mariam Sami",      "department": "HR",          "shift_start": "08:30"},
    {"name": "Ahmed Nabil",      "department": "Engineering", "shift_start": "09:00"},
]


def random_embedding():
    vec = np.random.randn(EMBED_DIM).astype(np.float32)
    return vec / np.linalg.norm(vec)


def main():
    init_db()
    existing_names = {e["name"] for e in get_all_employees()}

    added = 0
    for emp in MOCK_EMPLOYEES:
        if emp["name"] in existing_names:
            print(f"Skipping '{emp['name']}' -- already exists.")
            continue
        add_employee(
            emp["name"],
            emp["department"],
            random_embedding(),
            shift_start=emp["shift_start"],
        )
        added += 1
        print(f"Added '{emp['name']}' ({emp['department']}).")

    print(f"\nDone. Added {added} mock employee(s).")
    print("Now run: python seed_mock_data.py")


if __name__ == "__main__":
    main()