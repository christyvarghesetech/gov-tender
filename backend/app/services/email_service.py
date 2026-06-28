"""
GovTender Email Notification Service
Sends rich HTML emails via SMTP with graceful fallback when SMTP is not configured.
"""
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

# Read SMTP settings from environment
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@govtender.gov")
SMTP_ENABLED = bool(SMTP_HOST and SMTP_USER and SMTP_PASS)


def _build_html(title: str, preheader: str, body_html: str) -> str:
    """Wrap body content in the GovTender email shell."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#030712;font-family:'Inter',Arial,sans-serif;color:#f9fafb;">
  <div style="display:none;max-height:0;overflow:hidden;">{preheader}</div>

  <!-- Wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#030712;padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#0a0f1e,#111827);border:1px solid rgba(255,255,255,0.08);border-radius:16px 16px 0 0;padding:32px 40px;text-align:center;">
              <table cellpadding="0" cellspacing="0" style="margin:0 auto 12px;">
                <tr>
                  <td style="background:linear-gradient(135deg,#06b6d4,#3b82f6);border-radius:12px;padding:10px 16px;font-size:20px;font-weight:800;color:#fff;letter-spacing:-0.5px;">GT</td>
                  <td style="padding-left:12px;font-size:20px;font-weight:700;color:#f9fafb;letter-spacing:-0.5px;">GovTender</td>
                </tr>
              </table>
              <p style="margin:0;font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;">Secure Government Procurement Platform</p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="background:rgba(17,24,39,0.95);border-left:1px solid rgba(255,255,255,0.08);border-right:1px solid rgba(255,255,255,0.08);padding:40px;">
              {body_html}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#0a0f1e;border:1px solid rgba(255,255,255,0.06);border-radius:0 0 16px 16px;padding:24px 40px;text-align:center;">
              <p style="margin:0 0 8px;font-size:12px;color:#6b7280;">
                This notification was sent by the <strong style="color:#9ca3af;">GovTender Automated Engine</strong>.
              </p>
              <p style="margin:0;font-size:11px;color:#4b5563;">
                Powered by MOSIP · W3C Verifiable Credentials · eSignet
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def send_email(to_email: str, subject: str, html_body: str, preheader: str = "") -> bool:
    """
    Send an HTML email. Returns True on success, False on failure.
    Silently skips sending if SMTP is not configured (logs to console instead).
    """
    full_html = _build_html(subject, preheader, html_body)

    if not SMTP_ENABLED:
        print(f"[EMAIL MOCK] To: {to_email} | Subject: {subject}")
        print(f"[EMAIL MOCK] SMTP not configured — email logged only (set SMTP_HOST, SMTP_USER, SMTP_PASS in .env)")
        return True  # treat as success in mock mode

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[GovTender] {subject}"
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg.attach(MIMEText(full_html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())

        print(f"[EMAIL] Sent: '{subject}' → {to_email}")
        return True

    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send '{subject}' to {to_email}: {e}")
        return False


# ─── TEMPLATE FACTORIES ───────────────────────────────────────────────────────

def email_new_tender(
    to_email: str,
    recipient_name: str,
    tender_title: str,
    tender_no: str,
    department: str,
    budget: float,
    deadline: str,
    category: str,
):
    subject = f"New Tender Published — {tender_no}"
    preheader = f"A new {category} tender from {department} is now accepting bids."
    body = f"""
      <h1 style="margin:0 0 8px;font-size:26px;font-weight:700;color:#f9fafb;">New Tender Published 🏛️</h1>
      <p style="margin:0 0 28px;font-size:15px;color:#9ca3af;">Hello <strong style="color:#f9fafb;">{recipient_name}</strong>, a new tender matching your sector has been published.</p>

      <!-- Tender Card -->
      <div style="background:rgba(6,182,212,0.06);border:1px solid rgba(6,182,212,0.2);border-radius:12px;padding:24px;margin-bottom:28px;">
        <p style="margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#06b6d4;">Tender Reference</p>
        <p style="margin:0 0 16px;font-size:13px;font-weight:700;color:#06b6d4;">#{tender_no}</p>

        <p style="margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#6b7280;">Tender Title</p>
        <p style="margin:0 0 16px;font-size:18px;font-weight:700;color:#f9fafb;">{tender_title}</p>

        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding-right:16px;">
              <p style="margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#6b7280;">Department</p>
              <p style="margin:0;font-size:14px;color:#d1d5db;">{department}</p>
            </td>
            <td>
              <p style="margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#6b7280;">Budget</p>
              <p style="margin:0;font-size:14px;font-weight:700;color:#00ff9d;">${budget:,.0f}</p>
            </td>
          </tr>
          <tr><td colspan="2" style="padding-top:16px;">
            <p style="margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#6b7280;">Bid Submission Deadline</p>
            <p style="margin:0;font-size:14px;font-weight:600;color:#f59e0b;">{deadline}</p>
          </td></tr>
        </table>
      </div>

      <p style="margin:0 0 24px;font-size:14px;color:#9ca3af;">Log in to the GovTender portal to review the full specifications and submit your bid before the closing date.</p>

      <div style="text-align:center;">
        <a href="http://localhost:8080" style="display:inline-block;background:linear-gradient(135deg,#06b6d4,#3b82f6);color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:700;font-size:15px;">View Tender &rarr;</a>
      </div>
    """
    send_email(to_email, subject, body, preheader)


def email_deadline_reminder(
    to_email: str,
    recipient_name: str,
    tender_title: str,
    tender_no: str,
    deadline: str,
    days_left: int,
):
    subject = f"⚠️ Bid Deadline Approaching — {tender_no} ({days_left} days left)"
    preheader = f"You have {days_left} days left to submit your bid for {tender_no}."
    urgency_color = "#ef4444" if days_left <= 3 else "#f59e0b"
    body = f"""
      <h1 style="margin:0 0 8px;font-size:26px;font-weight:700;color:#f9fafb;">Deadline Reminder ⚠️</h1>
      <p style="margin:0 0 28px;font-size:15px;color:#9ca3af;">Hello <strong style="color:#f9fafb;">{recipient_name}</strong>, the submission deadline is approaching.</p>

      <div style="background:rgba(239,68,68,0.08);border:1px solid {urgency_color};border-radius:12px;padding:24px;margin-bottom:28px;text-align:center;">
        <p style="margin:0 0 8px;font-size:48px;font-weight:900;color:{urgency_color};">{days_left}</p>
        <p style="margin:0 0 16px;font-size:14px;font-weight:600;color:{urgency_color};">DAYS REMAINING</p>
        <p style="margin:0 0 4px;font-size:13px;font-weight:700;color:#f9fafb;">{tender_title}</p>
        <p style="margin:0;font-size:12px;color:#9ca3af;">#{tender_no} · Closes: {deadline}</p>
      </div>

      <p style="margin:0 0 24px;font-size:14px;color:#9ca3af;">Ensure your technical and financial documents are uploaded before the deadline. Late submissions will not be accepted by the procurement system.</p>

      <div style="text-align:center;">
        <a href="http://localhost:8080" style="display:inline-block;background:{urgency_color};color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:700;font-size:15px;">Submit Bid Now &rarr;</a>
      </div>
    """
    send_email(to_email, subject, body, preheader)


def email_bid_status_update(
    to_email: str,
    recipient_name: str,
    tender_title: str,
    tender_no: str,
    new_status: str,
    admin_name: Optional[str] = None,
):
    status_map = {
        "approved": ("🎉 Bid Approved!", "#00ff9d", "rgba(0,255,157,0.08)", "Congratulations! Your bid has been approved by the Ministry."),
        "rejected": ("❌ Bid Rejected", "#ef4444", "rgba(239,68,68,0.08)", "Unfortunately, your bid was not selected for this tender."),
        "review":   ("🔍 Clarification Required", "#f59e0b", "rgba(245,158,11,0.08)", "The admin has flagged your bid for review. Please check the portal for details."),
        "opened":   ("📂 Bid Unlocked", "#06b6d4", "rgba(6,182,212,0.08)", "Your encrypted bid has been unlocked by the procurement committee after tender closing."),
    }
    emoji_title, accent_color, bg_color, desc_text = status_map.get(
        new_status, ("📋 Bid Status Updated", "#9ca3af", "rgba(156,163,175,0.08)", "Your bid status has been updated.")
    )
    subject = f"{emoji_title} — Tender #{tender_no}"
    preheader = f"Your bid for '{tender_title}' status: {new_status.upper()}"
    body = f"""
      <h1 style="margin:0 0 8px;font-size:26px;font-weight:700;color:#f9fafb;">{emoji_title}</h1>
      <p style="margin:0 0 28px;font-size:15px;color:#9ca3af;">Hello <strong style="color:#f9fafb;">{recipient_name}</strong>,</p>

      <div style="background:{bg_color};border:1px solid {accent_color};border-radius:12px;padding:24px;margin-bottom:28px;">
        <p style="margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:{accent_color};">Status Update</p>
        <p style="margin:0 0 4px;font-size:22px;font-weight:800;color:{accent_color};">{new_status.upper()}</p>
        <p style="margin:0 0 20px;font-size:12px;color:#9ca3af;">#{tender_no}</p>
        <p style="margin:0 0 4px;font-size:13px;font-weight:700;color:#f9fafb;">{tender_title}</p>
        <p style="margin:0;font-size:13px;color:#9ca3af;">{desc_text}</p>
        {f'<p style="margin:12px 0 0;font-size:12px;color:#6b7280;">Reviewed by: {admin_name}</p>' if admin_name else ''}
      </div>

      <div style="text-align:center;">
        <a href="http://localhost:8080" style="display:inline-block;background:{accent_color};color:#030712;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:700;font-size:15px;">View Portal &rarr;</a>
      </div>
    """
    send_email(to_email, subject, body, preheader)
