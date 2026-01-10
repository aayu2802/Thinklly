"""
Notification Management Routes
Routes for notification creation, management, templates, and sending
"""

from flask import request, jsonify, render_template, redirect, url_for, flash, g
from flask_login import current_user
from sqlalchemy import or_, desc, func
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import logging

from db_single import get_session
from notification_models import (
    Notification, NotificationTemplate, NotificationRecipient, NotificationDocument,
    NotificationStatusEnum, NotificationPriorityEnum, RecipientTypeEnum, RecipientStatusEnum
)
from models import Student, Class, Tenant
from teacher_models import Teacher

logger = logging.getLogger(__name__)


def create_notification_routes(school_blueprint, require_school_auth):
    """Add notification management routes to school blueprint"""
    
    # ===== NOTIFICATIONS DASHBOARD =====
    @school_blueprint.route('/<tenant_slug>/notifications')
    @require_school_auth
    def notifications_dashboard(tenant_slug):
        """Notifications dashboard with statistics"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Get statistics
            stats = {
                'total': session.query(Notification).filter_by(tenant_id=tenant_id).count(),
                'sent': session.query(Notification).filter_by(tenant_id=tenant_id, status=NotificationStatusEnum.SENT).count(),
                'draft': session.query(Notification).filter_by(tenant_id=tenant_id, status=NotificationStatusEnum.DRAFT).count(),
                'scheduled': session.query(Notification).filter_by(tenant_id=tenant_id, status=NotificationStatusEnum.SCHEDULED).count(),
            }
            
            # Recent notifications
            recent_notifications = session.query(Notification).filter_by(
                tenant_id=tenant_id
            ).order_by(desc(Notification.created_at)).limit(10).all()
            
            # Recent templates
            templates_count = session.query(NotificationTemplate).filter_by(
                tenant_id=tenant_id, is_active=True
            ).count()
            
            return render_template('akademi/notifications/dashboard.html',
                                 school=g.current_tenant,
                                 stats=stats,
                                 recent_notifications=recent_notifications,
                                 templates_count=templates_count,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== ALL NOTIFICATIONS LIST =====
    @school_blueprint.route('/<tenant_slug>/notifications/all')
    @require_school_auth
    def notifications_list(tenant_slug):
        """List all notifications with filters"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Filters
            status = request.args.get('status', '')
            priority = request.args.get('priority', '')
            recipient_type = request.args.get('recipient_type', '')
            search = request.args.get('search', '').strip()
            page = request.args.get('page', 1, type=int)
            per_page = 20
            
            query = session.query(Notification).filter_by(tenant_id=tenant_id)
            
            if status:
                query = query.filter(Notification.status == status)
            
            if priority:
                query = query.filter(Notification.priority == priority)
            
            if recipient_type:
                query = query.filter(Notification.recipient_type == recipient_type)
            
            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    or_(
                        Notification.title.ilike(search_pattern),
                        Notification.message.ilike(search_pattern)
                    )
                )
            
            # Get total count
            total = query.count()
            total_pages = (total + per_page - 1) // per_page
            
            # Paginate
            notifications = query.order_by(desc(Notification.created_at)).offset(
                (page - 1) * per_page
            ).limit(per_page).all()
            
            pagination = {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'start': (page - 1) * per_page + 1 if total > 0 else 0,
                'end': min(page * per_page, total)
            }
            
            # Get filter options
            statuses = [e.value for e in NotificationStatusEnum]
            priorities = [e.value for e in NotificationPriorityEnum]
            recipient_types = [e.value for e in RecipientTypeEnum]
            
            current_filters = {
                'status': status,
                'priority': priority,
                'recipient_type': recipient_type,
                'search': search
            }
            
            return render_template('akademi/notifications/list.html',
                                 school=g.current_tenant,
                                 notifications=notifications,
                                 statuses=statuses,
                                 priorities=priorities,
                                 recipient_types=recipient_types,
                                 current_filters=current_filters,
                                 pagination=pagination,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== CREATE NOTIFICATION =====
    @school_blueprint.route('/<tenant_slug>/notifications/create', methods=['GET', 'POST'])
    @require_school_auth
    def notifications_create(tenant_slug):
        """Create a new notification"""
        import sys
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            if request.method == 'POST':
                print(f"[NOTIFICATION] POST request received", flush=True)
                try:
                    # Get form data
                    title = request.form.get('title', '').strip()
                    message = request.form.get('message', '').strip()
                    recipient_type = request.form.get('recipient_type', '')
                    priority = request.form.get('priority', 'Normal')
                    class_id = request.form.get('class_id', type=int)
                    action = request.form.get('action', 'draft')  # draft or send
                    scheduled_at_str = request.form.get('scheduled_at', '').strip()
                    send_as_email = request.form.get('send_as_email') in ('1', 'on', 'true')  # Email checkbox
                    send_as_whatsapp = request.form.get('send_as_whatsapp') in ('1', 'on', 'true')  # WhatsApp checkbox
                    
                    # Debug log for email checkbox
                    print(f"[NOTIFICATION] send_as_email checkbox value: {request.form.get('send_as_email')} -> {send_as_email}", flush=True)
                    print(f"[NOTIFICATION] send_as_whatsapp checkbox value: {request.form.get('send_as_whatsapp')} -> {send_as_whatsapp}", flush=True)
                    print(f"[NOTIFICATION] Action: {action}, Title: {title[:30]}...", flush=True)
                    sys.stdout.flush()
                    
                    # Get selected recipients for specific targeting
                    selected_students = request.form.getlist('students[]')
                    selected_teachers = request.form.getlist('teachers[]')
                    
                    # Validate required fields
                    if not title or not message or not recipient_type:
                        flash('Title, message, and recipient type are required', 'danger')
                        raise ValueError('Missing required fields')
                    
                    # Validate recipient type requirements
                    if recipient_type == RecipientTypeEnum.CLASS.value and not class_id:
                        flash('Please select a class for class-targeted notifications', 'danger')
                        raise ValueError('Class required for class notifications')
                    
                    if recipient_type == RecipientTypeEnum.SPECIFIC_STUDENTS.value and not selected_students:
                        flash('Please select at least one student', 'danger')
                        raise ValueError('No students selected')
                    
                    if recipient_type == RecipientTypeEnum.SPECIFIC_TEACHERS.value and not selected_teachers:
                        flash('Please select at least one teacher', 'danger')
                        raise ValueError('No teachers selected')
                    
                    # Determine status
                    status = NotificationStatusEnum.DRAFT
                    scheduled_at = None
                    
                    if action == 'send':
                        status = NotificationStatusEnum.SENT
                    elif action == 'schedule' and scheduled_at_str:
                        status = NotificationStatusEnum.SCHEDULED
                        scheduled_at = datetime.strptime(scheduled_at_str, '%Y-%m-%dT%H:%M')
                    
                    # Create notification
                    notification = Notification(
                        tenant_id=tenant_id,
                        title=title,
                        message=message,
                        recipient_type=recipient_type,
                        class_id=class_id if recipient_type == RecipientTypeEnum.CLASS.value else None,
                        priority=priority,
                        status=status,
                        scheduled_at=scheduled_at,
                        sent_at=datetime.now() if status == NotificationStatusEnum.SENT else None,
                        send_as_email=send_as_email,
                        created_by=current_user.id if hasattr(current_user, 'id') else None
                    )
                    
                    session.add(notification)
                    session.flush()  # Get the notification ID
                    
                    # Create recipients based on type
                    recipients = []
                    
                    if recipient_type == RecipientTypeEnum.ALL_STUDENTS.value:
                        from models import StudentStatusEnum
                        students = session.query(Student).filter_by(
                            tenant_id=tenant_id,
                            status=StudentStatusEnum.ACTIVE
                        ).all()
                        for student in students:
                            recipients.append(NotificationRecipient(
                                tenant_id=tenant_id,
                                notification_id=notification.id,
                                student_id=student.id,
                                status=RecipientStatusEnum.SENT if status == NotificationStatusEnum.SENT else RecipientStatusEnum.PENDING,
                                sent_at=datetime.now() if status == NotificationStatusEnum.SENT else None
                            ))
                    
                    elif recipient_type == RecipientTypeEnum.ALL_TEACHERS.value:
                        from teacher_models import EmployeeStatusEnum
                        teachers = session.query(Teacher).filter_by(
                            tenant_id=tenant_id,
                            employee_status=EmployeeStatusEnum.ACTIVE
                        ).all()
                        for teacher in teachers:
                            recipients.append(NotificationRecipient(
                                tenant_id=tenant_id,
                                notification_id=notification.id,
                                teacher_id=teacher.id,
                                status=RecipientStatusEnum.SENT if status == NotificationStatusEnum.SENT else RecipientStatusEnum.PENDING,
                                sent_at=datetime.now() if status == NotificationStatusEnum.SENT else None
                            ))
                    
                    elif recipient_type == RecipientTypeEnum.ALL.value:
                        # Both students and teachers
                        from models import StudentStatusEnum
                        from teacher_models import EmployeeStatusEnum
                        students = session.query(Student).filter_by(
                            tenant_id=tenant_id,
                            status=StudentStatusEnum.ACTIVE
                        ).all()
                        teachers = session.query(Teacher).filter_by(
                            tenant_id=tenant_id,
                            employee_status=EmployeeStatusEnum.ACTIVE
                        ).all()
                        
                        for student in students:
                            recipients.append(NotificationRecipient(
                                tenant_id=tenant_id,
                                notification_id=notification.id,
                                student_id=student.id,
                                status=RecipientStatusEnum.SENT if status == NotificationStatusEnum.SENT else RecipientStatusEnum.PENDING,
                                sent_at=datetime.now() if status == NotificationStatusEnum.SENT else None
                            ))
                        
                        for teacher in teachers:
                            recipients.append(NotificationRecipient(
                                tenant_id=tenant_id,
                                notification_id=notification.id,
                                teacher_id=teacher.id,
                                status=RecipientStatusEnum.SENT if status == NotificationStatusEnum.SENT else RecipientStatusEnum.PENDING,
                                sent_at=datetime.now() if status == NotificationStatusEnum.SENT else None
                            ))
                    
                    elif recipient_type == RecipientTypeEnum.CLASS.value:
                        from models import StudentStatusEnum
                        students = session.query(Student).filter_by(
                            tenant_id=tenant_id,
                            class_id=class_id,
                            status=StudentStatusEnum.ACTIVE
                        ).all()
                        for student in students:
                            recipients.append(NotificationRecipient(
                                tenant_id=tenant_id,
                                notification_id=notification.id,
                                student_id=student.id,
                                status=RecipientStatusEnum.SENT if status == NotificationStatusEnum.SENT else RecipientStatusEnum.PENDING,
                                sent_at=datetime.now() if status == NotificationStatusEnum.SENT else None
                            ))
                    
                    elif recipient_type == RecipientTypeEnum.SPECIFIC_STUDENTS.value:
                        for student_id in selected_students:
                            recipients.append(NotificationRecipient(
                                tenant_id=tenant_id,
                                notification_id=notification.id,
                                student_id=int(student_id),
                                status=RecipientStatusEnum.SENT if status == NotificationStatusEnum.SENT else RecipientStatusEnum.PENDING,
                                sent_at=datetime.now() if status == NotificationStatusEnum.SENT else None
                            ))
                    
                    elif recipient_type == RecipientTypeEnum.SPECIFIC_TEACHERS.value:
                        for teacher_id in selected_teachers:
                            recipients.append(NotificationRecipient(
                                tenant_id=tenant_id,
                                notification_id=notification.id,
                                teacher_id=int(teacher_id),
                                status=RecipientStatusEnum.SENT if status == NotificationStatusEnum.SENT else RecipientStatusEnum.PENDING,
                                sent_at=datetime.now() if status == NotificationStatusEnum.SENT else None
                            ))
                    
                    session.add_all(recipients)
                    
                    # Handle document uploads
                    files = request.files.getlist('documents[]')
                    for file in files:
                        if file and file.filename:
                            filename = secure_filename(file.filename)
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f"{timestamp}_{filename}"
                            
                            # Create upload directory
                            upload_folder = os.path.join(
                                'akademi', 'static', 'uploads', 'notifications',
                                str(tenant_id), str(notification.id)
                            )
                            os.makedirs(upload_folder, exist_ok=True)
                            
                            file_path = os.path.join(upload_folder, filename)
                            file.save(file_path)
                            
                            # Get file size
                            file_size_kb = os.path.getsize(file_path) // 1024
                            
                            doc = NotificationDocument(
                                tenant_id=tenant_id,
                                notification_id=notification.id,
                                file_name=filename,
                                file_path=f"uploads/notifications/{tenant_id}/{notification.id}/{filename}",
                                file_size_kb=file_size_kb,
                                mime_type=file.content_type,
                                uploaded_by=current_user.id if hasattr(current_user, 'id') else None
                            )
                            session.add(doc)
                    
                    # Ensure notification creation timestamps align with local time
                    try:
                        # If model uses defaults, they may already be set; explicitly set created_at if missing
                        if not getattr(notification, 'created_at', None):
                            notification.created_at = datetime.now()
                    except Exception:
                        pass

                    session.commit()
                    
                    # Debug: Log email decision
                    print(f"[NOTIFICATION] After commit - send_as_email={send_as_email}, status={status}")
                    
                    # Send emails if enabled and notification is being sent immediately
                    email_count = 0
                    whatsapp_count = 0
                    
                    if send_as_email and status == NotificationStatusEnum.SENT:
                        print(f"[NOTIFICATION] Email sending triggered for notification ID {notification.id}")
                        try:
                            from notification_email import send_notification_emails_async
                            
                            # Collect recipient emails
                            recipients_with_emails = []
                            for r in recipients:
                                if r.student_id:
                                    student = session.query(Student).filter_by(id=r.student_id).first()
                                    if student and student.email:
                                        recipients_with_emails.append((student.full_name, student.email))
                                        print(f"[NOTIFICATION] Found student email: {student.email}")
                                elif r.teacher_id:
                                    teacher = session.query(Teacher).filter_by(id=r.teacher_id).first()
                                    if teacher and teacher.email:
                                        recipients_with_emails.append((teacher.full_name, teacher.email))
                                        print(f"[NOTIFICATION] Found teacher email: {teacher.email}")
                            
                            print(f"[NOTIFICATION] Total emails collected: {len(recipients_with_emails)}")
                            email_count = len(recipients_with_emails)
                            
                            if recipients_with_emails:
                                # Refresh notification to get documents
                                notification = session.query(Notification).filter_by(id=notification.id).first()
                                
                                # Create a plain dict for the async thread (avoid DetachedInstanceError)
                                notification_data = {
                                    'id': notification.id,
                                    'title': notification.title,
                                    'message': notification.message,
                                    'priority': notification.priority.value if hasattr(notification.priority, 'value') else str(notification.priority),
                                    'documents': [
                                        {
                                            'file_name': doc.file_name,
                                            'file_path': doc.file_path,
                                            'file_size_kb': doc.file_size_kb,
                                            'mime_type': doc.mime_type
                                        }
                                        for doc in notification.documents
                                    ] if notification.documents else []
                                }
                                
                                from notification_email import send_notification_emails_async
                                send_notification_emails_async(notification_data, recipients_with_emails)
                                notification.email_sent_at = datetime.now()
                                session.commit()
                        except Exception as email_error:
                            logger.error(f"Error sending notification emails: {email_error}")
                            flash(f'Email sending failed: {str(email_error)}', 'warning')
                    
                    # Send WhatsApp messages if enabled and notification is being sent immediately
                    if send_as_whatsapp and status == NotificationStatusEnum.SENT:
                        print(f"[NOTIFICATION] WhatsApp sending triggered for notification ID {notification.id}")
                        try:
                            from whatsapp_helper import send_whatsapp_async, is_whatsapp_configured
                            
                            if is_whatsapp_configured(tenant_id):
                                # Collect recipient phone numbers
                                recipients_with_phones = []
                                for r in recipients:
                                    if r.student_id:
                                        student = session.query(Student).filter_by(id=r.student_id).first()
                                        # Try student phone, then parent phone, then father's phone
                                        phone = None
                                        if student:
                                            phone = student.mobile_number or getattr(student, 'parent_mobile', None) or getattr(student, 'father_mobile', None)
                                            if phone:
                                                recipients_with_phones.append((phone, student.full_name, 'student'))
                                                print(f"[NOTIFICATION] Found student phone: {phone}")
                                    elif r.teacher_id:
                                        teacher = session.query(Teacher).filter_by(id=r.teacher_id).first()
                                        if teacher and teacher.phone_primary:
                                            recipients_with_phones.append((teacher.phone_primary, teacher.full_name, 'teacher'))
                                            print(f"[NOTIFICATION] Found teacher phone: {teacher.phone_primary}")
                                
                                print(f"[NOTIFICATION] Total WhatsApp recipients collected: {len(recipients_with_phones)}")
                                whatsapp_count = len(recipients_with_phones)
                                
                                if recipients_with_phones:
                                    # Create WhatsApp message (combine title and message)
                                    wa_message = f"*{notification.title}*\n\n{notification.message}"
                                    
                                    # Collect document URLs and local file paths for WhatsApp attachments
                                    media_urls = []
                                    media_files = []
                                    if notification.documents:
                                        # Use production URL instead of localhost
                                        base_url = os.getenv('WHATSAPP_MEDIA_BASE_URL', 'https://erp.edusaint.in')
                                        for doc in notification.documents:
                                            # Build public URL for the document
                                            file_path = doc.file_path
                                            if file_path.startswith('uploads/'):
                                                doc_url = f"{base_url}/akademi/static/{file_path}"
                                                local_path = os.path.join('akademi', 'static', file_path)
                                            else:
                                                doc_url = f"{base_url}/akademi/static/uploads/{file_path}"
                                                local_path = os.path.join('akademi', 'static', 'uploads', file_path)

                                            media_urls.append(doc_url)
                                            media_files.append(local_path)
                                            logger.info(f"[NOTIFICATION] Adding WhatsApp attachment: {doc_url} (local: {local_path})")
                                    
                                    # Send async to avoid blocking; pass both public URLs and local file paths
                                    send_whatsapp_async(
                                        tenant_id=tenant_id,
                                        recipients=recipients_with_phones,
                                        message=wa_message,
                                        notification_id=notification.id,
                                        media_urls=media_urls if media_urls else None,
                                        media_files=media_files if media_files else None
                                    )
                                    notification.whatsapp_sent_at = datetime.now()
                                    session.commit()
                            else:
                                flash('WhatsApp is not configured properly', 'warning')
                        except Exception as wa_error:
                            logger.error(f"Error sending WhatsApp notifications: {wa_error}")
                            flash(f'WhatsApp sending failed: {str(wa_error)}', 'warning')
                    
                    # Flash success message
                    if status == NotificationStatusEnum.SENT:
                        msg_parts = [f'Notification sent to {len(recipients)} recipient(s)']
                        if email_count > 0:
                            msg_parts.append(f'{email_count} email(s) queued')
                        if whatsapp_count > 0:
                            msg_parts.append(f'{whatsapp_count} WhatsApp message(s) queued')
                        flash(', '.join(msg_parts) + '!', 'success')
                    elif status == NotificationStatusEnum.SCHEDULED:
                        flash(f'Notification scheduled for {scheduled_at_str}', 'success')
                    else:
                        flash('Notification saved as draft', 'success')
                    
                    return redirect(url_for('school.notifications_list', tenant_slug=tenant_slug))
                    
                except ValueError:
                    # Flash message already set
                    pass
                except Exception as e:
                    session.rollback()
                    logger.error(f"Error creating notification: {e}")
                    flash(f'Error creating notification: {str(e)}', 'danger')
            
            # GET request - show form
            classes = session.query(Class).filter_by(tenant_id=tenant_id, is_active=True).order_by(Class.class_name, Class.section).all()
            from models import StudentStatusEnum
            students = session.query(Student).filter_by(
                tenant_id=tenant_id,
                status=StudentStatusEnum.ACTIVE
            ).order_by(Student.full_name).all()
            from teacher_models import EmployeeStatusEnum
            teachers = session.query(Teacher).filter_by(
                tenant_id=tenant_id,
                employee_status=EmployeeStatusEnum.ACTIVE
            ).order_by(Teacher.first_name).all()
            templates = session.query(NotificationTemplate).filter_by(tenant_id=tenant_id, is_active=True).all()
            
            # Check if WhatsApp is configured
            from whatsapp_helper import is_whatsapp_configured
            whatsapp_enabled = is_whatsapp_configured(tenant_id)
            
            priorities = [e.value for e in NotificationPriorityEnum]
            recipient_types = [
                {'value': e.value, 'name': e.value} for e in RecipientTypeEnum
            ]
            
            return render_template('akademi/notifications/create.html',
                                 school=g.current_tenant,
                                 classes=classes,
                                 students=students,
                                 teachers=teachers,
                                 templates=templates,
                                 priorities=priorities,
                                 recipient_types=recipient_types,
                                 whatsapp_enabled=whatsapp_enabled,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== VIEW NOTIFICATION =====
    @school_blueprint.route('/<tenant_slug>/notifications/<int:notification_id>')
    @require_school_auth
    def notifications_view(tenant_slug, notification_id):
        """View notification details"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            notification = session.query(Notification).filter_by(
                id=notification_id, tenant_id=tenant_id
            ).first()
            
            if not notification:
                flash('Notification not found', 'danger')
                return redirect(url_for('school.notifications_list', tenant_slug=tenant_slug))
            
            # Get recipient stats
            recipients = notification.recipients
            total_recipients = len(recipients)
            sent_count = sum(1 for r in recipients if r.status in [RecipientStatusEnum.SENT, RecipientStatusEnum.READ])
            read_count = sum(1 for r in recipients if r.status == RecipientStatusEnum.READ)
            pending_count = sum(1 for r in recipients if r.status == RecipientStatusEnum.PENDING)
            failed_count = sum(1 for r in recipients if r.status == RecipientStatusEnum.FAILED)
            
            stats = {
                'total': total_recipients,
                'sent': sent_count,
                'read': read_count,
                'pending': pending_count,
                'failed': failed_count
            }
            
            return render_template('akademi/notifications/view.html',
                                 school=g.current_tenant,
                                 notification=notification,
                                 stats=stats,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== EDIT NOTIFICATION (DRAFT ONLY) =====
    @school_blueprint.route('/<tenant_slug>/notifications/<int:notification_id>/edit', methods=['GET', 'POST'])
    @require_school_auth
    def notifications_edit(tenant_slug, notification_id):
        """Edit a draft notification"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            notification = session.query(Notification).filter_by(
                id=notification_id, tenant_id=tenant_id
            ).first()
            
            if not notification:
                flash('Notification not found', 'danger')
                return redirect(url_for('school.notifications_list', tenant_slug=tenant_slug))
            
            if notification.status != NotificationStatusEnum.DRAFT:
                flash('Only draft notifications can be edited', 'warning')
                return redirect(url_for('school.notifications_view', tenant_slug=tenant_slug, notification_id=notification_id))
            
            if request.method == 'POST':
                try:
                    notification.title = request.form.get('title', '').strip()
                    notification.message = request.form.get('message', '').strip()
                    notification.priority = request.form.get('priority', 'Normal')
                    
                    action = request.form.get('action', 'draft')
                    
                    if action == 'send':
                        notification.status = NotificationStatusEnum.SENT
                        notification.sent_at = datetime.now()
                        
                        # Update all recipients to sent
                        for recipient in notification.recipients:
                            recipient.status = RecipientStatusEnum.SENT
                            recipient.sent_at = datetime.now()
                    
                    session.commit()
                    
                    if action == 'send':
                        flash('Notification sent successfully!', 'success')
                    else:
                        flash('Notification updated', 'success')
                    
                    return redirect(url_for('school.notifications_view', tenant_slug=tenant_slug, notification_id=notification_id))
                    
                except Exception as e:
                    session.rollback()
                    flash(f'Error updating notification: {str(e)}', 'danger')
            
            # GET request
            priorities = [e.value for e in NotificationPriorityEnum]
            
            return render_template('akademi/notifications/edit.html',
                                 school=g.current_tenant,
                                 notification=notification,
                                 priorities=priorities,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== DELETE NOTIFICATION =====
    @school_blueprint.route('/<tenant_slug>/notifications/<int:notification_id>/delete', methods=['POST'])
    @require_school_auth
    def notifications_delete(tenant_slug, notification_id):
        """Delete a notification"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            notification = session.query(Notification).filter_by(
                id=notification_id, tenant_id=tenant_id
            ).first()
            
            if not notification:
                flash('Notification not found', 'danger')
                return redirect(url_for('school.notifications_list', tenant_slug=tenant_slug))
            
            # Delete associated documents from disk
            for doc in notification.documents:
                try:
                    file_path = os.path.join('akademi', 'static', doc.file_path)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error deleting notification document: {e}")
            
            session.delete(notification)
            session.commit()
            
            flash('Notification deleted successfully', 'success')
            return redirect(url_for('school.notifications_list', tenant_slug=tenant_slug))
            
        except Exception as e:
            session.rollback()
            flash(f'Error deleting notification: {str(e)}', 'danger')
            return redirect(url_for('school.notifications_list', tenant_slug=tenant_slug))
        finally:
            session.close()
    
    # ===== SEND DRAFT NOTIFICATION =====
    @school_blueprint.route('/<tenant_slug>/notifications/<int:notification_id>/send', methods=['POST'])
    @require_school_auth
    def notifications_send(tenant_slug, notification_id):
        """Send a draft notification"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            notification = session.query(Notification).filter_by(
                id=notification_id, tenant_id=tenant_id
            ).first()
            
            if not notification:
                flash('Notification not found', 'danger')
                return redirect(url_for('school.notifications_list', tenant_slug=tenant_slug))
            
            if notification.status not in [NotificationStatusEnum.DRAFT, NotificationStatusEnum.SCHEDULED]:
                flash('This notification has already been sent', 'warning')
                return redirect(url_for('school.notifications_view', tenant_slug=tenant_slug, notification_id=notification_id))
            
            notification.status = NotificationStatusEnum.SENT
            notification.sent_at = datetime.now()
            
            # Update all recipients to sent
            for recipient in notification.recipients:
                recipient.status = RecipientStatusEnum.SENT
                recipient.sent_at = datetime.now()
            
            session.commit()
            
            # Send emails if enabled
            if notification.send_as_email:
                try:
                    from notification_email import send_notification_emails_async
                    
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
                        flash(f'Notification sent to {len(notification.recipients)} recipient(s) and {len(recipients_with_emails)} email(s) queued!', 'success')
                    else:
                        flash(f'Notification sent to {len(notification.recipients)} recipient(s)! (No valid emails found)', 'warning')
                except Exception as email_error:
                    logger.error(f"Error sending notification emails: {email_error}")
                    flash(f'Notification sent to {len(notification.recipients)} recipient(s)! (Email failed: {str(email_error)})', 'warning')
            else:
                flash(f'Notification sent to {len(notification.recipients)} recipient(s)!', 'success')
            
            return redirect(url_for('school.notifications_view', tenant_slug=tenant_slug, notification_id=notification_id))
            
        except Exception as e:
            session.rollback()
            flash(f'Error sending notification: {str(e)}', 'danger')
            return redirect(url_for('school.notifications_view', tenant_slug=tenant_slug, notification_id=notification_id))
        finally:
            session.close()
    
    # ===== TEMPLATES LIST =====
    @school_blueprint.route('/<tenant_slug>/notifications/templates')
    @require_school_auth
    def notification_templates_list(tenant_slug):
        """List all notification templates"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            templates = session.query(NotificationTemplate).filter_by(
                tenant_id=tenant_id
            ).order_by(NotificationTemplate.category, NotificationTemplate.name).all()
            
            return render_template('akademi/notifications/templates_list.html',
                                 school=g.current_tenant,
                                 templates=templates,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== CREATE TEMPLATE =====
    @school_blueprint.route('/<tenant_slug>/notifications/templates/create', methods=['GET', 'POST'])
    @require_school_auth
    def notification_templates_create(tenant_slug):
        """Create a new notification template"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            if request.method == 'POST':
                try:
                    template = NotificationTemplate(
                        tenant_id=tenant_id,
                        name=request.form.get('name', '').strip(),
                        category=request.form.get('category', '').strip() or None,
                        subject=request.form.get('subject', '').strip(),
                        body=request.form.get('body', '').strip(),
                        default_priority=request.form.get('priority', 'Normal'),
                        is_active=True,
                        created_by=current_user.id if hasattr(current_user, 'id') else None
                    )
                    
                    session.add(template)
                    session.commit()
                    
                    flash('Template created successfully!', 'success')
                    return redirect(url_for('school.notification_templates_list', tenant_slug=tenant_slug))
                    
                except Exception as e:
                    session.rollback()
                    flash(f'Error creating template: {str(e)}', 'danger')
            
            priorities = [e.value for e in NotificationPriorityEnum]
            categories = ['General', 'Fee', 'Attendance', 'Exam', 'Event', 'Holiday', 'Emergency', 'Other']
            
            return render_template('akademi/notifications/template_create.html',
                                 school=g.current_tenant,
                                 priorities=priorities,
                                 categories=categories,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== EDIT TEMPLATE =====
    @school_blueprint.route('/<tenant_slug>/notifications/templates/<int:template_id>/edit', methods=['GET', 'POST'])
    @require_school_auth
    def notification_templates_edit(tenant_slug, template_id):
        """Edit a notification template"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            template = session.query(NotificationTemplate).filter_by(
                id=template_id, tenant_id=tenant_id
            ).first()
            
            if not template:
                flash('Template not found', 'danger')
                return redirect(url_for('school.notification_templates_list', tenant_slug=tenant_slug))
            
            if request.method == 'POST':
                try:
                    template.name = request.form.get('name', '').strip()
                    template.category = request.form.get('category', '').strip() or None
                    template.subject = request.form.get('subject', '').strip()
                    template.body = request.form.get('body', '').strip()
                    template.default_priority = request.form.get('priority', 'Normal')
                    template.is_active = 'is_active' in request.form
                    
                    session.commit()
                    
                    flash('Template updated successfully!', 'success')
                    return redirect(url_for('school.notification_templates_list', tenant_slug=tenant_slug))
                    
                except Exception as e:
                    session.rollback()
                    flash(f'Error updating template: {str(e)}', 'danger')
            
            priorities = [e.value for e in NotificationPriorityEnum]
            categories = ['General', 'Fee', 'Attendance', 'Exam', 'Event', 'Holiday', 'Emergency', 'Other']
            
            return render_template('akademi/notifications/template_edit.html',
                                 school=g.current_tenant,
                                 template=template,
                                 priorities=priorities,
                                 categories=categories,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== DELETE TEMPLATE =====
    @school_blueprint.route('/<tenant_slug>/notifications/templates/<int:template_id>/delete', methods=['POST'])
    @require_school_auth
    def notification_templates_delete(tenant_slug, template_id):
        """Delete a notification template"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            template = session.query(NotificationTemplate).filter_by(
                id=template_id, tenant_id=tenant_id
            ).first()
            
            if not template:
                flash('Template not found', 'danger')
                return redirect(url_for('school.notification_templates_list', tenant_slug=tenant_slug))
            
            session.delete(template)
            session.commit()
            
            flash('Template deleted successfully', 'success')
            return redirect(url_for('school.notification_templates_list', tenant_slug=tenant_slug))
            
        except Exception as e:
            session.rollback()
            flash(f'Error deleting template: {str(e)}', 'danger')
            return redirect(url_for('school.notification_templates_list', tenant_slug=tenant_slug))
        finally:
            session.close()
    
    # ===== API: GET TEMPLATE DETAILS =====
    @school_blueprint.route('/<tenant_slug>/api/notifications/templates/<int:template_id>')
    @require_school_auth
    def api_notification_template(tenant_slug, template_id):
        """API to get template details for populating form"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            template = session.query(NotificationTemplate).filter_by(
                id=template_id, tenant_id=tenant_id
            ).first()
            
            if not template:
                return jsonify({'error': 'Template not found'}), 404
            
            return jsonify({
                'id': template.id,
                'name': template.name,
                'subject': template.subject,
                'body': template.body,
                'priority': template.default_priority.value if template.default_priority else 'Normal',
                'category': template.category
            })
        finally:
            session.close()
    
    # ===== API: GET STUDENTS BY CLASS =====
    @school_blueprint.route('/<tenant_slug>/api/notifications/students')
    @require_school_auth
    def api_notification_students(tenant_slug):
        """API to get students, optionally filtered by class"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            class_id = request.args.get('class_id', type=int)
            
            from models import StudentStatusEnum
            query = session.query(Student).filter_by(
                tenant_id=tenant_id,
                status=StudentStatusEnum.ACTIVE
            )
            
            if class_id:
                query = query.filter_by(class_id=class_id)
            
            students = query.order_by(Student.full_name).all()
            
            return jsonify([{
                'id': s.id,
                'name': s.full_name,
                'admission_number': s.admission_number,
                'class_name': f"{s.student_class.class_name}-{s.student_class.section}" if s.student_class else None
            } for s in students])
        finally:
            session.close()
    
    # ===== API: GET TEACHERS =====
    @school_blueprint.route('/<tenant_slug>/api/notifications/teachers')
    @require_school_auth
    def api_notification_teachers(tenant_slug):
        """API to get teachers"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            from teacher_models import EmployeeStatusEnum
            teachers = session.query(Teacher).filter_by(
                tenant_id=tenant_id,
                employee_status=EmployeeStatusEnum.ACTIVE
            ).order_by(Teacher.first_name).all()
            
            return jsonify([{
                'id': t.id,
                'name': t.full_name,
                'employee_id': t.employee_id,
                'email': t.email
            } for t in teachers])
        finally:
            session.close()
    
    # ===== API: PROCESS SCHEDULED NOTIFICATIONS =====
    @school_blueprint.route('/<tenant_slug>/api/notifications/process-scheduled', methods=['POST'])
    @require_school_auth
    def api_process_scheduled_notifications(tenant_slug):
        """API to manually trigger processing of scheduled notifications"""
        from notification_scheduler import process_scheduled_notifications
        
        try:
            processed, recipients, errors = process_scheduled_notifications()
            
            return jsonify({
                'success': True,
                'notifications_sent': processed,
                'total_recipients': recipients,
                'errors': errors
            })
        except Exception as e:
            logger.error(f"Error processing scheduled notifications: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # ===== API: GET SCHEDULED NOTIFICATIONS =====
    @school_blueprint.route('/<tenant_slug>/api/notifications/scheduled')
    @require_school_auth
    def api_get_scheduled_notifications(tenant_slug):
        """API to get list of pending scheduled notifications for this tenant"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            notifications = session.query(Notification).filter(
                Notification.tenant_id == tenant_id,
                Notification.status == NotificationStatusEnum.SCHEDULED,
                Notification.scheduled_at.isnot(None)
            ).order_by(Notification.scheduled_at).all()
            
            return jsonify({
                'success': True,
                'notifications': [{
                    'id': n.id,
                    'title': n.title,
                    'scheduled_at': n.scheduled_at.isoformat() if n.scheduled_at else None,
                    'recipient_count': len(n.recipients),
                    'priority': n.priority.value if n.priority else 'Normal'
                } for n in notifications]
            })
        finally:
            session.close()
    
    return school_blueprint
