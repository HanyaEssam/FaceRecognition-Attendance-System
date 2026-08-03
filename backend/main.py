"""
main.py — FastAPI backend for the Face Recognition Attendance Dashboard.

Reuses db.py and face_pipeline.py exactly as before (no changes to the
CV/DB logic) -- this file is purely the HTTP API layer that a React
frontend talks to.

Run with:
    uvicorn main:app --reload --port 8000
"""
import io
import os
import base64
from datetime import date
from typing import Optional, List

import cv2
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from db import (init_db, get_all_employees, log_check_in, log_check_out,
                 get_attendance_df, add_employee, delete_employee,
                 update_employee_profile, get_visitors_df,
                 get_visitor_count_this_month, get_today_summary,
                 get_open_visitor_sessions, log_visitor_check_in, log_visitor_check_out)
from face_pipeline import FacePipeline, LivenessChecker, detect_mask

app = FastAPI(title="Attendance API")

# Add your deployed frontend URL here via the FRONTEND_URL env var
# (e.g. FRONTEND_URL=https://your-app.vercel.app), or it falls back to
# just the local Vite dev server for local development.
_extra_origin = os.environ.get("FRONTEND_URL")
_allow_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if _extra_origin:
    _allow_origins.append(_extra_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

# Models are loaded once at startup. If the .onnx files aren't present
# yet (e.g. running the API before downloading models), this will raise
# -- see README for exactly which files go where.
try:
    pipeline = FacePipeline()
    liveness = LivenessChecker()
    MODELS_LOADED = True
except Exception as e:
    print(f"WARNING: could not load face models: {e}")
    print("The API will still start, but /checkin will return an error until models are in place.")
    pipeline = None
    liveness = None
    MODELS_LOADED = False


def decode_image(b64_string: str) -> np.ndarray:
    """Decodes a base64 data-URL (e.g. from a <canvas>.toDataURL() capture) into a BGR frame."""
    if "," in b64_string:
        b64_string = b64_string.split(",", 1)[1]
    img_bytes = base64.b64decode(b64_string)
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode image data.")
    return frame


# ---------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------
class CheckInRequest(BaseModel):
    image: str  # base64 data URL
    action: str  # "check_in" or "check_out"
    camera: str = "main gate in"


class EmployeeCreate(BaseModel):
    name: str
    department: str
    shift_start: str = "09:00"
    images: List[str]  # list of base64 data URLs, averaged into one embedding
    national_id: Optional[str] = None
    job_title: Optional[str] = None
    gender: Optional[str] = None
    religion: Optional[str] = None
    marital_status: Optional[str] = None
    birth_date: Optional[str] = None
    address: Optional[str] = None


class EmployeeProfileUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    shift_start: Optional[str] = None
    national_id: Optional[str] = None
    job_title: Optional[str] = None
    gender: Optional[str] = None
    religion: Optional[str] = None
    marital_status: Optional[str] = None
    birth_date: Optional[str] = None
    address: Optional[str] = None
    employee_status: Optional[str] = None


# ---------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------
@app.get("/api/employees")
def list_employees():
    employees = get_all_employees()
    # embeddings are large numpy arrays -- don't send them over the wire
    return [{k: v for k, v in e.items() if k != "embedding"} for e in employees]


@app.post("/api/employees")
def create_employee(payload: EmployeeCreate):
    if not MODELS_LOADED:
        raise HTTPException(status_code=503, detail="Face models not loaded on the server.")
    if not payload.images:
        raise HTTPException(status_code=400, detail="At least one image is required.")

    embeddings = []
    for img_b64 in payload.images:
        frame = decode_image(img_b64)
        faces = pipeline.detect_faces(frame)
        if faces is None or len(faces) == 0:
            continue
        embeddings.append(pipeline.get_embedding(frame, faces[0]))

    if not embeddings:
        raise HTTPException(status_code=400, detail="No face detected in any of the submitted images.")

    avg_embedding = np.mean(embeddings, axis=0)
    add_employee(
        payload.name, payload.department, avg_embedding, shift_start=payload.shift_start,
        national_id=payload.national_id, job_title=payload.job_title, gender=payload.gender,
        religion=payload.religion, marital_status=payload.marital_status,
        birth_date=payload.birth_date, address=payload.address,
    )
    return {"status": "created", "captures_used": len(embeddings)}


@app.put("/api/employees/{employee_id}")
def edit_employee(employee_id: int, payload: EmployeeProfileUpdate):
    fields = {k: v for k, v in payload.dict().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update.")
    update_employee_profile(employee_id, **fields)
    return {"status": "updated"}


@app.delete("/api/employees/{employee_id}")
def remove_employee(employee_id: int):
    delete_employee(employee_id)
    return {"status": "deleted"}


# ---------------------------------------------------------------------
# Check In / Out
# ---------------------------------------------------------------------
def _process_one_face(frame, face_row, action, camera):
    """Runs the full liveness -> match -> log pipeline for ONE detected
    face and returns a result dict. Used to process every face found in
    a frame, so a single photo with multiple people checks everyone in."""
    box = face_row[:4].astype(int).tolist()
    is_live, live_score, live_details = liveness.is_live(frame, face_row, debug=False)

    if not is_live:
        return {
            "result": "spoof_suspected", "box": box,
            "message": f"Liveness check failed (score {live_score:.2f}). This looks like a photo or screen.",
            "liveness_score": live_score, "liveness_details": live_details,
        }

    embedding = pipeline.get_embedding(frame, face_row)
    employees = get_all_employees()
    match, score = pipeline.match(embedding, employees) if employees else (None, 0.0)

    if match is not None:
        wearing_mask, mask_score = detect_mask(frame, face_row)
        if action == "check_in":
            status = log_check_in(match["id"], match["shift_start"], wore_mask=wearing_mask)
            return {
                "result": "check_in", "box": box, "status": status, "employee_name": match["name"],
                "similarity": float(score), "liveness_score": live_score, "wore_mask": wearing_mask,
            }
        else:
            status = log_check_out(match["id"])
            return {
                "result": "check_out", "box": box, "status": status, "employee_name": match["name"],
                "similarity": float(score),
            }

    # --- Not a recognized employee: handle as a VISITOR SESSION ---
    open_sessions = get_open_visitor_sessions()
    visitor_match, visitor_score = pipeline.match(embedding, open_sessions) if open_sessions else (None, 0.0)

    if action == "check_in":
        if visitor_match is not None:
            return {"result": "visitor_already_checked_in", "box": box,
                    "message": "This visitor is already checked in (no new session created)."}
        log_visitor_check_in(embedding, camera=camera, best_similarity=float(score))
        return {"result": "visitor_check_in", "box": box, "message": "Visitor checked in.",
                "similarity_to_employees": float(score)}
    else:
        if visitor_match is None:
            return {"result": "visitor_no_session", "box": box,
                    "message": "No matching visitor check-in found to check out."}
        duration = log_visitor_check_out(visitor_match["id"], camera=camera)
        return {"result": "visitor_check_out", "box": box,
                "message": f"Visitor checked out after {duration} minutes.",
                "duration_minutes": duration}


@app.post("/api/checkin")
def checkin(payload: CheckInRequest):
    if not MODELS_LOADED:
        raise HTTPException(status_code=503, detail="Face models not loaded on the server.")

    frame = decode_image(payload.image)
    faces = pipeline.detect_faces(frame)

    if faces is None or len(faces) == 0:
        return {"faces_detected": 0, "results": [
            {"result": "no_face", "message": "No face detected. Try again with better lighting."}
        ]}

    results = [_process_one_face(frame, face_row, payload.action, payload.camera) for face_row in faces]
    return {"faces_detected": len(faces), "results": results}


# ---------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------
@app.get("/api/attendance")
def attendance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
):
    df = get_attendance_df()
    if df.empty:
        return []

    if start_date:
        df = df[df["date"] >= start_date]
    if end_date:
        df = df[df["date"] <= end_date]
    if department:
        df = df[df["department"] == department]
    if status:
        df = df[df["status"] == status]
    if search:
        df = df[df["name"].str.contains(search, case=False, na=False)]

    df = df.astype(object).where(df.notnull(), None)  # NaN -> null for clean JSON
    return df.to_dict(orient="records")


@app.get("/api/attendance/export/csv")
def export_csv():
    df = get_attendance_df()
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance_log.csv"},
    )


