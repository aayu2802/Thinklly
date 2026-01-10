"""
Chat Routes for Teacher-Student Communication
Handles all chat-related endpoints for both teacher and student portals
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify, current_app
from werkzeug.utils import secure_filename
import os
from flask_login import login_required, current_user
from sqlalchemy import desc, or_, and_
from datetime import datetime
import logging

from db_single import get_session
from models import Tenant, Student, Class
from teacher_models import Teacher
from timetable_models import ClassTeacherAssignment
from chat_models import ChatConversation, ChatMessage, SenderTypeEnum

print("DEBUG: Loading updated chat_routes.py (v2)")

logger = logging.getLogger(__name__)


def register_chat_routes(school_bp, require_school_auth):
    """Register chat routes on the school blueprint"""
    
    # ===== TEACHER CHAT ROUTES =====
    
    @school_bp.route('/<tenant_slug>/teacher/<int:teacher_id>/chat')
    def teacher_chat_list(tenant_slug, teacher_id):
        """Teacher chat list - shows all students teacher can chat with"""
        session_db = get_session()
        try:
            # Get school info
            school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
            if not school:
                flash('School not found', 'error')
                return redirect('/admin/')
            
            # Get teacher
            teacher = session_db.query(Teacher).filter_by(id=teacher_id, tenant_id=school.id).first()
            if not teacher:
                flash('Teacher not found', 'error')
                return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
            
            # Get classes taught by this teacher
            class_assignments = session_db.query(ClassTeacherAssignment).filter_by(
                teacher_id=teacher_id,
                tenant_id=school.id,
                removed_date=None
            ).all()
            
            class_ids = list(set([ca.class_id for ca in class_assignments]))
            
            # Get all students in those classes
            students = []
            if class_ids:
                students = session_db.query(Student).filter(
                    Student.tenant_id == school.id,
                    Student.class_id.in_(class_ids),
                    Student.status == 'ACTIVE'
                ).order_by(Student.first_name).all()
            
            # Get existing conversations
            conversations = session_db.query(ChatConversation).filter_by(
                teacher_id=teacher_id,
                tenant_id=school.id,
                is_active=True
            ).order_by(desc(ChatConversation.last_message_at)).all()
            
            # Build student list with conversation info
            student_list = []
            conv_map = {conv.student_id: conv for conv in conversations}
            
            for student in students:
                conv = conv_map.get(student.id)
                student_list.append({
                    'id': student.id,
                    'name': student.full_name,
                    'class_name': student.student_class.class_name if student.student_class else 'N/A',
                    'section': student.student_class.section if student.student_class else '',
                    'admission_number': student.admission_number,
                    'conversation_id': conv.id if conv else None,
                    'unread_count': conv.teacher_unread_count if conv else 0,
                    'last_message_at': conv.last_message_at if conv else None,
                    'photo_url': student.photo_url if hasattr(student, 'photo_url') else None
                })
            
            # Sort by last message (conversations first, then alphabetically)
            student_list.sort(key=lambda x: (x['last_message_at'] is None, -(x['last_message_at'].timestamp() if x['last_message_at'] else 0)))
            
            return render_template('teacher_dashboard_new/chat.html',
                                 school=school,
                                 teacher=teacher,
                                 student_list=student_list,
                                 active_student=None,
                                 messages=[])
        except Exception as e:
            logger.error(f"Teacher chat list error: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading chat', 'error')
            return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/teacher/<int:teacher_id>/chat/<int:student_id>')
    def teacher_chat_with_student(tenant_slug, teacher_id, student_id):
        """Teacher chat with a specific student"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
            if not school:
                flash('School not found', 'error')
                return redirect('/admin/')
            
            teacher = session_db.query(Teacher).filter_by(id=teacher_id, tenant_id=school.id).first()
            if not teacher:
                flash('Teacher not found', 'error')
                return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
            
            student = session_db.query(Student).filter_by(id=student_id, tenant_id=school.id).first()
            if not student:
                flash('Student not found', 'error')
                return redirect(url_for('school.teacher_chat_list', tenant_slug=tenant_slug, teacher_id=teacher_id))
            
            # Get or create conversation
            conversation = session_db.query(ChatConversation).filter_by(
                tenant_id=school.id,
                teacher_id=teacher_id,
                student_id=student_id
            ).first()
            
            if not conversation:
                conversation = ChatConversation(
                    tenant_id=school.id,
                    teacher_id=teacher_id,
                    student_id=student_id
                )
                session_db.add(conversation)
                session_db.commit()
            
            # Mark messages as read for teacher
            session_db.query(ChatMessage).filter(
                ChatMessage.conversation_id == conversation.id,
                ChatMessage.sender_type == SenderTypeEnum.STUDENT,
                ChatMessage.is_read == False
            ).update({'is_read': True, 'read_at': datetime.now()})
            conversation.teacher_unread_count = 0
            session_db.commit()
            
            # Get messages
            messages = session_db.query(ChatMessage).filter_by(
                conversation_id=conversation.id
            ).order_by(ChatMessage.created_at).all()
            
            # Get student list for sidebar
            class_assignments = session_db.query(ClassTeacherAssignment).filter_by(
                teacher_id=teacher_id,
                tenant_id=school.id,
                removed_date=None
            ).all()
            class_ids = list(set([ca.class_id for ca in class_assignments]))
            
            students = []
            if class_ids:
                students = session_db.query(Student).filter(
                    Student.tenant_id == school.id,
                    Student.class_id.in_(class_ids),
                    Student.status == 'ACTIVE'
                ).order_by(Student.first_name).all()
            
            conversations = session_db.query(ChatConversation).filter_by(
                teacher_id=teacher_id,
                tenant_id=school.id,
                is_active=True
            ).all()
            conv_map = {conv.student_id: conv for conv in conversations}
            
            student_list = []
            for s in students:
                conv = conv_map.get(s.id)
                student_list.append({
                    'id': s.id,
                    'name': s.full_name,
                    'class_name': s.student_class.class_name if s.student_class else 'N/A',
                    'section': s.student_class.section if s.student_class else '',
                    'admission_number': s.admission_number,
                    'conversation_id': conv.id if conv else None,
                    'unread_count': conv.teacher_unread_count if conv else 0,
                    'last_message_at': conv.last_message_at if conv else None,
                })
            
            student_list.sort(key=lambda x: (x['last_message_at'] is None, -(x['last_message_at'].timestamp() if x['last_message_at'] else 0)))
            
            return render_template('teacher_dashboard_new/chat.html',
                                 school=school,
                                 teacher=teacher,
                                 student_list=student_list,
                                 active_student=student,
                                 conversation=conversation,
                                 messages=messages)
        except Exception as e:
            logger.error(f"Teacher chat error: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading chat', 'error')
            return redirect(url_for('school.teacher_chat_list', tenant_slug=tenant_slug, teacher_id=teacher_id))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/teacher/<int:teacher_id>/chat/<int:student_id>/messages')
    def teacher_get_messages(tenant_slug, teacher_id, student_id):
        """API: Get messages for teacher-student conversation"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
            if not school:
                return jsonify({'success': False, 'error': 'School not found'}), 404
            
            conversation = session_db.query(ChatConversation).filter_by(
                tenant_id=school.id,
                teacher_id=teacher_id,
                student_id=student_id
            ).first()
            
            if not conversation:
                return jsonify({'success': True, 'messages': [], 'unread_count': 0})
            
            # Get last_id from query params for polling
            last_id = request.args.get('last_id', 0, type=int)
            
            # Get new messages
            query = session_db.query(ChatMessage).filter_by(conversation_id=conversation.id)
            if last_id > 0:
                query = query.filter(ChatMessage.id > last_id)
            
            messages = query.order_by(ChatMessage.created_at).all()
            
            # Mark student messages as read
            if messages:
                for msg in messages:
                    if msg.sender_type == SenderTypeEnum.STUDENT and not msg.is_read:
                        msg.is_read = True
                        msg.read_at = datetime.now()
                conversation.teacher_unread_count = 0
                session_db.commit()
            
            return jsonify({
                'success': True,
                'messages': [m.to_dict() for m in messages],
                'unread_count': conversation.teacher_unread_count
            })
        except Exception as e:
            logger.error(f"Get messages error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/teacher/<int:teacher_id>/chat/<int:student_id>/send', methods=['POST'])
    def teacher_send_message(tenant_slug, teacher_id, student_id):
        """API: Teacher sends message to student"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
            if not school:
                return jsonify({'success': False, 'error': 'School not found'}), 404
            
            data = request.form
            message_text = data.get('message', '').strip()
            
            # File handling
            file = request.files.get('file')
            attachment_url = None
            attachment_type = None
            attachment_name = None
            
            if file and file.filename:
                filename = secure_filename(file.filename)
                upload_dir = os.path.join(current_app.static_folder, 'uploads', 'chat')
                os.makedirs(upload_dir, exist_ok=True)
                
                unique_filename = f"{int(datetime.now().timestamp())}_{filename}"
                file_path = os.path.join(upload_dir, unique_filename)
                file.save(file_path)
                
                attachment_url = url_for('static', filename=f'uploads/chat/{unique_filename}')
                attachment_name = filename
                
                ext = os.path.splitext(filename)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    attachment_type = 'image'
                elif ext in ['.pdf', '.doc', '.docx', '.txt']:
                    attachment_type = 'document'
                else:
                    attachment_type = 'file'
            
            if not message_text and not attachment_url:
                return jsonify({'success': False, 'error': 'Message or file is required'}), 400
            
            # Get or create conversation
            conversation = session_db.query(ChatConversation).filter_by(
                tenant_id=school.id,
                teacher_id=teacher_id,
                student_id=student_id
            ).first()
            
            if not conversation:
                conversation = ChatConversation(
                    tenant_id=school.id,
                    teacher_id=teacher_id,
                    student_id=student_id
                )
                session_db.add(conversation)
                session_db.flush()
            
            # Create message
            message = ChatMessage(
                conversation_id=conversation.id,
                sender_type=SenderTypeEnum.TEACHER,
                sender_id=teacher_id,
                message=message_text,
                attachment_url=attachment_url,
                attachment_type=attachment_type,
                attachment_name=attachment_name
            )
            session_db.add(message)
            
            # Update conversation
            conversation.last_message_at = datetime.now()
            conversation.student_unread_count += 1
            
            session_db.commit()
            
            return jsonify({
                'success': True,
                'message': message.to_dict()
            })
        except Exception as e:
            session_db.rollback()
            logger.error(f"Send message error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/teacher/<int:teacher_id>/chat/updates')
    def teacher_get_chat_updates(tenant_slug, teacher_id):
        """API: Get unread counts for all students"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
            if not school:
                return jsonify({'success': False, 'error': 'School not found'}), 404
                
            # Get active conversations with unread messages
            conversations = session_db.query(ChatConversation).filter(
                ChatConversation.tenant_id == school.id,
                ChatConversation.teacher_id == teacher_id,
                ChatConversation.is_active == True,
                ChatConversation.teacher_unread_count > 0
            ).all()
            
            updates = []
            for conv in conversations:
                updates.append({
                    'student_id': conv.student_id,
                    'unread_count': conv.teacher_unread_count,
                    'last_message_at': conv.last_message_at
                })
                
            return jsonify({'success': True, 'updates': updates})
        except Exception as e:
            logger.error(f"Teacher chat updates error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            session_db.close()

    # ===== STUDENT CHAT ROUTES =====
    
    @school_bp.route('/<tenant_slug>/student/<int:student_id>/chat')
    def student_chat_list(tenant_slug, student_id):
        """Student chat list - shows all teachers student can chat with"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
            if not school:
                flash('School not found', 'error')
                return redirect('/admin/')
            
            student = session_db.query(Student).filter_by(id=student_id, tenant_id=school.id).first()
            if not student:
                flash('Student not found', 'error')
                return redirect(url_for('student_auth.student_dashboard', tenant_slug=tenant_slug))
            
            # Get teachers who teach this student's class
            class_assignments = session_db.query(ClassTeacherAssignment).filter_by(
                class_id=student.class_id,
                tenant_id=school.id,
                removed_date=None
            ).all()
            
            teacher_ids = list(set([ca.teacher_id for ca in class_assignments]))
            
            teachers = []
            if teacher_ids:
                teachers = session_db.query(Teacher).filter(
                    Teacher.id.in_(teacher_ids),
                    Teacher.tenant_id == school.id
                ).order_by(Teacher.first_name).all()
            
            # Get existing conversations
            conversations = session_db.query(ChatConversation).filter_by(
                student_id=student_id,
                tenant_id=school.id,
                is_active=True
            ).order_by(desc(ChatConversation.last_message_at)).all()
            
            conv_map = {conv.teacher_id: conv for conv in conversations}
            
            # Build teacher list with conversation info
            teacher_list = []
            for teacher in teachers:
                conv = conv_map.get(teacher.id)
                # Get subject for this teacher-class assignment
                assignment = next((ca for ca in class_assignments if ca.teacher_id == teacher.id), None)
                subject_name = assignment.subject.name if assignment and assignment.subject else 'N/A'
                
                teacher_list.append({
                    'id': teacher.id,
                    'name': teacher.full_name,
                    'subject': subject_name,
                    'designation': teacher.designation if hasattr(teacher, 'designation') else '',
                    'conversation_id': conv.id if conv else None,
                    'unread_count': conv.student_unread_count if conv else 0,
                    'last_message_at': conv.last_message_at if conv else None,
                    'photo_url': teacher.photo_url if hasattr(teacher, 'photo_url') else None
                })
            
            teacher_list.sort(key=lambda x: (x['last_message_at'] is None, -(x['last_message_at'].timestamp() if x['last_message_at'] else 0)))
            
            return render_template('student_dashboard_new/chat.html',
                                 school=school,
                                 student=student,
                                 teacher_list=teacher_list,
                                 active_teacher=None,
                                 messages=[])
        except Exception as e:
            logger.error(f"Student chat list error: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading chat', 'error')
            return redirect(url_for('student_auth.student_dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/student/<int:student_id>/chat/<int:teacher_id>')
    def student_chat_with_teacher(tenant_slug, student_id, teacher_id):
        """Student chat with a specific teacher"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
            if not school:
                flash('School not found', 'error')
                return redirect('/admin/')
            
            student = session_db.query(Student).filter_by(id=student_id, tenant_id=school.id).first()
            if not student:
                flash('Student not found', 'error')
                return redirect(url_for('student_auth.student_dashboard', tenant_slug=tenant_slug))
            
            teacher = session_db.query(Teacher).filter_by(id=teacher_id, tenant_id=school.id).first()
            if not teacher:
                flash('Teacher not found', 'error')
                return redirect(url_for('school.student_chat_list', tenant_slug=tenant_slug, student_id=student_id))
            
            # Get or create conversation
            conversation = session_db.query(ChatConversation).filter_by(
                tenant_id=school.id,
                teacher_id=teacher_id,
                student_id=student_id
            ).first()
            
            if not conversation:
                conversation = ChatConversation(
                    tenant_id=school.id,
                    teacher_id=teacher_id,
                    student_id=student_id
                )
                session_db.add(conversation)
                session_db.commit()
            
            # Mark messages as read for student
            session_db.query(ChatMessage).filter(
                ChatMessage.conversation_id == conversation.id,
                ChatMessage.sender_type == SenderTypeEnum.TEACHER,
                ChatMessage.is_read == False
            ).update({'is_read': True, 'read_at': datetime.now()})
            conversation.student_unread_count = 0
            session_db.commit()
            
            # Get messages
            messages = session_db.query(ChatMessage).filter_by(
                conversation_id=conversation.id
            ).order_by(ChatMessage.created_at).all()
            
            # Get teacher list for sidebar
            class_assignments = session_db.query(ClassTeacherAssignment).filter_by(
                class_id=student.class_id,
                tenant_id=school.id,
                removed_date=None
            ).all()
            teacher_ids = list(set([ca.teacher_id for ca in class_assignments]))
            
            teachers = []
            if teacher_ids:
                teachers = session_db.query(Teacher).filter(
                    Teacher.id.in_(teacher_ids),
                    Teacher.tenant_id == school.id
                ).order_by(Teacher.first_name).all()
            
            conversations = session_db.query(ChatConversation).filter_by(
                student_id=student_id,
                tenant_id=school.id,
                # removed_date=None # TODO: Add check for current academic year if needed
            ).all()
            conv_map = {conv.teacher_id: conv for conv in conversations}
            
            teacher_list = []
            for t in teachers:
                conv = conv_map.get(t.id)
                assignment = next((ca for ca in class_assignments if ca.teacher_id == t.id), None)
                subject_name = assignment.subject.name if assignment and assignment.subject else 'N/A'
                
                teacher_list.append({
                    'id': t.id,
                    'name': t.full_name,
                    'subject': subject_name,
                    'conversation_id': conv.id if conv else None,
                    'unread_count': conv.student_unread_count if conv else 0,
                    'last_message_at': conv.last_message_at if conv else None,
                })
            
            teacher_list.sort(key=lambda x: (x['last_message_at'] is None, -(x['last_message_at'].timestamp() if x['last_message_at'] else 0)))
            
            return render_template('student_dashboard_new/chat.html',
                                 school=school,
                                 student=student,
                                 teacher_list=teacher_list,
                                 active_teacher=teacher,
                                 conversation=conversation,
                                 messages=messages)
        except Exception as e:
            logger.error(f"Student chat error: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading chat', 'error')
            return redirect(url_for('school.student_chat_list', tenant_slug=tenant_slug, student_id=student_id))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/student/<int:student_id>/chat/<int:teacher_id>/messages')
    def student_get_messages(tenant_slug, student_id, teacher_id):
        """API: Get messages for student-teacher conversation"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
            if not school:
                return jsonify({'success': False, 'error': 'School not found'}), 404
            
            conversation = session_db.query(ChatConversation).filter_by(
                tenant_id=school.id,
                teacher_id=teacher_id,
                student_id=student_id
            ).first()
            
            if not conversation:
                return jsonify({'success': True, 'messages': [], 'unread_count': 0})
            
            last_id = request.args.get('last_id', 0, type=int)
            
            query = session_db.query(ChatMessage).filter_by(conversation_id=conversation.id)
            if last_id > 0:
                query = query.filter(ChatMessage.id > last_id)
            
            messages = query.order_by(ChatMessage.created_at).all()
            
            # Mark teacher messages as read
            if messages:
                for msg in messages:
                    if msg.sender_type == SenderTypeEnum.TEACHER and not msg.is_read:
                        msg.is_read = True
                        msg.read_at = datetime.now()
                conversation.student_unread_count = 0
                session_db.commit()
            
            return jsonify({
                'success': True,
                'messages': [m.to_dict() for m in messages],
                'unread_count': conversation.student_unread_count
            })
        except Exception as e:
            logger.error(f"Get messages error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/student/<int:student_id>/chat/<int:teacher_id>/send', methods=['POST'])
    def student_send_message(tenant_slug, student_id, teacher_id):
        """API: Student sends message to teacher"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
            if not school:
                return jsonify({'success': False, 'error': 'School not found'}), 404
            
            data = request.form
            message_text = data.get('message', '').strip()
            
            # File handling
            file = request.files.get('file')
            attachment_url = None
            attachment_type = None
            attachment_name = None
            
            if file and file.filename:
                filename = secure_filename(file.filename)
                upload_dir = os.path.join(current_app.static_folder, 'uploads', 'chat')
                os.makedirs(upload_dir, exist_ok=True)
                
                unique_filename = f"{int(datetime.now().timestamp())}_{filename}"
                file_path = os.path.join(upload_dir, unique_filename)
                file.save(file_path)
                
                attachment_url = url_for('static', filename=f'uploads/chat/{unique_filename}')
                attachment_name = filename
                
                ext = os.path.splitext(filename)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    attachment_type = 'image'
                elif ext in ['.pdf', '.doc', '.docx', '.txt']:
                    attachment_type = 'document'
                else:
                    attachment_type = 'file'
            
            if not message_text and not attachment_url:
                return jsonify({'success': False, 'error': 'Message or file is required'}), 400
            
            # Get or create conversation
            conversation = session_db.query(ChatConversation).filter_by(
                tenant_id=school.id,
                teacher_id=teacher_id,
                student_id=student_id
            ).first()
            
            if not conversation:
                conversation = ChatConversation(
                    tenant_id=school.id,
                    teacher_id=teacher_id,
                    student_id=student_id
                )
                session_db.add(conversation)
                session_db.flush()
            
            # Create message
            message = ChatMessage(
                conversation_id=conversation.id,
                sender_type=SenderTypeEnum.STUDENT,
                sender_id=student_id,
                message=message_text,
                attachment_url=attachment_url,
                attachment_type=attachment_type,
                attachment_name=attachment_name
            )
            session_db.add(message)
            
            # Update conversation
            conversation.last_message_at = datetime.now()
            conversation.teacher_unread_count += 1
            
            session_db.commit()
            
            return jsonify({
                'success': True,
                'message': message.to_dict()
            })
        except Exception as e:
            session_db.rollback()
            logger.error(f"Send message error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            session_db.close()
    @school_bp.route('/<tenant_slug>/student/<int:student_id>/chat/updates')
    def student_get_chat_updates(tenant_slug, student_id):
        """API: Get unread counts for all teachers"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
            if not school:
                return jsonify({'success': False, 'error': 'School not found'}), 404
                
            # Get active conversations with unread messages
            conversations = session_db.query(ChatConversation).filter(
                ChatConversation.tenant_id == school.id,
                ChatConversation.student_id == student_id,
                ChatConversation.is_active == True,
                ChatConversation.student_unread_count > 0
            ).all()
            
            updates = []
            for conv in conversations:
                updates.append({
                    'teacher_id': conv.teacher_id,
                    'unread_count': conv.student_unread_count,
                    'last_message_at': conv.last_message_at
                })
                
            return jsonify({'success': True, 'updates': updates})
        except Exception as e:
            logger.error(f"Student chat updates error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            session_db.close()
