from __future__ import annotations

from datetime import datetime
from io import BytesIO
from uuid import UUID

import face_recognition
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import require_faculty
from app.models.user import User
from app.services.attendance_service import AttendanceError, mark_attendance

router = APIRouter(prefix="/attendance", tags=["Attendance"])


class AttendanceResponse(BaseModel):
    id: UUID
    session_id: UUID
    student_id: UUID
    confidence_score: float
    marked_at: datetime


def _extract_single_face_encoding(image_bytes: bytes) -> list[float]:
    image = face_recognition.load_image_file(BytesIO(image_bytes))
    encodings = face_recognition.face_encodings(image)

    if len(encodings) == 0:
        raise AttendanceError("No face detected in the uploaded image.")
    if len(encodings) > 1:
        raise AttendanceError("Multiple faces detected. Please upload an image with exactly one face.")

    return np.asarray(encodings[0], dtype=np.float64).tolist()


@router.post(
    "/mark/{session_id}",
    response_model=AttendanceResponse,
    status_code=status.HTTP_200_OK,
)
async def mark_attendance_endpoint(
    session_id: UUID,
    image: UploadFile = File(...),
    _: User = Depends(require_faculty),
    db: AsyncSession = Depends(get_db_session),
) -> AttendanceResponse:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Please upload an image file.",
        )

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty.",
        )

    try:
        face_encoding = await run_in_threadpool(_extract_single_face_encoding, image_bytes)
        attendance = await mark_attendance(
            db=db,
            session_id=session_id,
            face_encoding=face_encoding,
        )
        return AttendanceResponse(
            id=attendance.id,
            session_id=attendance.session_id,
            student_id=attendance.student_id,
            confidence_score=float(attendance.confidence_score or 0.0),
            marked_at=attendance.marked_at,
        )
    except AttendanceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        ) from exc
