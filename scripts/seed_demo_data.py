#!/usr/bin/env python3
"""
scripts/seed_demo_data.py

=== DEMO / SEED DATA ===
Creates initial demo data for the student profile, progress records, and a reminder
so that the dashboard and frontend features are not empty on first load.

This data is explicitly for DEMO purposes and must NOT be used in evaluation or
experiments.
"""

import logging
from datetime import datetime, timedelta, timezone
from app.db.state.db import get_session, create_tables
from app.db.state.models import StudentProfile, PerformanceLog, Notification
from app.agents.progress import STRUGGLE_THRESHOLD, MASTERY_THRESHOLD, _evaluate_persistent_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STUDENT_ID = "demo_student"

def seed_demo_data(check_only: bool = False):
    create_tables()

    with get_session() as db:
        # 1. Profile
        profile = db.query(StudentProfile).filter_by(student_id=STUDENT_ID).first()
        if not profile:
            if check_only:
                logger.info("Profile not found.")
                return False
            profile = StudentProfile(student_id=STUDENT_ID, target_companies=[], skill_profile={})
            db.add(profile)
            db.commit()
            db.refresh(profile)

        # Update profile targets and time if empty
        if not profile.target_companies or len(profile.target_companies) == 0:
            if check_only: return False
            profile.target_companies = ["NovaTech", "Meridian Fintech"]
            profile.available_time = "10 hours per week"
            db.commit()

        # 2. Performance Logs (Demo data)
        logs_count = db.query(PerformanceLog).filter_by(student_id=STUDENT_ID).count()
        if logs_count == 0:
            if check_only: return False
            demo_scores = [
                ("DSA", 45),
                ("DSA", 72),
                ("DSA", 88),
                ("Aptitude", 65)
            ]
            
            # Insert with backdated timestamps to show history
            now = datetime.now(timezone.utc)
            for i, (topic, score) in enumerate(demo_scores):
                is_struggle = score < STRUGGLE_THRESHOLD
                is_mastery = score >= MASTERY_THRESHOLD
                signal = "struggle" if is_struggle else "mastery" if is_mastery else "neutral"
                
                log = PerformanceLog(
                    student_id=STUDENT_ID,
                    topic=topic,
                    score=score,
                    is_struggle=is_struggle,
                    is_mastery=is_mastery,
                    timestamp=now - timedelta(days=len(demo_scores)-i)
                )
                db.add(log)
                db.commit()
                
                persistent_status = _evaluate_persistent_status(db, STUDENT_ID, topic)
                if persistent_status:
                    prof = db.query(StudentProfile).filter_by(student_id=STUDENT_ID).first()
                    sp = prof.skill_profile or {}
                    sp = dict(sp)
                    sp[topic] = persistent_status
                    prof.skill_profile = sp
                    db.commit()

        # 3. Reminder (Demo data)
        reminders_count = db.query(Notification).filter_by(student_id=STUDENT_ID).count()
        if reminders_count == 0:
            if check_only: return False
            due = datetime.now(timezone.utc) + timedelta(days=1)
            n = Notification(
                student_id=STUDENT_ID,
                message="Revise DSA fundamentals",
                due_at=due,
                status="pending"
            )
            db.add(n)
            db.commit()

    logger.info("Demo data seeded successfully.")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Check if seed data exists without modifying")
    args = parser.parse_args()
    
    exists = seed_demo_data(check_only=args.check)
    if args.check:
        if exists:
            logger.info("Demo data already exists.")
        else:
            logger.info("Demo data is missing or incomplete.")
