"""
GovTender Notification Service
Central dispatcher: creates an in-app DB notification AND sends an email alert.
Call these functions from any router using FastAPI BackgroundTasks.
"""
import uuid
import datetime
from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.models.user import User
from typing import Optional


def _store_notification(db: Session, owner_email: str, title: str, desc: str):
    """Persist an in-app notification to the database."""
    notif = Notification(
        id=uuid.uuid4(),
        title=title,
        desc=desc,
        time="Just now",
        unread=True,
        owner_email=owner_email,
    )
    db.add(notif)
    db.commit()


# ─── PUBLIC DISPATCHER FUNCTIONS ─────────────────────────────────────────────

def notify_new_tender(
    db: Session,
    tender_title: str,
    tender_no: str,
    department: str,
    budget: float,
    deadline: str,
    category: str,
):
    """
    Notify ALL active vendor users about a newly published tender.
    Called from the tender approval endpoint via BackgroundTasks.
    """
    from app.services.email_service import email_new_tender

    vendors = db.query(User).filter(User.role == "Vendor").all()
    for vendor in vendors:
        # In-app notification
        _store_notification(
            db,
            owner_email=vendor.email,
            title=f"New Tender: {tender_title}",
            desc=f"A new {category} tender #{tender_no} from {department} has been published. Budget: ${budget:,.0f}. Deadline: {deadline}.",
        )
        # Email
        email_new_tender(
            to_email=vendor.email,
            recipient_name=vendor.name,
            tender_title=tender_title,
            tender_no=tender_no,
            department=department,
            budget=budget,
            deadline=deadline,
            category=category,
        )


def notify_bid_status_change(
    db: Session,
    vendor_email: str,
    vendor_name: str,
    tender_title: str,
    tender_no: str,
    new_status: str,
    admin_name: Optional[str] = None,
):
    """
    Notify a specific vendor when their bid status changes.
    Called from the application PATCH endpoint via BackgroundTasks.
    """
    from app.services.email_service import email_bid_status_update

    status_label_map = {
        "approved": "Approved ✓",
        "rejected": "Rejected",
        "review": "Requires Clarification",
        "opened": "Bid Unlocked & Opened",
    }
    label = status_label_map.get(new_status, new_status.capitalize())

    # In-app notification
    _store_notification(
        db,
        owner_email=vendor_email,
        title=f"Bid {label}: #{tender_no}",
        desc=f"Your bid application for '{tender_title}' has been updated to status: {label}.",
    )
    # Email
    email_bid_status_update(
        to_email=vendor_email,
        recipient_name=vendor_name,
        tender_title=tender_title,
        tender_no=tender_no,
        new_status=new_status,
        admin_name=admin_name,
    )


def notify_deadline_approaching(
    db: Session,
    vendor_email: str,
    vendor_name: str,
    tender_title: str,
    tender_no: str,
    deadline_str: str,
    days_left: int,
):
    """
    Called by the scheduler when a tender deadline is N days away.
    """
    from app.services.email_service import email_deadline_reminder

    # In-app notification
    _store_notification(
        db,
        owner_email=vendor_email,
        title=f"⚠️ Deadline in {days_left} days: {tender_no}",
        desc=f"The submission deadline for '{tender_title}' is approaching — only {days_left} day(s) left. Deadline: {deadline_str}.",
    )
    # Email
    email_deadline_reminder(
        to_email=vendor_email,
        recipient_name=vendor_name,
        tender_title=tender_title,
        tender_no=tender_no,
        deadline=deadline_str,
        days_left=days_left,
    )