@app.get("/api/attendance/export/xlsx")
def export_xlsx():
    df = get_attendance_df()
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance")
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=attendance_log.xlsx"},
    )


# ---------------------------------------------------------------------
# Visitors
# ---------------------------------------------------------------------
@app.get("/api/visitors")
def visitors():
    df = get_visitors_df()
    df = df.astype(object).where(df.notnull(), None)
    return {
        "records": df.to_dict(orient="records"),
        "total_all_time": len(df),
        "count_this_month": get_visitor_count_this_month(),
    }


# ---------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------
@app.get("/api/dashboard/stats")
def dashboard_stats():
    df = get_attendance_df()
    total_employees, attended_today, absent_today = get_today_summary()
    visitors_df = get_visitors_df()

    stats = {
        "total_employees": total_employees,
        "attended_today": attended_today,
        "absent_today": absent_today,
        "visitors_this_month": get_visitor_count_this_month(),
        "total_visitors_all_time": len(visitors_df),
        "on_time_pct": 0,
        "late_pct": 0,
        "top_attendees": [],
        "top_by_hours": [],
        "by_department": [],
    }

    if not df.empty:
        total = len(df)
        stats["on_time_pct"] = round((df["status"] == "on_time").sum() / total * 100)
        stats["late_pct"] = round((df["status"] == "late").sum() / total * 100)

        top_attendees = df.groupby("name").size().sort_values(ascending=False).head(10)
        stats["top_attendees"] = [{"name": k, "count": int(v)} for k, v in top_attendees.items()]

        hours_df = df.dropna(subset=["work_hours"])
        if not hours_df.empty:
            top_hours = hours_df.groupby("name")["work_hours"].sum().sort_values(ascending=False).head(10)
            stats["top_by_hours"] = [{"name": k, "hours": round(float(v), 2)} for k, v in top_hours.items()]

        dept_counts = df.groupby("department").size().sort_values(ascending=False)
        stats["by_department"] = [{"department": k, "count": int(v)} for k, v in dept_counts.items()]

    return stats


@app.get("/api/health")
def health():
    return {"status": "ok", "models_loaded": MODELS_LOADED}