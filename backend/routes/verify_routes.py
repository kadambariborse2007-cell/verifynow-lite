"""
verify_routes.py - PUBLIC endpoint used by the QR code (no login needed).

GET /api/verify/{case_code}
Returns ONLY case_code, result, visit_date and status.
No name, address or photos are ever exposed here.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import VerificationRequest
from schemas import VerifyOut

router = APIRouter(prefix="/api/verify", tags=["verify"])


@router.get("/{case_code}", response_model=VerifyOut)
def verify_report(case_code: str, db: Session = Depends(get_db)):
    req = (
        db.query(VerificationRequest)
        .filter(VerificationRequest.case_code == case_code.strip().upper())
        .first()
    )
    # A report is "genuine" only after staff have generated the PDF
    if req is None or req.status != "Completed" or req.report is None or not req.report.pdf_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No report found for this case code.")

    return VerifyOut(
        case_code=req.case_code,
        result=req.report.result,
        visit_date=req.report.visit_date,
        status=req.status,
    )
