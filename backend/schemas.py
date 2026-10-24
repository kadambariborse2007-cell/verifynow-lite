"""
schemas.py - Pydantic models.

They validate incoming JSON and control exactly what goes out in responses
(for example, password_hash is never part of any response model).
"""
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------- Auth ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.]+$")
    password: str = Field(min_length=6, max_length=72)  # bcrypt only uses the first 72 bytes

    @field_validator("name", "username")
    @classmethod
    def strip_spaces(cls, value: str) -> str:
        return value.strip()


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=72)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    username: str
    role: str


# ---------- Requests ----------
class RequestCreate(BaseModel):
    person_name: str = Field(min_length=2, max_length=100)
    address: str = Field(min_length=5, max_length=500)
    purpose: Literal["Job", "Loan", "Rent", "Other"]

    @field_validator("person_name", "address")
    @classmethod
    def strip_spaces(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("must not be empty")
        return value


class StatusUpdate(BaseModel):
    status: Literal["Received", "In Progress", "Completed"]


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    address_exists: bool
    nameplate_match: bool
    person_met: str
    visit_date: date
    result: str
    remarks: Optional[str] = ""
    staff_name: str
    pdf_ready: bool
    created_at: datetime


class RequestOut(BaseModel):
    id: int
    case_code: str
    person_name: str
    address: str
    purpose: str
    status: str
    created_at: datetime
    customer_name: str
    report: Optional[ReportOut] = None


class ActivityOut(BaseModel):
    id: int
    action: str
    user_name: str
    created_at: datetime


# ---------- Public verification ----------
class VerifyOut(BaseModel):
    case_code: str
    result: str
    visit_date: date
    status: str


class MessageOut(BaseModel):
    message: str


RequestList = List[RequestOut]
