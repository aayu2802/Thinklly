"""
Notification Scheduler
Handles sending scheduled notifications when their scheduled time arrives.

This module can be used in two ways:
1. As a CLI command: `flask send-scheduled-notifications` (for cron jobs)
2. As a background thread (for development or simple deployments)

For production, it's recommended to use a cron job or task queue like Celery.
"""

import logging
from datetime import datetime
from typing import Tuple, List

from db_single import get_session
from notification_models import (
    Notification, NotificationRecipient,
    NotificationStatusEnum, RecipientStatusEnum
)

logger = logging.getLogger(__name__)


def send_scheduled_notification(notification_id: int) -> Tuple[bool, str, int]:
    """
    Send a single scheduled notification.
    
    Args:
        notification_id: The ID of the notification to send
        
    Returns:
        Tuple of (success, message, recipients_count)
    """
    session = get_session()
    try:
        notification = session.query(Notification).filter(
            Notification.id == notification_id,
            Notification.status == NotificationStatusEnum.SCHEDULED
        ).first()
        
        if not notification:
            return False, f"Notification {notification_id} not found or not in scheduled status", 0
        
        # Update notification status to SENT
        notification.status = NotificationStatusEnum.SENT
        notification.sent_at = datetime.now()
        
        # Update all pending recipients to SENT
        recipients_updated = session.query(NotificationRecipient).filter(
            NotificationRecipient.notification_id == notification_id,
            NotificationRecipient.status == RecipientStatusEnum.PENDING
        ).update({
            'status': RecipientStatusEnum.SENT,
            'sent_at': datetime.now()
        }, synchronize_session=False)
        
        session.commit()
        
        # Send emails if enabled
        if notification.send_as_email:
            try:
                from notification_email import send_notification_emails_async
                from models import Student
                from teacher_models import Teacher
                
                # Reload notification with relationships
                notification = session.query(Notification).filter_by(id=notification_id).first()
                
                # Collect recipient emails
                recipients_with_emails = []
                for r in notification.recipients:
                    if r.student_id:
                        student = session.query(Student).filter_by(id=r.student_id).first()
                        if student and student.email:
                            recipients_with_emails.append((student.full_name, student.email))
                    elif r.teacher_id:
                        teacher = session.query(Teacher).filter_by(id=r.teacher_id).first()
                        if teacher and teacher.email:
                            recipients_with_emails.append((teacher.full_name, teacher.email))
                
                if recipients_with_emails:
                    send_notification_emails_async(notification, recipients_with_emails)
                    notification.email_sent_at = datetime.now()
                    session.commit()
                    logger.info(f"Queued {len(recipients_with_emails)} emails for notification {notification_id}")
            except Exception as email_error:
                logger.error(f"Error sending notification emails for {notification_id}: {email_error}")
        
        logger.info(f"Sent notification {notification_id} to {recipients_updated} recipients")
        return True, f"Notification sent successfully", recipients_updated
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error sending notification {notification_id}: {e}")
        return False, str(e), 0
    finally:
        session.close()


def process_scheduled_notifications() -> Tuple[int, int, List[str]]:
    """
    Find and send all notifications that are scheduled for now or in the past.
    
    Returns:
        Tuple of (notifications_processed, total_recipients, list_of_errors)
    """
    session = get_session()
    errors = []
    notifications_processed = 0
    total_recipients = 0
    
    try:
        # Use local time since scheduled_at is stored as local time from user input
        now = datetime.now()
        
        # Find all scheduled notifications whose scheduled_at has passed
        scheduled_notifications = session.query(Notification).filter(
            Notification.status == NotificationStatusEnum.SCHEDULED,
            Notification.scheduled_at <= now,
            Notification.scheduled_at.isnot(None)
        ).all()
        
        logger.info(f"Found {len(scheduled_notifications)} scheduled notifications to process (checked at {now})")
        
        for notification in scheduled_notifications:
            success, message, recipients_count = send_scheduled_notification(notification.id)
            
            if success:
                notifications_processed += 1
                total_recipients += recipients_count
            else:
                errors.append(f"Notification {notification.id}: {message}")
        
        return notifications_processed, total_recipients, errors
        
    except Exception as e:
        logger.error(f"Error processing scheduled notifications: {e}")
        errors.append(str(e))
        return notifications_processed, total_recipients, errors
    finally:
        session.close()


def get_pending_scheduled_notifications() -> List[dict]:
    """
    Get list of pending scheduled notifications for display.
    
    Returns:
        List of notification dictionaries with id, title, scheduled_at, tenant_id
    """
    session = get_session()
    try:
        notifications = session.query(Notification).filter(
            Notification.status == NotificationStatusEnum.SCHEDULED,
            Notification.scheduled_at.isnot(None)
        ).order_by(Notification.scheduled_at).all()
        
        return [{
            'id': n.id,
            'title': n.title,
            'scheduled_at': n.scheduled_at.isoformat() if n.scheduled_at else None,
            'tenant_id': n.tenant_id,
            'recipient_count': len(n.recipients)
        } for n in notifications]
        
    finally:
        session.close()


# ===== BACKGROUND SCHEDULER (for development/simple deployments) =====

import threading
import time

_scheduler_thread = None
_scheduler_running = False


def start_background_scheduler(interval_seconds: int = 60):
    """
    Start a background thread that checks for scheduled notifications periodically.
    
    Args:
        interval_seconds: How often to check for scheduled notifications (default: 60)
    """
    global _scheduler_thread, _scheduler_running
    
    if _scheduler_running:
        logger.warning("Scheduler is already running")
        return
    
    _scheduler_running = True
    
    def scheduler_loop():
        global _scheduler_running
        logger.info(f"Notification scheduler started (checking every {interval_seconds}s)")
        
        while _scheduler_running:
            try:
                processed, recipients, errors = process_scheduled_notifications()
                
                if processed > 0:
                    logger.info(f"Scheduler: Sent {processed} notifications to {recipients} recipients")
                
                if errors:
                    for error in errors:
                        logger.error(f"Scheduler error: {error}")
                        
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
            
            # Sleep in small increments to allow graceful shutdown
            for _ in range(interval_seconds):
                if not _scheduler_running:
                    break
                time.sleep(1)
        
        logger.info("Notification scheduler stopped")
    
    _scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    _scheduler_thread.start()


def stop_background_scheduler():
    """Stop the background scheduler."""
    global _scheduler_running
    _scheduler_running = False
    logger.info("Stopping notification scheduler...")


def is_scheduler_running() -> bool:
    """Check if the background scheduler is running."""
    return _scheduler_running
