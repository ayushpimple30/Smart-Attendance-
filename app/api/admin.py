from __future__ import annotations

from datetime import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import require_admin
from app.models.batch import Batch
from app.models.division import Division
from app.models.enums import UserRole
from app.models.faculty import Faculty
from app.models.student import Student
from app.models.subject import Subject
from app.models.user import User
from app.services.timetable_engine import TimetableValidationError, create_timetable_entry

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)])


class DivisionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=1, le=8)


class DivisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    year: int


class BatchCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    division_id: UUID


class BatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    division_id: UUID


class SubjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=50)
    semester: int = Field(ge=1, le=12)


class SubjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    semester: int


class FacultyCreateRequest(BaseModel):
    user_id: UUID
    department: str | None = Field(default=None, max_length=120)


class FacultyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    department: str | None


class StudentCreateRequest(BaseModel):
    user_id: UUID
    division_id: UUID
    batch_id: UUID | None = None
    roll_number: str = Field(min_length=1, max_length=50)
    face_encoding: list[float] | None = None


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    division_id: UUID
    batch_id: UUID | None
    roll_number: str
    face_encoding: list[float] | None


class TimetableCreateRequest(BaseModel):
    faculty_id: UUID
    subject_id: UUID
    division_id: UUID
    batch_id: UUID | None = None
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    session_type: str


class TimetableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject_id: UUID
    faculty_id: UUID
    division_id: UUID
    batch_id: UUID | None
    day_of_week: int
    start_time: time
    end_time: time
    session_type: str


@router.post("/divisions", response_model=DivisionResponse, status_code=status.HTTP_201_CREATED)
async def create_division(payload: DivisionCreateRequest, db: AsyncSession = Depends(get_db_session)) -> Division:
    existing = await db.execute(select(Division).where(Division.name == payload.name.strip()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Division name already exists.")

    division = Division(name=payload.name.strip(), year=payload.year)
    db.add(division)
    await db.commit()
    await db.refresh(division)
    return division


@router.post("/batches", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(payload: BatchCreateRequest, db: AsyncSession = Depends(get_db_session)) -> Batch:
    division = await db.execute(select(Division).where(Division.id == payload.division_id))
    if division.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Division not found.")

    batch = Batch(name=payload.name.strip(), division_id=payload.division_id)
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return batch


@router.post("/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(payload: SubjectCreateRequest, db: AsyncSession = Depends(get_db_session)) -> Subject:
    existing = await db.execute(select(Subject).where(Subject.code == payload.code.strip()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject code already exists.")

    subject = Subject(name=payload.name.strip(), code=payload.code.strip(), semester=payload.semester)
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return subject


@router.post("/faculty", response_model=FacultyResponse, status_code=status.HTTP_201_CREATED)
async def create_faculty(payload: FacultyCreateRequest, db: AsyncSession = Depends(get_db_session)) -> Faculty:
    user_result = await db.execute(select(User).where(User.id == payload.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.role != UserRole.FACULTY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User role must be FACULTY.")

    existing = await db.execute(select(Faculty).where(Faculty.user_id == payload.user_id))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Faculty already exists.")

    faculty = Faculty(user_id=payload.user_id, department=payload.department)
    db.add(faculty)
    await db.commit()
    await db.refresh(faculty)
    return faculty


@router.post("/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(payload: StudentCreateRequest, db: AsyncSession = Depends(get_db_session)) -> Student:
    user_result = await db.execute(select(User).where(User.id == payload.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User role must be STUDENT.")

    division_result = await db.execute(select(Division).where(Division.id == payload.division_id))
    if division_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Division not found.")

    if payload.batch_id is not None:
        batch_result = await db.execute(select(Batch).where(Batch.id == payload.batch_id))
        batch = batch_result.scalar_one_or_none()
        if batch is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")
        if batch.division_id != payload.division_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Batch does not belong to division.")

    existing_roll = await db.execute(
        select(Student).where(
            Student.division_id == payload.division_id,
            Student.roll_number == payload.roll_number.strip(),
        )
    )
    if existing_roll.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Roll number already exists in division.",
        )

    existing_student = await db.execute(select(Student).where(Student.user_id == payload.user_id))
    if existing_student.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student already exists.")

    student = Student(
        user_id=payload.user_id,
        division_id=payload.division_id,
        batch_id=payload.batch_id,
        roll_number=payload.roll_number.strip(),
        face_encoding=payload.face_encoding,
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


@router.post("/timetable", response_model=TimetableResponse, status_code=status.HTTP_201_CREATED)
async def create_timetable(payload: TimetableCreateRequest, db: AsyncSession = Depends(get_db_session)):
    faculty_result = await db.execute(select(Faculty).where(Faculty.id == payload.faculty_id))
    if faculty_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty not found.")

    subject_result = await db.execute(select(Subject).where(Subject.id == payload.subject_id))
    if subject_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found.")

    division_result = await db.execute(select(Division).where(Division.id == payload.division_id))
    if division_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Division not found.")

    if payload.batch_id is not None:
        batch_result = await db.execute(select(Batch).where(Batch.id == payload.batch_id))
        batch = batch_result.scalar_one_or_none()
        if batch is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")
        if batch.division_id != payload.division_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Batch does not belong to division.")

    try:
        entry = await create_timetable_entry(
            db=db,
            data={
                "faculty_id": payload.faculty_id,
                "subject_id": payload.subject_id,
                "division_id": payload.division_id,
                "batch_id": payload.batch_id,
                "day_of_week": payload.weekday,
                "start_time": payload.start_time,
                "end_time": payload.end_time,
                "session_type": payload.session_type,
            },
        )
    except TimetableValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return TimetableResponse(
        id=entry.id,
        subject_id=entry.subject_id,
        faculty_id=entry.faculty_id,
        division_id=entry.division_id,
        batch_id=entry.batch_id,
        day_of_week=entry.day_of_week,
        start_time=entry.start_time,
        end_time=entry.end_time,
        session_type=entry.session_type.value,
    )
