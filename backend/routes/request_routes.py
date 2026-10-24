"""
request_routes.py - Creating and viewing verification requests.

POST  /api/requests                 customer creates a request
GET   /api/requests                 customer: own list, staff: all (optional ?status=)
GET   /api/requests/{id}            one request (customers only their own)
PATCH /api/requests/{id}/status     staff: Received -> In Progress
GET   /api/requests/{id}/activity   activity timeline

The helper functions at the top are also used by report_routes.py.
"""
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from models import ActivityLog, User, VerificationRequest
from schemas import ActivityOut, ReportOut, RequestCreate, RequestOut, StatusUpdate

router = APIRouter(prefix="/api/requests", tags=["requests"])

# The only allowed status moves. "Completed" is set by generate-report, not here.
ALLOWED_STATUS_CHANGES = {"Received": "In Progress"}


# ---------- Helpers ----------
def get_request_for_user(db: Session, request_id: int, user: User) -> VerificationRequest:
    """Load a request and check access: staff see all, customers only their own."""
    req = db.get(VerificationRequest, request_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")
    if user.role != "staff" and req.customer_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this request.")
    return req


def log_activity(db: Session, request_id: int, user_id: int, action: str) -> None:
    """Add one line to the activity log (committed together with the caller's changes)."""
    db.add(ActivityLog(request_id=request_id, user_id=user_id, action=action))


def request_to_out(req: VerificationRequest) -> RequestOut:
    """Convert a database row into the response shape."""
    report_out = None
    if req.report is not None:
        r = req.report
        report_out = ReportOut(
            address_exists=r.address_exists,
            nameplate_match=r.nameplate_match,
            person_met=r.person_met,
            visit_date=r.visit_date,
            result=r.result,
            remarks=r.remarks or "",
            staff_name=r.staff.name,
            pdf_ready=bool(r.pdf_path),
            created_at=r.created_at,
        )
    return RequestOut(
        id=req.id,
        case_code=req.case_code,
        person_name=req.person_name,
        address=req.address,
        purpose=req.purpose,
        status=req.status,
        created_at=req.created_at,
        customer_name=req.customer.name,
        report=report_out,
    )


# ---------- Endpoints ----------
@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    data: RequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("customer")),
):
    req = VerificationRequest(
        customer_id=user.id,
        person_name=data.person_name,
        address=data.address,
        purpose=data.purpose,
        status="Received",
    )
    db.add(req)
    db.flush()  # gives us req.id without committing yet
    req.case_code = f"VN-{req.id:04d}"
    log_activity(db, req.id, user.id, f"Request {req.case_code} submitted by customer")
    db.commit()
    db.refresh(req)
    return request_to_out(req)


@router.get("", response_model=List[RequestOut])
def list_requests(
    # Read from ?status=... (named status_filter in Python to avoid clashing with fastapi.status)
    status_filter: Optional[Literal["Received", "In Progress", "Completed"]] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(VerificationRequest)
    if user.role == "staff":
        if status_filter:
            query = query.filter(VerificationRequest.status == status_filter)
    else:
        # Customers only ever see their own requests
        query = query.filter(VerificationRequest.customer_id == user.id)
    rows = query.order_by(VerificationRequest.id.desc()).all()
    return [request_to_out(r) for r in rows]


@router.get("/{request_id}", response_model=RequestOut)
def get_request(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return request_to_out(get_request_for_user(db, request_id, user))


@router.patch("/{request_id}/status", response_model=RequestOut)
def update_status(
    request_id: int,
    data: StatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("staff")),
):
    req = get_request_for_user(db, request_id, user)
    if ALLOWED_STATUS_CHANGES.get(req.status) != data.status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change status from '{req.status}' to '{data.status}'. "
            "Allowed order: Received -> In Progress -> Completed (Completed is set by Generate Report).",
        )
    req.status = data.status
    log_activity(db, req.id, user.id, f"Status changed to {data.status} by staff")
    db.commit()
    db.refresh(req)
    return request_to_out(req)


@router.get("/{request_id}/activity", response_model=List[ActivityOut])
def get_activity(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_request_for_user(db, request_id, user)  # access check
    rows = (
        db.query(ActivityLog)
        .filter(ActivityLog.request_id == request_id)
        .order_by(ActivityLog.created_at, ActivityLog.id)
        .all()
    )
    return [ActivityOut(id=a.id, action=a.action, user_name=a.user.name, created_at=a.created_at) for a in rows]
