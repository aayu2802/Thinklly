"""
Notification Email Helper
Sends notification emails to teachers and students via SMTP (cPanel compatible).

Configuration via environment variables:
- MAIL_SERVER: SMTP host (e.g., mail.yourdomain.com)
- MAIL_PORT: SMTP port (default: 587 for TLS)
- MAIL_USERNAME: SMTP username (e.g., notifications@yourdomain.com)
- MAIL_PASSWORD: SMTP password
- MAIL_USE_TLS: Use STARTTLS (default: True)
- MAIL_USE_SSL: Use SSL (default: False, use for port 465)
- MAIL_SENDER_NAME: Display name for sender (default: School Notifications)
- MAIL_DEBUG: Enable debug logging (default: False)
"""

import os
import smtplib
import socket
import logging
from email.message import EmailMessage
from email.utils import formataddr
from typing import List, Tuple, Optional
from threading import Thread
from time import sleep
from datetime import datetime

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Prefer using application-level logging configuration.
# Do NOT attach handlers at module import time; callers (e.g. app entry)
# should configure logging handlers. Keep a module logger only.
logger = logging.getLogger(__name__)


def get_smtp_config():
    """Get SMTP configuration from environment (reload each time for testing)."""
    return {
        'host': os.getenv('MAIL_SERVER', 'localhost'),
        'port': int(os.getenv('MAIL_PORT', 587)),
        'user': os.getenv('MAIL_USERNAME', ''),
        'password': os.getenv('MAIL_PASSWORD', ''),
        'use_tls': os.getenv('MAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes'),
        'use_ssl': os.getenv('MAIL_USE_SSL', 'False').lower() in ('true', '1', 'yes'),
        'sender_name': os.getenv('MAIL_SENDER_NAME', 'School Notifications'),
        # By default keep SMTP debug OFF to avoid printing raw SMTP/MIME to stdout
        'debug': os.getenv('MAIL_DEBUG', 'False').lower() in ('true', '1', 'yes'),
    }


# Legacy module-level variables (for backward compatibility)
SMTP_HOST = os.getenv('MAIL_SERVER', 'localhost')
SMTP_PORT = int(os.getenv('MAIL_PORT', 587))
SMTP_USER = os.getenv('MAIL_USERNAME', '')
SMTP_PASS = os.getenv('MAIL_PASSWORD', '')
USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
USE_SSL = os.getenv('MAIL_USE_SSL', 'False').lower() in ('true', '1', 'yes')
SENDER_NAME = os.getenv('MAIL_SENDER_NAME', 'School Notifications')
DEBUG_MODE = os.getenv('MAIL_DEBUG', 'False').lower() in ('true', '1', 'yes')


def log_config():
    """Log current email configuration (for debugging)."""
    cfg = get_smtp_config()
    msg = f"""
============================================================
EMAIL CONFIGURATION:
  MAIL_SERVER: {cfg['host']}
  MAIL_PORT: {cfg['port']}
  MAIL_USERNAME: {cfg['user'][:3] + '***' if cfg['user'] else '(not set)'}
  MAIL_PASSWORD: {'*' * 8 if cfg['password'] else '(not set)'}
  MAIL_USE_TLS: {cfg['use_tls']}
  MAIL_USE_SSL: {cfg['use_ssl']}
  MAIL_SENDER_NAME: {cfg['sender_name']}
  Is Configured: {is_email_configured()}
============================================================"""
    print(msg)  # Print to ensure visibility
    logger.info(msg)


def is_email_configured() -> bool:
    """Check if email sending is properly configured."""
    cfg = get_smtp_config()
    configured = bool(cfg['host'] and cfg['host'] != 'localhost' and cfg['user'] and cfg['password'])
    if not configured:
        print("[EMAIL WARNING] Email is NOT configured properly!")
        print(f"  - MAIL_SERVER set: {bool(cfg['host'] and cfg['host'] != 'localhost')}")
        print(f"  - MAIL_USERNAME set: {bool(cfg['user'])}")
        print(f"  - MAIL_PASSWORD set: {bool(cfg['password'])}")
    return configured


