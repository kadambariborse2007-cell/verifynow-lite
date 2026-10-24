# PAMAC VerifyNow (VerifyNow Lite)

An address verification system (college final year project) that runs fully on **localhost**.

1. A **customer** requests an address check.
2. **Staff** visit the address, upload 3 photos (entrance, nameplate, landmark) and their findings.
3. Staff generate a **1-page PDF report with a QR code**.
4. **Anyone** can scan the QR code to confirm the report is genuine (public verify page shows only case code, result, visit date and status).

## Tech stack

| Part | Technology |
|------|------------|
| Frontend | Plain HTML, CSS, JavaScript (fetch API), Bootstrap 5 via CDN |
| Backend | Python 3.11+ (tested on 3.12; all pinned packages have Windows wheels for 3.11-3.14), FastAPI, SQLAlchemy, Uvicorn |
| Database | PostgreSQL (local) |
| Auth | JWT (python-jose, 8 hour expiry), bcrypt password hashing (passlib + bcrypt 4.0.1) |
| PDF / QR | reportlab, qrcode[pil] |

FastAPI also serves the `frontend/` folder, so the whole app runs from **one command** at http://localhost:8000 (no CORS setup needed).

## Folder structure

```
verifynow-lite/
  backend/
    main.py            app creation, router includes, serves frontend/
    database.py        engine, session, Base
    models.py          users, requests, reports, activity_log tables
    schemas.py         Pydantic request/response models
    auth.py            bcrypt hashing, JWT, get_current_user, require_role
    routes/            auth_routes, request_routes, report_routes, verify_routes
    pdf_utils.py       PDF + QR code generation
    seed.py            creates the demo users
    uploads/           private photos and PDFs (NEVER served directly)
    requirements.txt
    .env.example
  frontend/
    index.html, register.html, login.html, new-request.html, my-requests.html,
    request-detail.html, staff-dashboard.html, staff-request.html, verify.html
    css/style.css
    js/api.js          fetch wrapper that adds the JWT header
    js/auth.js         login state, role checks, navbar, logout
```

## Demo users (created by `seed.py`)

| Role | Username | Password |
|------|----------|----------|
| Staff | `staff1` | `Staff@123` |
| Customer | `demo` | `Demo@123` |

Customers can also self-register. Staff accounts can only be created by `seed.py`.

## How to run (Windows PowerShell)

**1. Create the PostgreSQL database `verifynow`** (use pgAdmin, or psql):

```powershell
psql -U postgres -c "CREATE DATABASE verifynow;"
```

**2. Copy `.env.example` to `.env` and fill `DATABASE_URL` and `SECRET_KEY`:**

```powershell
cd verifynow-lite\backend
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste the output as SECRET_KEY in .env
notepad .env
```

Example `DATABASE_URL`: `postgresql://postgres:YOUR_PG_PASSWORD@localhost:5432/verifynow`

**3. Create a virtual environment and install packages:**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks `Activate.ps1`, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**4. Create the demo users:**

```powershell
python seed.py
```

**5. Start the server:**

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**6. Open http://localhost:8000**

(Linux/macOS: same steps, but use `cp .env.example .env` and `source venv/bin/activate`.)

> **Scan the QR code from a phone:** the phone must be on the same WiFi as the laptop. Set
> `PUBLIC_BASE_URL` in `.env` to the laptop's local IP, for example `PUBLIC_BASE_URL=http://192.168.1.5:8000`
> (find it with `ipconfig`), restart the server and generate the report again. Windows Firewall may ask
> to allow Python on port 8000 - allow it for private networks.

## Demo flow

1. Register a customer (or log in as `demo`) -> **New Request** -> note the case code (e.g. `VN-0001`).
2. Log out, log in as `staff1` -> open the request -> **Start Work**.
3. Fill the findings, add 3 photos (phones open the camera) -> **Save Findings** -> **Generate Report**.
4. Log in as the customer -> open the request -> **Download PDF Report**.
5. Scan the QR code in the PDF (or open `http://localhost:8000/verify.html?code=VN-0001`) -> "Genuine report".

## API endpoints (all under `/api`)

| Method | Path | Who |
|--------|------|-----|
| POST | `/api/auth/register` | public (creates customers only) |
| POST | `/api/auth/login` | public -> `{access_token, role, name}` |
| GET | `/api/me` | logged in |
| POST | `/api/requests` | customer |
| GET | `/api/requests` (`?status=` for staff) | customer: own, staff: all |
| GET | `/api/requests/{id}` | owner customer or staff |
| PATCH | `/api/requests/{id}/status` | staff (Received -> In Progress only) |
| POST | `/api/requests/{id}/findings` | staff, multipart, request must be In Progress |
| POST | `/api/requests/{id}/generate-report` | staff, builds PDF, sets Completed |
| GET | `/api/requests/{id}/photos/{entrance\|nameplate\|landmark}` | owner customer or staff |
| GET | `/api/requests/{id}/report-pdf` | owner customer or staff, only when Completed |
| GET | `/api/requests/{id}/activity` | owner customer or staff |
| GET | `/api/verify/{case_code}` | **public** - only case_code, result, visit_date, status |

Interactive API docs: http://localhost:8000/docs

## Security rules implemented

- Passwords hashed with bcrypt; `password_hash` is never returned.
- Role checks in the backend with `require_role(...)` dependencies (not only in the frontend).
- A customer gets **403** on another customer's request, photos, PDF and activity.
- Uploads: only `.jpg/.jpeg/.png`, max 5 MB each, content checked with Pillow (a renamed `.txt` is rejected), saved with random UUID names in `backend/uploads/`, which is **not** a public folder.
- SQLAlchemy ORM only (no raw SQL), Pydantic validation on all inputs, proper HTTP status codes.
- Status order enforced: Received -> In Progress -> Completed (invalid jumps return 400).
- Public verify page shows no name, address or photos.
