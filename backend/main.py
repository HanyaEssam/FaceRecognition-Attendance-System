"""
main.py — FastAPI backend for the Face Recognition Attendance Dashboard.

Reuses db.py and face_pipeline.py exactly as before (no changes to the
CV/DB logic) -- this file is purely the HTTP API layer that a React
frontend talks to.

Run with:
    uvicorn main:app --reload --port 8000
"""
import base64
import io
import os
import time
import uuid
from datetime import date, datetime
from typing import List, Optional

import cv2
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()
from db import (
    add_employee,
    delete_employee,
    get_all_employees,
    get_attendance_df,
    get_open_visitor_sessions,
    get_today_status,
    get_today_summary,
    get_visitor_count_this_month,
    get_visitors_df,
    init_db,
    log_check_in,
    log_check_out,
    log_visitor_check_in,
    log_visitor_check_out,
    get_visitor_photo_path,
    get_visitor_photo_url,
    upload_visitor_photo,
    update_employee_profile,
)
from face_pipeline import FacePipeline, LivenessChecker, detect_mask

app = FastAPI(title="Attendance API")
router = APIRouter(prefix="/api")

# CORS
#
# Railway environment variable examples:
# FRONTEND_URL=https://your-app.vercel.app
#
# You may also provide several comma-separated URLs:
# FRONTEND_URL=https://app.vercel.app,https://www.example.com
_frontend_urls = os.environ.get("FRONTEND_URL", "")
_allow_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

for origin in _frontend_urls.split(","):
    origin = origin.strip().rstrip("/")
    if origin and origin not in _allow_origins:
        _allow_origins.append(origin)

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
    shift_end: str = "17:00"
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
    shift_end: Optional[str] = None
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
@router.get("/employees")
def list_employees():
    employees = get_all_employees()
    # embeddings are large numpy arrays -- don't send them over the wire
    return [{k: v for k, v in e.items() if k != "embedding"} for e in employees]


@router.post("/employees")
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
        payload.name, payload.department, avg_embedding,
        shift_start=payload.shift_start, shift_end=payload.shift_end,
        national_id=payload.national_id, job_title=payload.job_title, gender=payload.gender,
        religion=payload.religion, marital_status=payload.marital_status,
        birth_date=payload.birth_date, address=payload.address,
    )
    return {"status": "created", "captures_used": len(embeddings)}


@router.put("/employees/{employee_id}")
def edit_employee(employee_id: int, payload: EmployeeProfileUpdate):
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update.")
    update_employee_profile(employee_id, **fields)
    return {"status": "updated"}


@router.delete("/employees/{employee_id}")
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
        _, jpeg_bytes = cv2.imencode(".jpg", frame)
        photo_path = upload_visitor_photo(jpeg_bytes.tobytes(), session_id_hint=uuid.uuid4().hex[:8])
        log_visitor_check_in(embedding, camera=camera, best_similarity=float(score), photo_path=photo_path)
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


@router.post("/checkin")
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
# Kiosk mode — continuous automatic scanning
# ---------------------------------------------------------------------

# Ignore repeated scans of the same recognized person for this many seconds.
KIOSK_COOLDOWN_SECONDS = int(
    os.environ.get("KIOSK_COOLDOWN_SECONDS", "10")
)

# With one camera, a second sighting is considered check-out only after this
# number of minutes. For a real installation, separate IN and OUT cameras are
# safer; the request model below also supports direction="in" or "out".
MIN_MINUTES_BEFORE_CHECKOUT = int(
    os.environ.get("MIN_MINUTES_BEFORE_CHECKOUT", "60")
)

# In-memory duplicate protection. This is suitable for a single Railway
# process. It resets whenever the Railway service restarts.
_last_processed = {}


def _cooldown_key(
    kind: str,
    entity_id: int,
    direction: str,
) -> str:
    """
    Keep separate cooldowns for entrance and exit processing.

    Example:
      emp_3_in
      emp_3_out

    This prevents a recent check-in from blocking a legitimate check-out
    when the operator switches from "main gate in" to "main gate out".
    """
    return f"{kind}_{entity_id}_{direction}"


def _in_cooldown(
    kind: str,
    entity_id: int,
    direction: str,
) -> bool:
    last_time = _last_processed.get(
        _cooldown_key(kind, entity_id, direction)
    )

    if last_time is None:
        return False

    return (
        time.time() - last_time
    ) < KIOSK_COOLDOWN_SECONDS


def _mark_processed(
    kind: str,
    entity_id: int,
    direction: str,
) -> None:
    _last_processed[
        _cooldown_key(kind, entity_id, direction)
    ] = time.time()


