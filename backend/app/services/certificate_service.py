"""
GovTender Bid Award Certificate Generator
Produces a server-side PDF with:
  - Bid award details (bidder name, tender, amount)
  - Signed Verifiable Credential (VC) block
  - PixelPass-style QR code embedding the signed credential URL
  - MOSIP-style seal / watermark
"""
import io
import os
import datetime
import json
import qrcode

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas as rl_canvas


# ── Colour Palette ────────────────────────────────────────────────────────────
DARK_BG    = colors.HexColor("#ffffff")
CARD_BG    = colors.HexColor("#f9fafb")
BORDER     = colors.HexColor("#e5e7eb")
CYAN       = colors.HexColor("#0284c7")
GREEN      = colors.HexColor("#059669")
DARK_GREEN = colors.HexColor("#15803d")
GOLD       = colors.HexColor("#d97706")
TEXT_PRI   = colors.HexColor("#111827")
TEXT_SEC   = colors.HexColor("#4b5563")
TEXT_MUT   = colors.HexColor("#6b7280")
WHITE      = colors.white
RED_REJECT = colors.HexColor("#ef4444")


def _make_qr_image(data: str, size_px: int = 180) -> io.BytesIO:
    """Generate a QR code image in memory and return as BytesIO."""
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#030712", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _draw_background(canvas: rl_canvas.Canvas, doc):
    """Draw the dark background and decorative border on every page."""
    w, h = A4
    canvas.saveState()

    # Dark background
    canvas.setFillColor(DARK_BG)
    canvas.rect(0, 0, w, h, fill=1, stroke=0)

    # Outer border
    canvas.setStrokeColor(CYAN)
    canvas.setLineWidth(1.5)
    canvas.rect(10 * mm, 10 * mm, w - 20 * mm, h - 20 * mm, fill=0, stroke=1)

    # Inner subtle border
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.rect(13 * mm, 13 * mm, w - 26 * mm, h - 26 * mm, fill=0, stroke=1)

    canvas.restoreState()


