"""
pdf_utils.py - Builds the 1-page A4 PDF report with a QR code (reportlab + qrcode).

The QR code encodes:  PUBLIC_BASE_URL + "/verify.html?code=" + case_code
so anyone can scan it and confirm the report is genuine.
"""
import io
import os
import uuid
from datetime import datetime
from pathlib import Path

import qrcode
from dotenv import load_dotenv
from PIL import Image as PILImage
from PIL import ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, KeepInFrame, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

load_dotenv()

APP_NAME = "PAMAC VerifyNow"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

# Private folder for photos and PDFs (never served as static files)
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

BRAND_BLUE = colors.HexColor("#0d6efd")
RESULT_COLORS = {
    "Verified": colors.HexColor("#198754"),
    "Not verified": colors.HexColor("#dc3545"),
    "Unable to verify": colors.HexColor("#fd7e14"),
}


def build_verify_url(case_code: str) -> str:
    return f"{PUBLIC_BASE_URL}/verify.html?code={case_code}"


def draw_shield_logo(canvas, x, y, size):
    """Draw the tick-in-a-shield logo with plain vector shapes (no image file)."""
    w = h = size
    shield = canvas.beginPath()
    shield.moveTo(x + w * 0.5, y + h)
    shield.lineTo(x + w * 0.92, y + h * 0.84)
    shield.lineTo(x + w * 0.92, y + h * 0.50)
    shield.curveTo(x + w * 0.92, y + h * 0.22, x + w * 0.72, y + h * 0.06, x + w * 0.5, y)
    shield.curveTo(x + w * 0.28, y + h * 0.06, x + w * 0.08, y + h * 0.22, x + w * 0.08, y + h * 0.50)
    shield.lineTo(x + w * 0.08, y + h * 0.84)
    shield.close()
    canvas.setFillColor(colors.white)
    canvas.drawPath(shield, stroke=0, fill=1)

    tick = canvas.beginPath()
    tick.moveTo(x + w * 0.30, y + h * 0.52)
    tick.lineTo(x + w * 0.45, y + h * 0.36)
    tick.lineTo(x + w * 0.71, y + h * 0.66)
    canvas.setStrokeColor(BRAND_BLUE)
    canvas.setLineWidth(size * 0.1)
    canvas.setLineCap(1)
    canvas.setLineJoin(1)
    canvas.drawPath(tick, stroke=1, fill=0)


def draw_header_footer(canvas, doc):
    """Blue header bar with logo + app name, and a small footer line."""
    page_w, page_h = A4
    canvas.saveState()
    canvas.setFillColor(BRAND_BLUE)
    canvas.rect(0, page_h - 2.2 * cm, page_w, 2.2 * cm, stroke=0, fill=1)
    draw_shield_logo(canvas, 1.5 * cm, page_h - 1.85 * cm, 1.5 * cm)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 18)
    canvas.drawString(3.3 * cm, page_h - 1.25 * cm, APP_NAME)
    canvas.setFont("Helvetica", 9)
    canvas.drawString(3.3 * cm, page_h - 1.7 * cm, "Address Verification Service")

    canvas.setFillColor(colors.grey)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(page_w / 2, 1 * cm,
                             f"{APP_NAME} - scan the QR code or visit {PUBLIC_BASE_URL}/verify.html to check this report.")
    canvas.restoreState()


def photo_flowable(file_name: str, max_w: float, max_h: float) -> Image:
    """Shrink a photo in memory (keeps the PDF small) and return a reportlab Image."""
    with PILImage.open(UPLOAD_DIR / file_name) as img:
        img = ImageOps.exif_transpose(img)  # respect phone rotation
        img = img.convert("RGB")
        img.thumbnail((800, 800))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=80)
        width, height = img.size
    buffer.seek(0)
    scale = min(max_w / width, max_h / height)
    return Image(buffer, width=width * scale, height=height * scale)