def _minutes_since(time_string: Optional[str]) -> float:
    if not time_string:
        return 0.0

    stored_time = datetime.strptime(time_string, "%H:%M:%S")
    now = datetime.now()
    stored_datetime = datetime.combine(now.date(), stored_time.time())
    return max((now - stored_datetime).total_seconds() / 60.0, 0.0)


def _camera_direction(camera: str, requested_direction: str) -> str:
    """
    Resolve whether this camera should act as an IN or OUT camera.

    Priority:
      1. Explicit direction from frontend: "in", "out", or "auto"
      2. Camera name ending in/containing "out"
      3. Otherwise automatic history-based behavior
    """
    direction = (requested_direction or "auto").strip().lower()

    if direction in {"in", "out"}:
        return direction

    camera_name = (camera or "").strip().lower()
    if "out" in camera_name:
        return "out"
    if "in" in camera_name:
        return "in"

    return "auto"


def _kiosk_process_employee(
    frame,
    face_row,
    box,
    match,
    score,
    direction,
):
    employee_id = match["id"]
    employee_name = match["name"]

    if _in_cooldown("emp", employee_id, direction):
        return {
            "result": "cooldown",
            "box": box,
            "employee_name": employee_name,
        }

    check_in_time, check_out_time = get_today_status(employee_id)

    # Dedicated entrance camera
    if direction == "in":
        if check_in_time is not None:
            return {
                "result": "too_soon",
                "box": box,
                "employee_name": employee_name,
            }

        wearing_mask, mask_score = detect_mask(frame, face_row)
        status = log_check_in(
            employee_id,
            match["shift_start"],
            wore_mask=wearing_mask,
        )
        _mark_processed("emp", employee_id, direction)

        return {
            "result": "check_in",
            "box": box,
            "status": status,
            "employee_name": employee_name,
            "similarity": float(score),
            "wore_mask": bool(wearing_mask),
            "mask_score": float(mask_score),
        }

    # Dedicated exit camera
    if direction == "out":
        if check_in_time is None:
            return {
                "result": "no_check_in",
                "box": box,
                "employee_name": employee_name,
                "message": "Employee has not checked in today.",
            }

        if check_out_time is not None:
            return {
                "result": "already_done",
                "box": box,
                "employee_name": employee_name,
            }

        status = log_check_out(employee_id)
        _mark_processed("emp", employee_id, direction)

        return {
            "result": "check_out",
            "box": box,
            "status": status,
            "employee_name": employee_name,
            "similarity": float(score),
        }

    # One-camera automatic behavior
    if check_in_time is None:
        wearing_mask, mask_score = detect_mask(frame, face_row)
        status = log_check_in(
            employee_id,
            match["shift_start"],
            wore_mask=wearing_mask,
        )
        _mark_processed("emp", employee_id, direction)

        return {
            "result": "check_in",
            "box": box,
            "status": status,
            "employee_name": employee_name,
            "similarity": float(score),
            "wore_mask": bool(wearing_mask),
            "mask_score": float(mask_score),
        }

    if check_out_time is not None:
        return {
            "result": "already_done",
            "box": box,
            "employee_name": employee_name,
        }

    elapsed_minutes = _minutes_since(check_in_time)
    if elapsed_minutes < MIN_MINUTES_BEFORE_CHECKOUT:
        return {
            "result": "too_soon",
            "box": box,
            "employee_name": employee_name,
            "minutes_since_check_in": round(elapsed_minutes, 1),
        }

    status = log_check_out(employee_id)
    _mark_processed("emp", employee_id, direction)

    return {
        "result": "check_out",
        "box": box,
        "status": status,
        "employee_name": employee_name,
        "similarity": float(score),
    }