def send_otp_email(to_email: str, otp: str, teacher_name: str = "Teacher", school_name: str = "School") -> Tuple[bool, str]:
    """
    Send OTP email for password reset.
    
    Args:
        to_email: Recipient email address
        otp: 6-digit OTP code
        teacher_name: Name of the teacher
        school_name: Name of the school
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    subject = f"Password Reset OTP - {school_name}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f4f4f4; }}
            .container {{ max-width: 600px; margin: 20px auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ padding: 30px; }}
            .otp-box {{ background: #f8f9fa; border: 2px dashed #667eea; border-radius: 10px; padding: 20px; text-align: center; margin: 20px 0; }}
            .otp-code {{ font-size: 36px; font-weight: bold; color: #667eea; letter-spacing: 8px; margin: 10px 0; }}
            .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Password Reset Request</h1>
            </div>
            <div class="content">
                <p>Dear <strong>{teacher_name}</strong>,</p>
                <p>We received a request to reset your password for the Teacher Portal at <strong>{school_name}</strong>.</p>
                
                <div class="otp-box">
                    <p style="margin: 0; color: #666;">Your One-Time Password (OTP) is:</p>
                    <div class="otp-code">{otp}</div>
                    <p style="margin: 0; color: #999; font-size: 14px;">Valid for 10 minutes</p>
                </div>
                
                <div class="warning">
                    <strong>⚠️ Security Notice:</strong>
                    <ul style="margin: 10px 0 0 0; padding-left: 20px;">
                        <li>Never share this OTP with anyone</li>
                        <li>Our staff will never ask for your OTP</li>
                        <li>If you didn't request this, please ignore this email</li>
                    </ul>
                </div>
                
                <p>If you did not request a password reset, please ignore this email or contact your school administrator if you have concerns.</p>
            </div>
            <div class="footer">
                This is an automated message from {school_name} Teacher Portal.<br>
                Please do not reply to this email.
            </div>
        </div>
    </body>
    </html>
    """
    
    plain_body = f"""
Password Reset Request - {school_name}

Dear {teacher_name},

We received a request to reset your password for the Teacher Portal.

Your One-Time Password (OTP) is: {otp}

This OTP is valid for 10 minutes.

SECURITY NOTICE:
- Never share this OTP with anyone
- Our staff will never ask for your OTP
- If you didn't request this, please ignore this email

If you did not request a password reset, please ignore this email.

---
This is an automated message from {school_name} Teacher Portal.
"""
    
    return send_email(
        to_addrs=[to_email],
        subject=subject,
        html_body=html_body,
        plain_body=plain_body
    )


def send_student_otp_email(to_email: str, otp: str, student_name: str = "Student", school_name: str = "School") -> Tuple[bool, str]:
    """
    Send OTP email for student password reset.
    
    Args:
        to_email: Recipient email address
        otp: 6-digit OTP code
        student_name: Name of the student
        school_name: Name of the school
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    subject = f"Password Reset OTP - {school_name}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f4f4f4; }}
            .container {{ max-width: 600px; margin: 20px auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ padding: 30px; }}
            .otp-box {{ background: #f8f9fa; border: 2px dashed #667eea; border-radius: 10px; padding: 20px; text-align: center; margin: 20px 0; }}
            .otp-code {{ font-size: 36px; font-weight: bold; color: #667eea; letter-spacing: 8px; margin: 10px 0; }}
            .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Student Password Reset</h1>
            </div>
            <div class="content">
                <p>Dear Parent/Guardian of <strong>{student_name}</strong>,</p>
                <p>We received a request to reset the student portal password at <strong>{school_name}</strong>.</p>
                
                <div class="otp-box">
                    <p style="margin: 0; color: #666;">Your One-Time Password (OTP) is:</p>
                    <div class="otp-code">{otp}</div>
                    <p style="margin: 0; color: #999; font-size: 14px;">Valid for 10 minutes</p>
                </div>
                
                <div class="warning">
                    <strong>⚠️ Security Notice:</strong>
                    <ul style="margin: 10px 0 0 0; padding-left: 20px;">
                        <li>Never share this OTP with anyone outside your family</li>
                        <li>School staff will never ask for your OTP</li>
                        <li>If you or your child didn't request this, please ignore this email</li>
                    </ul>
                </div>
                
                <p>If you did not request a password reset, please ignore this email or contact your school administrator if you have concerns.</p>
            </div>
            <div class="footer">
                This is an automated message from {school_name} Student Portal.<br>
                Please do not reply to this email.
            </div>
        </div>
    </body>
    </html>
    """
    
    plain_body = f"""
Student Password Reset Request - {school_name}

Dear Parent/Guardian of {student_name},

We received a request to reset the student portal password.

Your One-Time Password (OTP) is: {otp}

This OTP is valid for 10 minutes.

SECURITY NOTICE:
- Never share this OTP with anyone outside your family
- School staff will never ask for your OTP
- If you or your child didn't request this, please ignore this email

If you did not request a password reset, please ignore this email.

---
This is an automated message from {school_name} Student Portal.
"""
    
    return send_email(
        to_addrs=[to_email],
        subject=subject,
        html_body=html_body,
        plain_body=plain_body
    )


