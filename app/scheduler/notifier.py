import logging
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from app.db.state.db import get_session
from app.db.state.models import Notification

logger = logging.getLogger(__name__)

# Global scheduler singleton
scheduler = BackgroundScheduler()
_is_started = False

def start_scheduler():
    global _is_started
    if _is_started:
        return
    
    # Load all pending notifications from DB and schedule them
    with get_session() as db:
        pending_notifications = db.query(Notification).filter(Notification.status == "pending").all()
        
        now = datetime.now(timezone.utc)
        for n in pending_notifications:
            # SQLite may return naive datetimes even for DateTime(timezone=True)
            db_due_at = n.due_at.replace(tzinfo=timezone.utc) if n.due_at.tzinfo is None else n.due_at
            
            # If due_at is in the past, dispatch it immediately
            run_time = db_due_at if db_due_at > now else now
            job_id = f"notification_{n.id}"
            
            # Avoid duplicate jobs on reload if already in scheduler
            if not scheduler.get_job(job_id):
                scheduler.add_job(
                    dispatch_notification,
                    trigger=DateTrigger(run_date=run_time),
                    args=[n.id],
                    id=job_id
                )
                
    scheduler.start()
    _is_started = True
    logger.info("Local APScheduler started for notifications.")

def schedule_reminder(notification_id: int, due_at: datetime):
    job_id = f"notification_{notification_id}"
    
    if not _is_started:
        start_scheduler()
        
    if not scheduler.get_job(job_id):
        scheduler.add_job(
            dispatch_notification,
            trigger=DateTrigger(run_date=due_at),
            args=[notification_id],
            id=job_id
        )
        logger.info(f"Scheduled job {job_id} for {due_at}")

def dispatch_notification(notification_id: int):
    with get_session() as db:
        # Use with_for_update to avoid race conditions with duplicate dispatches
        n = db.query(Notification).filter_by(id=notification_id).with_for_update().first()
        if not n or n.status == "dispatched":
            return
            
        # The Local Sink
        logger.info(f"🔔 [NOTIFICATION SINK] To Student {n.student_id}: {n.message}")
        
        n.status = "dispatched"
        n.dispatched_at = datetime.now(timezone.utc)
        db.commit()