def qr_flowable(url: str, size: float) -> Image:
    buffer = io.BytesIO()
    qrcode.make(url).save(buffer, format="PNG")
    buffer.seek(0)
    return Image(buffer, width=size, height=size)


def yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def generate_report_pdf(req, report, staff_name: str) -> str:
    """Create the PDF in uploads/ and return its (random) file name."""
    file_name = f"{uuid.uuid4().hex}.pdf"
    doc = SimpleDocTemplate(
        str(UPLOAD_DIR / file_name), pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=2.8 * cm, bottomMargin=1.6 * cm,
        title=f"{APP_NAME} - {req.case_code}", author=APP_NAME,
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Title"], fontSize=17, spaceAfter=4)
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontSize=9.5, leading=12)
    label = ParagraphStyle("label", parent=normal, fontName="Helvetica-Bold")
    caption = ParagraphStyle("caption", parent=normal, fontSize=8.5, alignment=1)
    result_style = ParagraphStyle("result", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=20,
                                  leading=24, alignment=1,
                                  textColor=RESULT_COLORS.get(report.result, colors.black))

    def esc(text) -> str:
        """Escape &, <, > because Paragraph understands simple HTML tags."""
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")

    story = [Paragraph("Address Verification Report", title),
             Paragraph(f"Case code: <b>{esc(req.case_code)}</b>", ParagraphStyle("c", parent=normal, alignment=1)),
             Spacer(1, 0.3 * cm)]

    # Details table (label / value pairs)
    rows = [
        ("Person name", req.person_name),
        ("Address", req.address),
        ("Purpose", req.purpose),
        ("Visit date", report.visit_date.strftime("%d %b %Y")),
        ("Address exists", yes_no(report.address_exists)),
        ("Nameplate match", yes_no(report.nameplate_match)),
        ("Person met", report.person_met),
        ("Remarks", report.remarks or "-"),
        ("Verified by (staff)", staff_name),
        ("Generated on", datetime.now().strftime("%d %b %Y, %I:%M %p")),
    ]
    details = Table([[Paragraph(k, label), Paragraph(esc(v), normal)] for k, v in rows],
                    colWidths=[4.2 * cm, 13.8 * cm])
    details.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5ff")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [details, Spacer(1, 0.35 * cm)]

    # Final result - big and bold
    result_box = Table([[Paragraph("FINAL RESULT", caption)], [Paragraph(esc(report.result.upper()), result_style)]],
                       colWidths=[18 * cm])
    result_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.2, RESULT_COLORS.get(report.result, colors.black)),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [result_box, Spacer(1, 0.35 * cm)]

    # Three photos in a row with captions
    photo_w, photo_h = 5.6 * cm, 4.2 * cm
    photos = Table(
        [[photo_flowable(report.entrance_photo, photo_w, photo_h),
          photo_flowable(report.nameplate_photo, photo_w, photo_h),
          photo_flowable(report.landmark_photo, photo_w, photo_h)],
         [Paragraph("Entrance", caption), Paragraph("Nameplate", caption), Paragraph("Landmark", caption)]],
        colWidths=[6 * cm] * 3, rowHeights=[photo_h + 0.2 * cm, None],
    )
    photos.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [photos, Spacer(1, 0.3 * cm)]

    # QR code with explanation
    verify_url = build_verify_url(req.case_code)
    qr_text = Paragraph(
        "<b>Verify this report</b><br/>Scan the QR code with any phone camera to confirm this report is "
        f"genuine, or open:<br/><font color='#0d6efd'>{esc(verify_url)}</font>", normal)
    qr_table = Table([[qr_flowable(verify_url, 3.3 * cm), qr_text]], colWidths=[3.8 * cm, 14.2 * cm])
    qr_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(qr_table)

    # KeepInFrame shrinks everything slightly if very long remarks/address would need a 2nd page
    one_page = KeepInFrame(doc.width, doc.height, story, mode="shrink")
    doc.build([one_page], onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
    return file_name