def send_admin_otp_email(to_email: str, otp: str, admin_name: str = "Admin", school_name: str = "School") -> Tuple[bool, str]:
    """
    Send OTP email for school admin password reset.
    
    Args:
        to_email: Recipient email address
        otp: 6-digit OTP code
        admin_name: Name of the admin
        school_name: Name of the school
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    subject = f"Password Reset OTP - {school_name} Admin Portal"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f4f4f4; }}
            .container {{ max-width: 600px; margin: 20px auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 30px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ padding: 30px; }}
            .otp-box {{ background: #f8f9fa; border: 2px dashed #1a1a2e; border-radius: 10px; padding: 20px; text-align: center; margin: 20px 0; }}
            .otp-code {{ font-size: 36px; font-weight: bold; color: #1a1a2e; letter-spacing: 8px; margin: 10px 0; }}
            .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Admin Password Reset</h1>
            </div>
            <div class="content">
                <p>Dear <strong>{admin_name}</strong>,</p>
                <p>We received a request to reset your password for the School Admin Portal at <strong>{school_name}</strong>.</p>
                
                <div class="otp-box">
                    <p style="margin: 0; color: #666;">Your One-Time Password (OTP) is:</p>
                    <div class="otp-code">{otp}</div>
                    <p style="margin: 0; color: #999; font-size: 14px;">Valid for 10 minutes</p>
                </div>
                
                <div class="warning">
                    <strong>⚠️ Security Notice:</strong>
                    <ul style="margin: 10px 0 0 0; padding-left: 20px;">
                        <li>Never share this OTP with anyone</li>
                        <li>Our staff will never ask for your OTP</li>
                        <li>If you didn't request this, please ignore this email</li>
                    </ul>
                </div>
                
                <p>If you did not request a password reset, please ignore this email or contact your system administrator if you have concerns.</p>
            </div>
            <div class="footer">
                This is an automated message from {school_name} Admin Portal.<br>
                Please do not reply to this email.
            </div>
        </div>
    </body>
    </html>
    """
    
    plain_body = f"""
Admin Password Reset Request - {school_name}

Dear {admin_name},

We received a request to reset your password for the School Admin Portal.

Your One-Time Password (OTP) is: {otp}

This OTP is valid for 10 minutes.

SECURITY NOTICE:
- Never share this OTP with anyone
- Our staff will never ask for your OTP
- If you didn't request this, please ignore this email

If you did not request a password reset, please ignore this email.

---
This is an automated message from {school_name} Admin Portal.
"""
    
    return send_email(
        to_addrs=[to_email],
        subject=subject,
        html_body=html_body,
        plain_body=plain_body
    )