def generate_bid_certificate_pdf(
    bid_id: str,
    bid_ref: str,
    vendor_name: str,
    vendor_email: str,
    tender_title: str,
    tender_no: str,
    department: str,
    bid_value: float,
    issue_date: str,
    vc_id: str,
    issuer_did: str,
    credential_json: dict,
    qr_base_url: str = "http://localhost:8080",
) -> bytes:
    """
    Generates the PDF certificate and returns raw bytes.
    """
    buf = io.BytesIO()
    w, h = A4

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom paragraph styles
    def sty(name, **kw):
        s = ParagraphStyle(name, **kw)
        return s

    h1   = sty("h1",   fontName="Helvetica-Bold",   fontSize=22, textColor=TEXT_PRI, alignment=TA_CENTER, spaceAfter=8, leading=26)
    h2   = sty("h2",   fontName="Helvetica-Bold",   fontSize=14, textColor=CYAN,     alignment=TA_CENTER, spaceAfter=4, leading=18)
    sub  = sty("sub",  fontName="Helvetica",         fontSize=9,  textColor=TEXT_SEC, alignment=TA_CENTER, spaceAfter=10, leading=12)
    lbl  = sty("lbl",  fontName="Helvetica-Bold",   fontSize=7,  textColor=TEXT_MUT, spaceAfter=4, leading=10)
    val  = sty("val",  fontName="Helvetica-Bold",   fontSize=11, textColor=TEXT_PRI, spaceAfter=14, leading=14)
    val_g= sty("val_g",fontName="Helvetica-Bold",   fontSize=13, textColor=DARK_GREEN, spaceAfter=14, leading=16)
    tiny = sty("tiny", fontName="Helvetica",         fontSize=7,  textColor=TEXT_MUT, alignment=TA_CENTER, leading=10)
    vc_t = sty("vc_t", fontName="Helvetica-Bold",   fontSize=8,  textColor=DARK_GREEN, leading=11)
    vc_v = sty("vc_v", fontName="Helvetica",         fontSize=7,  textColor=TEXT_SEC, leading=10, wordWrap='LTR')
    warn = sty("warn", fontName="Helvetica",         fontSize=8,  textColor=GOLD,     alignment=TA_CENTER)

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("GovTender", sty("gt", fontName="Helvetica-Bold", fontSize=30,
                                             textColor=CYAN, alignment=TA_CENTER, spaceAfter=8, leading=36)))
    story.append(Paragraph("GOVERNMENT PROCUREMENT AUTHORITY", sty("gtSub",
                             fontName="Helvetica", fontSize=8, textColor=TEXT_MUT,
                             alignment=TA_CENTER, spaceAfter=6, tracking=120, leading=10)))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("BID AWARD CERTIFICATE", h1))
    story.append(Paragraph("Verifiable Credential  ·  Cryptographically Signed  ·  MOSIP IDA Authenticated", sub))
    story.append(Spacer(1, 8 * mm))

    # ── Status Banner ──────────────────────────────────────────────────────────
    banner_data = [[ Paragraph("✓  APPROVED & AWARDED", sty("ban",
        fontName="Helvetica-Bold", fontSize=14, textColor=WHITE, alignment=TA_CENTER)) ]]
    banner_tbl = Table(banner_data, colWidths=[doc.width])
    banner_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREEN),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [GREEN]),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(banner_tbl)
    story.append(Spacer(1, 8 * mm))

    # ── Bidder Info ────────────────────────────────────────────────────────────
    story.append(Paragraph("CERTIFICATE ISSUED TO", lbl))
    story.append(Paragraph(vendor_name, sty("vn", fontName="Helvetica-Bold", fontSize=18,
                                             textColor=TEXT_PRI, spaceAfter=6, leading=22)))
    story.append(Paragraph(vendor_email, sty("ve", fontName="Helvetica", fontSize=9,
                                              textColor=TEXT_SEC, spaceAfter=14, leading=12)))
    story.append(HRFlowable(width="100%", thickness=0.3, color=BORDER, spaceAfter=8))

    # ── Two-column details grid ───────────────────────────────────────────────
    half = doc.width / 2 - 4 * mm
    grid_data = [
        [
            [Paragraph("TENDER REFERENCE", lbl), Paragraph(f"#{tender_no}", val)],
            [Paragraph("BID REFERENCE", lbl),    Paragraph(f"#{bid_ref}", val)],
        ],
        [
            [Paragraph("TENDER TITLE", lbl),     Paragraph(tender_title, sty("tt", fontName="Helvetica-Bold",
                                                  fontSize=10, textColor=TEXT_PRI, spaceAfter=10, leading=13))],
            [Paragraph("ISSUING DEPARTMENT", lbl), Paragraph(department, val)],
        ],
        [
            [Paragraph("AWARDED BID VALUE", lbl), Paragraph(f"₹ {bid_value:,.2f} INR", val_g)],
            [Paragraph("CERTIFICATE DATE", lbl),  Paragraph(issue_date, val)],
        ],
    ]

    def cell(*paras):
        """Wrap a list of paragraphs into a table cell."""
        return paras

    flat_rows = []
    for row in grid_data:
        left_content  = row[0]
        right_content = row[1]
        flat_rows.append([
            Table([[p] for p in left_content],  colWidths=[half]),
            Table([[p] for p in right_content], colWidths=[half]),
        ])

    detail_tbl = Table(flat_rows, colWidths=[half + 4 * mm, half + 4 * mm])
    detail_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), CARD_BG),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [CARD_BG, CARD_BG]),
        ("GRID",          (0, 0), (-1, -1), 0.3, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(detail_tbl)
    story.append(Spacer(1, 8 * mm))

    # ── Verifiable Credential Section ─────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=DARK_GREEN, spaceAfter=6))
    story.append(Paragraph("VERIFIABLE CREDENTIAL (W3C VC 1.1)", sty("vct",
        fontName="Helvetica-Bold", fontSize=10, textColor=DARK_GREEN, spaceAfter=6, leading=12)))

    # QR Code — encodes the VC verification URL
    qr_url = f"{qr_base_url}/verify/{vc_id}"
    qr_buf = _make_qr_image(qr_url, size_px=200)
    qr_img = Image(qr_buf, width=42 * mm, height=42 * mm)

    # VC details text column
    vc_json_snippet = json.dumps(credential_json, indent=2)[:500] + "\n..."
    vc_details = [
        [Paragraph("CREDENTIAL ID (VC)", vc_t)],
        [Paragraph(vc_id, vc_v)],
        [Spacer(1, 3 * mm)],
        [Paragraph("ISSUER DID", vc_t)],
        [Paragraph(issuer_did, vc_v)],
        [Spacer(1, 3 * mm)],
        [Paragraph("TYPE", vc_t)],
        [Paragraph("VerifiableCredential · GovernmentBidAwardCredential", vc_v)],
        [Spacer(1, 3 * mm)],
        [Paragraph("SCAN QR TO VERIFY →", sty("qrl",
            fontName="Helvetica-Bold", fontSize=7, textColor=CYAN))],
    ]
    vc_text_tbl = Table(vc_details, colWidths=[doc.width - 50 * mm])
    vc_text_tbl.setStyle(TableStyle([
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))

    # Side-by-side: text | qr
    vc_row = Table(
        [[vc_text_tbl, qr_img]],
        colWidths=[doc.width - 50 * mm, 50 * mm]
    )
    vc_row.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), CARD_BG),
        ("BOX",           (0, 0), (-1, -1), 0.5, GREEN),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(vc_row)
    story.append(Spacer(1, 6 * mm))

    # ── VC JSON Snippet ───────────────────────────────────────────────────────
    story.append(Paragraph("SIGNED CREDENTIAL PAYLOAD (JSON-LD)", sty("jsonT",
        fontName="Helvetica-Bold", fontSize=7, textColor=TEXT_MUT, spaceAfter=3, leading=9)))
    story.append(Paragraph(
        vc_json_snippet.replace("\n", "<br/>").replace(" ", "&nbsp;"),
        sty("jsonBody", fontName="Courier", fontSize=6, textColor=DARK_GREEN, leading=9,
            backColor=DARK_BG, leftIndent=6, spaceAfter=6)
    ))

    story.append(HRFlowable(width="100%", thickness=0.3, color=BORDER, spaceAfter=6))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Paragraph(
        "This certificate was generated automatically by the GovTender Procurement Platform upon bid approval. "
        "The embedded QR code encodes a W3C Verifiable Credential signed by MOSIP's IDA Authority. "
        "Scan to verify authenticity at any time.",
        tiny
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC  ·  "
        "Powered by MOSIP · eSignet · Inji Certify · W3C VC",
        tiny
    ))

    # Build PDF with background on every page
    doc.build(story, onFirstPage=_draw_background, onLaterPages=_draw_background)

    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
