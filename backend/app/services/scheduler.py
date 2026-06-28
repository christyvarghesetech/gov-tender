"""
GovTender Background Scheduler
Uses APScheduler to run deadline reminder checks every day at 08:00 UTC.
Starts automatically when the FastAPI app boots.
"""
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Deadline warning thresholds (days before deadline to send reminder)
REMINDER_DAYS = [7, 3, 1]

scheduler = BackgroundScheduler(timezone="UTC")


def check_deadline_reminders():
    """
    Scans all verified/open tenders, identifies those whose deadlines are
    REMINDER_DAYS away, and sends notifications to all vendors who have
    submitted a bid.
    """
    from app.database import SessionLocal
    from app.models.tender import Tender
    from app.models.bid import Bid
    from app.models.user import User
    from app.services.notification_service import notify_deadline_approaching

    db = SessionLocal()
    try:
        today = datetime.datetime.utcnow().date()
        open_tenders = db.query(Tender).filter(
            Tender.status.in_(["verified", "pending"]),
            Tender.date.isnot(None),
        ).all()

        for tender in open_tenders:
            deadline_date = tender.date.date() if isinstance(tender.date, datetime.datetime) else tender.date
            days_left = (deadline_date - today).days

            if days_left in REMINDER_DAYS:
                deadline_str = deadline_date.strftime("%B %d, %Y")
                print(f"[SCHEDULER] Tender {tender.tender_number} deadline in {days_left} days — notifying bidders.")

                # Notify every vendor who submitted a bid
                bids = db.query(Bid).filter(Bid.tender_id == tender.id).all()
                notified = set()
                for bid in bids:
                    vendor = db.query(User).filter(User.id == bid.vendor_id).first()
                    if vendor and vendor.email not in notified:
                        notified.add(vendor.email)
                        notify_deadline_approaching(
                            db=db,
                            vendor_email=vendor.email,
                            vendor_name=vendor.name,
                            tender_title=tender.title,
                            tender_no=tender.tender_number,
                            deadline_str=deadline_str,
                            days_left=days_left,
                        )
    except Exception as e:
        print(f"[SCHEDULER ERROR] Deadline check failed: {e}")
    finally:
        db.close()


def start_scheduler():
    """Boot the APScheduler background job. Called once on FastAPI startup."""
    if not scheduler.running:
        # Run every day at 08:00 UTC
        scheduler.add_job(
            check_deadline_reminders,
            trigger=CronTrigger(hour=8, minute=0),
            id="deadline_reminder",
            replace_existing=True,
        )
        scheduler.start()
        print("[SCHEDULER] Deadline reminder scheduler started (daily at 08:00 UTC).")


def stop_scheduler():
    """Gracefully stop the scheduler on FastAPI shutdown."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("[SCHEDULER] Scheduler stopped.")
