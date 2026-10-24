"""
models.py - Database tables defined as SQLAlchemy ORM classes.

Tables: users, requests, reports, activity_log
They are created automatically on startup by Base.metadata.create_all() in main.py.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


def utc_now():
    """Current time in UTC (stored with timezone so the browser can show local time)."""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # "customer" or "staff"


class VerificationRequest(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, index=True)
    # Filled right after insert using the id, e.g. id 1 -> "VN-0001"
    case_code = Column(String(20), unique=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    person_name = Column(String(100), nullable=False)
    address = Column(Text, nullable=False)
    purpose = Column(String(20), nullable=False)  # Job / Loan / Rent / Other
    status = Column(String(20), nullable=False, default="Received")  # Received / In Progress / Completed
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    customer = relationship("User")
    report = relationship("Report", back_populates="request", uselist=False)


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id"), unique=True, nullable=False)
    address_exists = Column(Boolean, nullable=False)
    nameplate_match = Column(Boolean, nullable=False)
    person_met = Column(String(20), nullable=False)  # Self / Family / Neighbour / Nobody
    visit_date = Column(Date, nullable=False)
    result = Column(String(30), nullable=False)  # Verified / Not verified / Unable to verify
    remarks = Column(Text, default="")
    # Only the random file names are stored; files live in backend/uploads/
    entrance_photo = Column(String(100), nullable=False)
    nameplate_photo = Column(String(100), nullable=False)
    landmark_photo = Column(String(100), nullable=False)
    pdf_path = Column(String(100))  # filled when the PDF is generated
    staff_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    request = relationship("VerificationRequest", back_populates="report")
    staff = relationship("User")


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User")
