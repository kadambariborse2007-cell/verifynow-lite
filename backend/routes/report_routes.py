"""
report_routes.py - Staff findings, PDF generation, and protected file downloads.

POST /api/requests/{id}/findings         staff: save findings + 3 photos (multipart form)
POST /api/requests/{id}/generate-report  staff: build the PDF, mark Completed
GET  /api/requests/{id}/photos/{kind}    owner customer or staff: one photo
GET  /api/requests/{id}/report-pdf       owner customer or staff: the PDF (only when Completed)

Uploaded files are stored in backend/uploads/ with random UUID names.
That folder is NOT a public static folder - files are only returned through
these endpoints after the access check.
"""
import io
import uuid
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from models import Report, User
from pdf_utils import UPLOAD_DIR, generate_report_pdf
from routes.request_routes import get_request_for_user, log_activity, request_to_out
from schemas import RequestOut

router = APIRouter(prefix="/api/requests", tags=["reports"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG"}  # what Pillow reports for real jpg/png files
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
PHOTO_COLUMNS = {"entrance": "entrance_photo", "nameplate": "nameplate_photo", "landmark": "landmark_photo"}


def save_photo(upload: UploadFile, label: str) -> str:
    """Validate one uploaded photo and save it with a random name. Returns the file name."""
    extension = Path(upload.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label}: only .jpg, .jpeg or .png files are allowed.",
        )

    # Read at most 5 MB + 1 byte, so we can detect files that are too big
    content = upload.file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{label}: file is larger than 5 MB.")
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{label}: file is empty.")

    # Check the content really is an image (a renamed .txt file will fail here)
    try:
        with Image.open(io.BytesIO(content)) as img:
            image_format = img.format
            img.verify()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{label}: file is not a valid image.")
    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{label}: only JPG or PNG images are allowed.")

    file_name = f"{uuid.uuid4().hex}{'.png' if image_format == 'PNG' else '.jpg'}"
    (UPLOAD_DIR / file_name).write_bytes(content)
    return file_name


def delete_file(file_name) -> None:
    """Remove an old upload (used when findings are saved again)."""
    if file_name:
        (UPLOAD_DIR / file_name).unlink(missing_ok=True)


@router.post("/{request_id}/findings", response_model=RequestOut)
def save_findings(
    request_id: int,
    # Form fields are validated by FastAPI/Pydantic using these types
    address_exists: bool = Form(...),
    nameplate_match: bool = Form(...),
    person_met: Literal["Self", "Family", "Neighbour", "Nobody"] = Form(...),
    visit_date: date = Form(...),
    result: Literal["Verified", "Not verified", "Unable to verify"] = Form(...),
    remarks: str = Form("", max_length=1000),
    entrance_photo: UploadFile = File(...),
    nameplate_photo: UploadFile = File(...),
    landmark_photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("staff")),
):
    req = get_request_for_user(db, request_id, user)
    if req.status != "In Progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Findings can only be saved when the request is 'In Progress' (current: '{req.status}').",
        )
    if visit_date > date.today():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Visit date cannot be in the future.")

    # Save all three photos; if one fails, remove the ones already saved
    saved = []
    try:
        for upload, label in (
            (entrance_photo, "Entrance photo"),
            (nameplate_photo, "Nameplate photo"),
            (landmark_photo, "Landmark photo"),
        ):
            saved.append(save_photo(upload, label))
    except HTTPException:
        for name in saved:
            delete_file(name)
        raise

    report = req.report
    if report is None:
        report = Report(request_id=req.id)
        db.add(report)
        action = "Findings and 3 photos uploaded by staff"
    else:
        # Findings saved again before generating the report: replace old photos
        for old in (report.entrance_photo, report.nameplate_photo, report.landmark_photo):
            delete_file(old)
        action = "Findings updated by staff"

    report.address_exists = address_exists
    report.nameplate_match = nameplate_match
    report.person_met = person_met
    report.visit_date = visit_date
    report.result = result
    report.remarks = remarks.strip()
    report.entrance_photo, report.nameplate_photo, report.landmark_photo = saved
    report.staff_id = user.id

    log_activity(db, req.id, user.id, action)
    db.commit()
    db.refresh(req)
    return request_to_out(req)


@router.post("/{request_id}/generate-report", response_model=RequestOut)
def generate_report(request_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("staff"))):
    req = get_request_for_user(db, request_id, user)
    if req.status != "In Progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Report can only be generated when the request is 'In Progress' (current: '{req.status}').",
        )
    if req.report is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Save the findings and photos first.")

    req.report.pdf_path = generate_report_pdf(req, req.report, user.name)
    req.status = "Completed"
    log_activity(db, req.id, user.id, "PDF report generated, status changed to Completed")
    db.commit()
    db.refresh(req)
    return request_to_out(req)


@router.get("/{request_id}/photos/{kind}")
def get_photo(
    request_id: int,
    kind: Literal["entrance", "nameplate", "landmark"],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = get_request_for_user(db, request_id, user)  # 403 for other customers
    if req.report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No photos uploaded yet.")
    path = UPLOAD_DIR / getattr(req.report, PHOTO_COLUMNS[kind])
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo file missing on server.")
    media_type = "image/png" if path.suffix == ".png" else "image/jpeg"
    return FileResponse(path, media_type=media_type)


@router.get("/{request_id}/report-pdf")
def get_report_pdf(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = get_request_for_user(db, request_id, user)  # 403 for other customers
    if req.status != "Completed" or req.report is None or not req.report.pdf_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report is not ready yet.")
    path = UPLOAD_DIR / req.report.pdf_path
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file missing on server.")
    return FileResponse(path, media_type="application/pdf", filename=f"{req.case_code}-report.pdf")