def _kiosk_process_visitor(
    embedding,
    box,
    camera,
    direction,
    employee_similarity,
):
    open_sessions = get_open_visitor_sessions()
    visitor_match, visitor_score = (
        pipeline.match(embedding, open_sessions)
        if open_sessions
        else (None, 0.0)
    )

    # Entrance camera: create a session only for a new visitor.
    if direction == "in":
        if visitor_match is not None:
            return {
                "result": "visitor_too_soon",
                "box": box,
                "message": "Visitor session is already active.",
            }

        log_visitor_check_in(
            embedding,
            camera=camera,
            best_similarity=float(employee_similarity),
        )
        return {
            "result": "visitor_check_in",
            "box": box,
            "similarity_to_employees": float(employee_similarity),
        }

    # Exit camera: only close an existing visitor session.
    if direction == "out":
        if visitor_match is None:
            return {
                "result": "visitor_no_session",
                "box": box,
                "message": "No matching open visitor session was found.",
            }

        visitor_id = visitor_match["id"]
        if _in_cooldown("visitor", visitor_id, direction):
            return {"result": "cooldown", "box": box}

        duration = log_visitor_check_out(visitor_id, camera=camera)
        _mark_processed("visitor", visitor_id, direction)

        return {
            "result": "visitor_check_out",
            "box": box,
            "duration_minutes": duration,
            "similarity": float(visitor_score),
        }

    # One-camera automatic visitor behavior.
    if visitor_match is None:
        log_visitor_check_in(
            embedding,
            camera=camera,
            best_similarity=float(employee_similarity),
        )
        return {
            "result": "visitor_check_in",
            "box": box,
            "similarity_to_employees": float(employee_similarity),
        }

    visitor_id = visitor_match["id"]
    if _in_cooldown("visitor", visitor_id, direction):
        return {"result": "cooldown", "box": box}

    elapsed_minutes = _minutes_since(visitor_match.get("check_in"))
    if elapsed_minutes < MIN_MINUTES_BEFORE_CHECKOUT:
        return {
            "result": "visitor_too_soon",
            "box": box,
            "minutes_since_check_in": round(elapsed_minutes, 1),
        }

    duration = log_visitor_check_out(visitor_id, camera=camera)
    _mark_processed("visitor", visitor_id, direction)

    return {
        "result": "visitor_check_out",
        "box": box,
        "duration_minutes": duration,
        "similarity": float(visitor_score),
    }


def _kiosk_process_one_face(
    frame,
    face_row,
    camera: str,
    requested_direction: str,
):
    box = face_row[:4].astype(int).tolist()

    is_live, live_score, live_details = liveness.is_live(
        frame,
        face_row,
        debug=False,
    )

    if not is_live:
        return {
            "result": "spoof_suspected",
            "box": box,
            "message": f"Liveness check failed (score {live_score:.2f}).",
            "liveness_score": float(live_score),
            "liveness_details": live_details,
        }

    embedding = pipeline.get_embedding(frame, face_row)
    employees = get_all_employees()
    match, score = (
        pipeline.match(embedding, employees)
        if employees
        else (None, 0.0)
    )

    direction = _camera_direction(camera, requested_direction)

    if match is not None:
        return _kiosk_process_employee(
            frame,
            face_row,
            box,
            match,
            score,
            direction,
        )

    return _kiosk_process_visitor(
        embedding,
        box,
        camera,
        direction,
        score,
    )
class KioskScanRequest(BaseModel):
    image: str
    camera: str = "main gate in"
    direction: str = "auto"


@router.post("/kiosk/scan")
def kiosk_scan(payload: KioskScanRequest):
    requested_direction = payload.direction.strip().lower()

    if requested_direction not in {"in", "out", "auto"}:
        raise HTTPException(
            status_code=400,
            detail='direction must be "in", "out", or "auto".',
        )

    if not MODELS_LOADED:
        raise HTTPException(
            status_code=503,
            detail="Face models are not loaded on the server.",
        )

    frame = decode_image(payload.image)
    faces = pipeline.detect_faces(frame)

    if faces is None or len(faces) == 0:
        return {
            "faces_detected": 0,
            "results": [],
        }

    results = []

    for face_row in faces:
        try:
            results.append(
                _kiosk_process_one_face(
                    frame,
                    face_row,
                    payload.camera,
                    requested_direction,
                )
            )
        except Exception as error:
            print("Kiosk face processing error:", repr(error))
            results.append({
                "result": "processing_error",
                "message": str(error),
            })

    return {
        "faces_detected": int(len(faces)),
        "results": results,
    }

@router.get("/attendance")
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


@router.get("/attendance/export/csv")
def export_csv():
    df = get_attendance_df()
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance_log.csv"},
    )


@router.get("/attendance/export/xlsx")
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


@router.get("/visitors")
def visitors():
    df = get_visitors_df()
    df = df.astype(object).where(df.notnull(), None)
    return {
        "records": df.to_dict(orient="records"),
        "total_all_time": len(df),
        "count_this_month": get_visitor_count_this_month(),
    }


@router.get("/visitors/{visitor_id}/photo-url")
def visitor_photo_url(visitor_id: int):
    photo_path = get_visitor_photo_path(visitor_id)
    if not photo_path:
        raise HTTPException(status_code=404, detail="No photo on file for this visitor.")
    url = get_visitor_photo_url(photo_path)
    if not url:
        raise HTTPException(status_code=503, detail="Could not generate photo URL (storage not configured).")
    return {"url": url}


# ---------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------
@router.get("/dashboard/stats")
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


@router.get("/health")
def health():
    return {
        "status": "ok",
        "models_loaded": MODELS_LOADED,
        "kiosk_endpoint": "/api/kiosk/scan",
        "supported_directions": ["in", "out", "auto"],
    }

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Face Recognition Attendance API is running",
        "docs": "/docs",
        "health": "/api/health",
    }


app.include_router(router)
