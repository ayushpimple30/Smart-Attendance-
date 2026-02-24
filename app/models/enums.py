from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    FACULTY = "FACULTY"
    STUDENT = "STUDENT"


class SessionType(str, Enum):
    LECTURE = "LECTURE"
    PRACTICAL = "PRACTICAL"


class SessionStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class AttendanceStatus(str, Enum):
    PRESENT = "PRESENT"
    LATE = "LATE"
    ABSENT = "ABSENT"