def send_email(
    to_addrs: List[str],
    subject: str,
    html_body: str,
    plain_body: Optional[str] = None,
    attachments: Optional[List[Tuple[str, str, str]]] = None,
    reply_to: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Send an email to one or more recipients.
    
    Args:
        to_addrs: List of recipient email addresses
        subject: Email subject
        html_body: HTML content of the email
        plain_body: Plain text fallback (optional)
        attachments: List of tuples (file_path, filename, mimetype)
        reply_to: Reply-to address (optional)
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    # Reload config each time
    cfg = get_smtp_config()
    
    start_time = datetime.now()
    print("=" * 60)
    print(f"[EMAIL] SENDING EMAIL - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[EMAIL]   Subject: {subject[:80]}...")
    print(f"[EMAIL]   Recipients: {to_addrs}")
    
    # Log configuration on first send
    if cfg['debug']:
        log_config()
    
    if not is_email_configured():
        msg = "Email not configured. Set MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD environment variables."
        print(f"[EMAIL] [FAIL] FAILED: {msg}")
        return False, msg
    
    if not to_addrs:
        msg = "No recipients specified"
        print(f"[EMAIL] [FAIL] FAILED: {msg}")
        return False, msg
    
    # Filter out empty/None addresses
    original_count = len(to_addrs)
    to_addrs = [addr for addr in to_addrs if addr and '@' in addr]
    if original_count != len(to_addrs):
        print(f"[EMAIL] Filtered out {original_count - len(to_addrs)} invalid addresses")
    
    if not to_addrs:
        msg = "No valid email addresses provided"
        print(f"[EMAIL] [FAIL] FAILED: {msg}")
        return False, msg
    
    print(f"[EMAIL]   Valid recipients: {len(to_addrs)}")
    
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = formataddr((cfg['sender_name'], cfg['user']))
        msg['To'] = ', '.join(to_addrs)
        
        # Add headers to improve deliverability and avoid spam filters
        msg['Message-ID'] = f"<{datetime.now().strftime('%Y%m%d%H%M%S')}.{os.getpid()}@edusaint.in>"
        msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0530')
        msg['X-Mailer'] = 'EduSaint School Management System'
        msg['List-Unsubscribe'] = f'<mailto:{cfg["user"]}?subject=Unsubscribe>'
        
        if reply_to:
            msg['Reply-To'] = reply_to
        else:
            msg['Reply-To'] = cfg['user']  # Always set Reply-To
        
        # Set content
        if plain_body:
            msg.set_content(plain_body)
            msg.add_alternative(html_body, subtype='html')
        else:
            msg.set_content('Please view this email in an HTML-compatible email client.')
            msg.add_alternative(html_body, subtype='html')
        
        # Add attachments
        if attachments:
            print(f"[EMAIL]   Attachments: {len(attachments)} files")
            for file_path, filename, mimetype in attachments:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        data = f.read()
                    if mimetype and '/' in mimetype:
                        maintype, subtype = mimetype.split('/', 1)
                    else:
                        maintype, subtype = 'application', 'octet-stream'
                    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
                    print(f"[EMAIL]     [OK] Attached: {filename}")
                else:
                    print(f"[EMAIL]     [FAIL] Attachment file not found: {file_path}", flush=True)
        
        # Send email
        print(f"[EMAIL]   Connecting to SMTP: {cfg['host']}:{cfg['port']} (TLS={cfg['use_tls']}, SSL={cfg['use_ssl']})", flush=True)
        
        if cfg['use_ssl']:
            print("[EMAIL]   Attempting SSL connection...", flush=True)
            with smtplib.SMTP_SSL(cfg['host'], cfg['port'], timeout=30) as server:
                if cfg['debug']:
                    server.set_debuglevel(2)
                print("[EMAIL]   Connected with SSL", flush=True)
                if cfg['user'] and cfg['password']:
                    print(f"[EMAIL]   Logging in as {cfg['user']}...", flush=True)
                    server.login(cfg['user'], cfg['password'])
                    print("[EMAIL]   Logged in successfully", flush=True)
                print("[EMAIL]   Sending message...", flush=True)
                server.send_message(msg)
                print("[EMAIL]   Message sent!", flush=True)
        else:
            print("[EMAIL]   Attempting TLS connection...", flush=True)
            with smtplib.SMTP(cfg['host'], cfg['port'], timeout=30) as server:
                if cfg['debug']:
                    server.set_debuglevel(2)
                print("[EMAIL]   Connected to SMTP server", flush=True)
                if cfg['use_tls']:
                    server.starttls()
                    print("[EMAIL]   STARTTLS initiated", flush=True)
                if cfg['user'] and cfg['password']:
                    print(f"[EMAIL]   Logging in as {cfg['user']}...", flush=True)
                    server.login(cfg['user'], cfg['password'])
                    print("[EMAIL]   Logged in successfully", flush=True)
                print("[EMAIL]   Sending message...", flush=True)
                server.send_message(msg)
                print("[EMAIL]   Message sent!", flush=True)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        success_msg = f"Email sent to {len(to_addrs)} recipient(s) in {elapsed:.2f}s"
        print(f"[EMAIL] [OK] SUCCESS: {success_msg}", flush=True)
        print("=" * 60, flush=True)
        return True, success_msg
    
    except smtplib.SMTPAuthenticationError as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        error_msg = f"SMTP authentication failed: {str(e)}"
        print(f"[EMAIL] [FAIL] FAILED ({elapsed:.2f}s): {error_msg}", flush=True)
        print(f"[EMAIL]   Check your MAIL_USERNAME and MAIL_PASSWORD", flush=True)
        print("=" * 60, flush=True)
        return False, error_msg
    except smtplib.SMTPConnectError as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        error_msg = f"Could not connect to SMTP server: {str(e)}"
        print(f"[EMAIL] [FAIL] FAILED ({elapsed:.2f}s): {error_msg}", flush=True)
        print(f"[EMAIL]   Check MAIL_SERVER ({cfg['host']}) and MAIL_PORT ({cfg['port']})", flush=True)
        print("=" * 60, flush=True)
        return False, error_msg
    except smtplib.SMTPException as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        error_msg = f"SMTP error: {str(e)}"
        print(f"[EMAIL] [FAIL] FAILED ({elapsed:.2f}s): {error_msg}", flush=True)
        print("=" * 60, flush=True)
        return False, error_msg
    except socket.timeout as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        error_msg = f"Connection timed out after 30 seconds: {str(e)}"
        print(f"[EMAIL] [FAIL] TIMEOUT ({elapsed:.2f}s): {error_msg}", flush=True)
        print(f"[EMAIL]   Server {cfg['host']}:{cfg['port']} may be unreachable or firewalled", flush=True)
        print("=" * 60, flush=True)
        return False, error_msg
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        error_msg = f"Error sending email: {str(e)}"
        print(f"[EMAIL] [FAIL] FAILED ({elapsed:.2f}s): {error_msg}", flush=True)
        import traceback
        print(f"[EMAIL] Full traceback:\n{traceback.format_exc()}", flush=True)
        print("=" * 60, flush=True)
        return False, error_msg


def send_bulk_emails(
    messages: List[dict],
    batch_size: int = 20,
    pause_seconds: float = 1.0
) -> Tuple[int, int, List[str]]:
    """
    Send multiple emails in batches.
    
    Args:
        messages: List of dicts with keys: to_addrs, subject, html_body, plain_body, attachments
        batch_size: Number of emails per batch (default: 20)
        pause_seconds: Pause between batches (default: 1.0)
    
    Returns:
        Tuple of (sent_count, failed_count, error_messages)
    """
    sent = 0
    failed = 0
    errors = []
    
    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        
        for m in batch:
            success, msg = send_email(
                to_addrs=m.get('to_addrs', []),
                subject=m.get('subject', 'Notification'),
                html_body=m.get('html_body', ''),
                plain_body=m.get('plain_body'),
                attachments=m.get('attachments')
            )
            if success:
                sent += 1
            else:
                failed += 1
                errors.append(msg)
        
        # Pause between batches to avoid rate limiting
        if i + batch_size < len(messages):
            sleep(pause_seconds)
    
    return sent, failed, errors


def send_notification_emails(
    notification,
    recipients_with_emails: List[Tuple[str, str]],  # List of (name, email)
    base_url: str = ''
) -> Tuple[int, int]:
    """
    Send notification as emails to recipients.
    
    Args:
        notification: Notification dict or object with title, message, documents, priority
        recipients_with_emails: List of (recipient_name, email) tuples
        base_url: Base URL for attachment links (optional)
    
    Returns:
        Tuple of (sent_count, failed_count)
    """
    # Support both dict and object access
    def get_attr(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)
    
    notif_id = get_attr(notification, 'id', 'unknown')
    notif_title = get_attr(notification, 'title', 'Notification')
    notif_message = get_attr(notification, 'message', '')
    notif_priority = get_attr(notification, 'priority', 'Normal')
    notif_documents = get_attr(notification, 'documents', [])
    
    print(f"[EMAIL] ============================================================", flush=True)
    print(f"[EMAIL] SEND NOTIFICATION AS EMAIL - ID: {notif_id}", flush=True)
    print(f"[EMAIL]   Title: {notif_title}", flush=True)
    print(f"[EMAIL]   Recipients provided: {len(recipients_with_emails)}", flush=True)
    
    if not recipients_with_emails:
        print("[EMAIL]   No recipients provided - skipping email send", flush=True)
        return 0, 0
    
    # Log all recipients for debugging
    for name, email in recipients_with_emails:
        logger.debug(f"    - {name}: {email}")
    
    # Build email content
    priority_colors = {
        'Low': '#6c757d',
        'Normal': '#17a2b8',
        'High': '#fd7e14',
        'Urgent': '#dc3545'
    }
    
    # Handle priority - could be enum value or string
    if hasattr(notif_priority, 'value'):
        priority_value = notif_priority.value
    else:
        priority_value = str(notif_priority)
    priority_color = priority_colors.get(priority_value, '#17a2b8')
    print(f"[EMAIL]   Priority: {priority_value}", flush=True)
    
    # Build HTML email
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #667eea; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .priority-badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; background: {priority_color}; color: white; margin-top: 10px; }}
            .content {{ background: #ffffff; padding: 20px; border: 1px solid #e0e0e0; border-top: none; }}
            .message {{ white-space: pre-wrap; margin-bottom: 20px; }}
            .attachments {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin-top: 20px; }}
            .attachments h3 {{ margin-top: 0; color: #555; font-size: 14px; }}
            .attachment-item {{ padding: 8px 0; border-bottom: 1px solid #e0e0e0; }}
            .attachment-item:last-child {{ border-bottom: none; }}
            .footer {{ background: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #666; border-radius: 0 0 8px 8px; border: 1px solid #e0e0e0; border-top: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{notif_title}</h1>
                <span class="priority-badge">{priority_value} Priority</span>
            </div>
            <div class="content">
                <div class="message">{notif_message}</div>
    """
    
    # Add attachments info
    if notif_documents and len(notif_documents) > 0:
        html_body += """
                <div class="attachments">
                    <h3>📎 Attachments</h3>
        """
        for doc in notif_documents:
            # Support both dict and object access for documents
            doc_name = doc.get('file_name') if isinstance(doc, dict) else getattr(doc, 'file_name', 'file')
            doc_size = doc.get('file_size_kb', 0) if isinstance(doc, dict) else getattr(doc, 'file_size_kb', 0)
            html_body += f"""
                    <div class="attachment-item">
                        📄 {doc_name} ({doc_size or 0} KB)
                    </div>
            """
        html_body += """
                </div>
        """
    
    html_body += f"""
            </div>
            <div class="footer">
                This is an automated notification from the School Management System.<br>
                Please do not reply to this email.
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text version
    plain_body = f"""
{notif_title}
{'=' * len(notif_title)}

Priority: {priority_value}

{notif_message}
"""
    
    if notif_documents and len(notif_documents) > 0:
        plain_body += "\nAttachments:\n"
        for doc in notif_documents:
            doc_name = doc.get('file_name') if isinstance(doc, dict) else getattr(doc, 'file_name', 'file')
            plain_body += f"- {doc_name}\n"
    
    plain_body += "\n---\nThis is an automated notification from the School Management System."
    
    # Prepare attachments
    attachments = []
    if notif_documents:
        print(f"[EMAIL]   Documents to attach: {len(notif_documents)}", flush=True)
        for doc in notif_documents:
            doc_path = doc.get('file_path') if isinstance(doc, dict) else getattr(doc, 'file_path', '')
            doc_name = doc.get('file_name') if isinstance(doc, dict) else getattr(doc, 'file_name', 'file')
            doc_mime = doc.get('mime_type') if isinstance(doc, dict) else getattr(doc, 'mime_type', None)
            file_path = os.path.join('akademi', 'static', doc_path)
            if os.path.exists(file_path):
                attachments.append((file_path, doc_name, doc_mime or 'application/octet-stream'))
                print(f"[EMAIL]     [OK] Will attach: {doc_name}", flush=True)
            else:
                print(f"[EMAIL]     [FAIL] File not found: {file_path}", flush=True)
    
    # Collect valid emails
    valid_emails = [email for name, email in recipients_with_emails if email and '@' in email]
    invalid_count = len(recipients_with_emails) - len(valid_emails)
    
    print(f"[EMAIL]   Valid emails: {len(valid_emails)}")
    if invalid_count > 0:
        print(f"[EMAIL]   Invalid/missing emails: {invalid_count}")
    
    if not valid_emails:
        print("[EMAIL]   No valid email addresses found for notification - aborting")
        return 0, 0
    
    # Log the emails we're sending to
    print(f"[EMAIL]   Sending to: {valid_emails}")
    
    # Send email - avoid spam trigger words in subject
    # Don't use [High], [Urgent] etc. as they trigger spam filters
    subject = notif_title  # Clean subject without priority tags
    
    success, msg = send_email(
        to_addrs=valid_emails,
        subject=subject,
        html_body=html_body,
        plain_body=plain_body,
        attachments=attachments if attachments else None
    )
    
    if success:
        print(f"[EMAIL] [OK] Notification emails sent successfully to {len(valid_emails)} recipient(s)")
        return len(valid_emails), 0
    else:
        print(f"[EMAIL] [FAIL] Failed to send notification emails: {msg}")
        return 0, len(valid_emails)


def send_notification_emails_async(notification, recipients_with_emails: List[Tuple[str, str]], base_url: str = ''):
    """
    Send notification emails in a background thread.
    """
    # Support both dict and object access
    notif_id = notification.get('id') if isinstance(notification, dict) else getattr(notification, 'id', 'unknown')
    
    print(f"[EMAIL] Starting async email send for notification {notif_id}", flush=True)
    print(f"[EMAIL]   Recipients: {len(recipients_with_emails)}", flush=True)
    
    def _send():
        try:
            print(f"[EMAIL ASYNC THREAD] Starting email send for notification {notif_id}", flush=True)
            sent, failed = send_notification_emails(notification, recipients_with_emails, base_url)
            print(f"[EMAIL ASYNC THREAD] Complete: {sent} sent, {failed} failed for notification {notif_id}", flush=True)
        except Exception as e:
            print(f"[EMAIL ASYNC THREAD] Error for notification {notif_id}: {e}", flush=True)
            import traceback
            print(f"[EMAIL ASYNC THREAD] Full traceback:\n{traceback.format_exc()}", flush=True)
    
    thread = Thread(target=_send, daemon=True)
    thread.start()
    print(f"[EMAIL]   Async thread started: {thread.name}", flush=True)
    return thread


# Test function to verify email setup
def test_email_config(test_recipient: str = None) -> dict:
    """
    Test the email configuration and optionally send a test email.
    
    Args:
        test_recipient: Email address to send test email to (optional)
    
    Returns:
        dict with test results
    """
    results = {
        'config_valid': False,
        'smtp_host': SMTP_HOST,
        'smtp_port': SMTP_PORT,
        'smtp_user': SMTP_USER[:3] + '***' if SMTP_USER else None,
        'use_tls': USE_TLS,
        'use_ssl': USE_SSL,
        'connection_test': None,
        'send_test': None
    }
    
    log_config()
    
    if not is_email_configured():
        results['error'] = 'Email not configured'
        return results
    
    results['config_valid'] = True
    
    # Test SMTP connection
    try:
        logger.info("Testing SMTP connection...")
        if USE_SSL:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.login(SMTP_USER, SMTP_PASS)
                results['connection_test'] = 'SUCCESS'
                logger.info("  [OK] SMTP connection successful (SSL)")
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                if USE_TLS:
                    server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                results['connection_test'] = 'SUCCESS'
                logger.info("  [OK] SMTP connection successful (TLS)")
    except Exception as e:
        results['connection_test'] = f'FAILED: {str(e)}'
        logger.error(f"  [FAIL] SMTP connection failed: {e}")
        return results
    
    # Send test email if recipient provided
    if test_recipient:
        logger.info(f"Sending test email to {test_recipient}...")
        success, msg = send_email(
            to_addrs=[test_recipient],
            subject='Test Email from School ERP',
            html_body='<h1>Test Email</h1><p>This is a test email from the School ERP notification system.</p><p>If you received this, email sending is working correctly!</p>',
            plain_body='Test Email\n\nThis is a test email from the School ERP notification system.\nIf you received this, email sending is working correctly!'
        )
        results['send_test'] = 'SUCCESS' if success else f'FAILED: {msg}'
    
    return results
