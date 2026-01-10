"""
Home Dashboard Routes - Unified Dashboard with Real Data
"""
from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, g
from flask_login import login_required, current_user
from sqlalchemy import func, and_, extract, desc
from datetime import datetime, date, timedelta
from functools import wraps
from models import (
    Student, Class, AcademicSession, Exam, StudentMark, 
    StudentAttendance, StudentAttendanceSummary, StudentHoliday,
    StudentAttendanceStatusEnum, StudentStatusEnum, User,
    Tenant, ExamSubject
)
from teacher_models import Teacher, TeacherAttendance, AttendanceStatusEnum as TeacherAttendanceStatusEnum, EmployeeStatusEnum, TeacherSalary
from fee_models import FeeReceipt
from db_single import get_session
import json
import logging

logger = logging.getLogger(__name__)

home_bp = Blueprint('home', __name__)

def require_school_auth(f):
    """Decorator to require school authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'current_tenant'):
            return redirect('/admin/')
        
        if not current_user.is_authenticated:
            tenant_slug = kwargs.get('tenant_slug', g.current_tenant.slug)
            from flask import url_for
            return redirect(f'/{tenant_slug}/login')
        
        # Check if user belongs to current tenant
        if current_user.tenant_id != g.current_tenant.id:
            flash('Access denied - wrong school', 'error')
            tenant_slug = kwargs.get('tenant_slug', g.current_tenant.slug)
            return redirect(f'/{tenant_slug}/login')
        
        return f(*args, **kwargs)
    
    return decorated_function

@home_bp.route('/<tenant_slug>/home')
@require_school_auth
def home_dashboard(tenant_slug):
    """Unified Home Dashboard with real data"""
    session_db = get_session()
    try:
        # Get school info
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        if not school:
            return "School not found", 404
        
        tenant_id = school.id
        today = date.today()
        
        # ===== BASIC STATISTICS =====
        # Get current academic session
        current_session = session_db.query(AcademicSession).filter(
            and_(
                AcademicSession.tenant_id == tenant_id,
                AcademicSession.is_current == True
            )
        ).first()
        
        # Total active students
        total_students = session_db.query(func.count(Student.id)).filter(
            and_(
                Student.tenant_id == tenant_id,
                Student.status == StudentStatusEnum.ACTIVE
            )
        ).scalar() or 0
        
        # Total active teachers
        total_teachers = session_db.query(func.count(Teacher.id)).filter(
            and_(
                Teacher.tenant_id == tenant_id,
                Teacher.employee_status == EmployeeStatusEnum.ACTIVE
            )
        ).scalar() or 0
        
        # Total active classes
        total_classes = session_db.query(func.count(Class.id)).filter(
            and_(
                Class.tenant_id == tenant_id,
                Class.is_active == True
            )
        ).scalar() or 0
        
        # Total upcoming exams
        upcoming_exams_count = session_db.query(func.count(Exam.id)).filter(
            and_(
                Exam.tenant_id == tenant_id,
                Exam.start_date >= today,
                Exam.is_active == True
            )
        ).scalar() or 0

        # Total Events (Upcoming Holidays)
        total_events = session_db.query(func.count(StudentHoliday.id)).filter(
            and_(
                StudentHoliday.tenant_id == tenant_id,
                StudentHoliday.end_date >= today
            )
        ).scalar() or 0

        # Total Foods (Placeholder)
        total_foods = 50
        
        # ===== TODAY'S STUDENT ATTENDANCE =====
        today_student_attendance = session_db.query(
            StudentAttendance.status,
            func.count(StudentAttendance.id)
        ).filter(
            and_(
                StudentAttendance.tenant_id == tenant_id,
                StudentAttendance.attendance_date == today
            )
        ).group_by(StudentAttendance.status).all()
        
        student_attendance_stats = {
            'present': 0,
            'absent': 0,
            'half_day': 0,
            'on_leave': 0,
            'total': 0,
            'percentage': 0
        }
        
        for status, count in today_student_attendance:
            if status == StudentAttendanceStatusEnum.PRESENT:
                student_attendance_stats['present'] = count
            elif status == StudentAttendanceStatusEnum.ABSENT:
                student_attendance_stats['absent'] = count
            elif status == StudentAttendanceStatusEnum.HALF_DAY:
                student_attendance_stats['half_day'] = count
            elif status == StudentAttendanceStatusEnum.ON_LEAVE:
                student_attendance_stats['on_leave'] = count
            student_attendance_stats['total'] += count
        
        if student_attendance_stats['total'] > 0:
            student_attendance_stats['percentage'] = round(
                (student_attendance_stats['present'] / student_attendance_stats['total']) * 100, 2
            )
        
        # ===== TODAY'S TEACHER ATTENDANCE =====
        today_teacher_attendance = session_db.query(
            TeacherAttendance.status,
            func.count(TeacherAttendance.id)
        ).filter(
            and_(
                TeacherAttendance.tenant_id == tenant_id,
                TeacherAttendance.attendance_date == today
            )
        ).group_by(TeacherAttendance.status).all()
        
        teacher_attendance_stats = {
            'present': 0,
            'absent': 0,
            'half_day': 0,
            'on_leave': 0,
            'total': 0,
            'percentage': 0
        }
        
        for status, count in today_teacher_attendance:
            if status == TeacherAttendanceStatusEnum.PRESENT:
                teacher_attendance_stats['present'] = count
            elif status == TeacherAttendanceStatusEnum.ABSENT:
                teacher_attendance_stats['absent'] = count
            elif status == TeacherAttendanceStatusEnum.HALF_DAY:
                teacher_attendance_stats['half_day'] = count
            elif status == TeacherAttendanceStatusEnum.ON_LEAVE:
                teacher_attendance_stats['on_leave'] = count
            teacher_attendance_stats['total'] += count
        
        if teacher_attendance_stats['total'] > 0:
            teacher_attendance_stats['percentage'] = round(
                (teacher_attendance_stats['present'] / teacher_attendance_stats['total']) * 100, 2
            )
        
        # ===== UPCOMING EXAMS =====
        upcoming_exams = session_db.query(Exam).filter(
            and_(
                Exam.tenant_id == tenant_id,
                Exam.start_date >= today,
                Exam.is_active == True
            )
        ).order_by(Exam.start_date).limit(5).all()
        
        # ===== UPCOMING HOLIDAYS =====
        upcoming_holidays = session_db.query(StudentHoliday).filter(
            and_(
                StudentHoliday.tenant_id == tenant_id,
                StudentHoliday.end_date >= today
            )
        ).order_by(StudentHoliday.start_date).limit(5).all()
        
        # ===== MONTHLY ATTENDANCE TREND (Last 6 months) =====
        six_months_ago = today - timedelta(days=180)
        monthly_attendance = session_db.query(
            StudentAttendanceSummary.month,
            StudentAttendanceSummary.year,
            func.avg(StudentAttendanceSummary.attendance_percentage)
        ).filter(
            and_(
                StudentAttendanceSummary.tenant_id == tenant_id,
                StudentAttendanceSummary.year >= six_months_ago.year
            )
        ).group_by(
            StudentAttendanceSummary.year,
            StudentAttendanceSummary.month
        ).order_by(
            StudentAttendanceSummary.year,
            StudentAttendanceSummary.month
        ).all()
        
        # Format for chart
        attendance_months = []
        attendance_percentages = []
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        for month, year, avg_percentage in monthly_attendance:
            attendance_months.append(f"{month_names[month-1]} {year}")
            attendance_percentages.append(float(avg_percentage) if avg_percentage else 0)
        
        # ===== CLASS-WISE STUDENT DISTRIBUTION =====
        class_distribution = session_db.query(
            Class.class_name,
            Class.section,
            func.count(Student.id)
        ).join(
            Student, Student.class_id == Class.id
        ).filter(
            and_(
                Class.tenant_id == tenant_id,
                Class.is_active == True,
                Student.status == StudentStatusEnum.ACTIVE
            )
        ).group_by(
            Class.class_name,
            Class.section
        ).order_by(
            Class.class_name,
            Class.section
        ).all()
        
        # Format for chart
        class_labels = []
        class_counts = []
        for class_name, section, count in class_distribution:
            class_labels.append(f"{class_name}-{section}")
            class_counts.append(count)
        
        # ===== RECENT STUDENTS (Last 5 registered) =====
        recent_students = session_db.query(Student).filter(
            Student.tenant_id == tenant_id
        ).order_by(desc(Student.created_at)).limit(5).all()
        
        # ===== RECENT TEACHERS (Last 5 registered) =====
        recent_teachers = session_db.query(Teacher).filter(
            Teacher.tenant_id == tenant_id
        ).order_by(desc(Teacher.created_at)).limit(5).all()
        
        # ===== EXAM RESULTS STATISTICS =====
        if current_session:
            recent_exam = session_db.query(Exam).filter(
                and_(
                    Exam.tenant_id == tenant_id,
                    Exam.session_id == current_session.id,
                    Exam.end_date < today
                )
            ).order_by(desc(Exam.end_date)).first()
            
            exam_stats = None
            if recent_exam:
                # Calculate pass/fail statistics
                total_marks = session_db.query(func.count(StudentMark.id)).filter(
                    and_(
                        StudentMark.tenant_id == tenant_id,
                        StudentMark.exam_id == recent_exam.id
                    )
                ).scalar() or 0
                
                # Get exam subjects to find pass marks
                exam_subjects = session_db.query(ExamSubject).filter(
                    ExamSubject.exam_id == recent_exam.id
                ).all()
                
                exam_stats = {
                    'exam_name': recent_exam.exam_name,
                    'total_marks_entered': total_marks
                }
        else:
            exam_stats = None

        # ===== FINANCE: SCHOOL PERFORMANCE (REVENUE) =====
        # This Week vs Last Week
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        start_of_last_week = start_of_week - timedelta(days=7)
        end_of_last_week = start_of_last_week + timedelta(days=6)
        
        this_week_revenue = session_db.query(func.sum(FeeReceipt.amount_paid)).filter(
            and_(
                FeeReceipt.tenant_id == tenant_id,
                FeeReceipt.payment_date >= start_of_week,
                FeeReceipt.payment_date <= end_of_week
            )
        ).scalar() or 0
        
        last_week_revenue = session_db.query(func.sum(FeeReceipt.amount_paid)).filter(
            and_(
                FeeReceipt.tenant_id == tenant_id,
                FeeReceipt.payment_date >= start_of_last_week,
                FeeReceipt.payment_date <= end_of_last_week
            )
        ).scalar() or 0
        
        # Daily Revenue for Chart (Last 30 days)
        thirty_days_ago = today - timedelta(days=30)
        daily_revenue = session_db.query(
            FeeReceipt.payment_date,
            func.sum(FeeReceipt.amount_paid)
        ).filter(
            and_(
                FeeReceipt.tenant_id == tenant_id,
                FeeReceipt.payment_date >= thirty_days_ago
            )
        ).group_by(FeeReceipt.payment_date).all()
        
        revenue_dates = []
        revenue_values = []
        # Fill in missing dates with 0
        current_date = thirty_days_ago
        revenue_dict = {r[0]: r[1] for r in daily_revenue}
        
        while current_date <= today:
            revenue_dates.append(current_date.strftime('%Y-%m-%d'))
            revenue_values.append(float(revenue_dict.get(current_date, 0)))
            current_date += timedelta(days=1)
            
        # ===== FINANCE: SCHOOL OVERVIEW (REVENUE VS EXPENSES) =====
        # Monthly Revenue vs Expenses (Last 12 months)
        # Expenses = Total Active Teacher Salaries (Estimated)
        
        total_monthly_salary_expense = session_db.query(func.sum(TeacherSalary.net_salary)).join(
            Teacher, Teacher.id == TeacherSalary.teacher_id
        ).filter(
            and_(
                TeacherSalary.tenant_id == tenant_id,
                TeacherSalary.is_active == True,
                Teacher.employee_status == EmployeeStatusEnum.ACTIVE
            )
        ).scalar() or 0
        
        # Monthly Revenue
        twelve_months_ago = today.replace(day=1) - timedelta(days=365)
        monthly_revenue = session_db.query(
            extract('year', FeeReceipt.payment_date).label('year'),
            extract('month', FeeReceipt.payment_date).label('month'),
            func.sum(FeeReceipt.amount_paid)
        ).filter(
            and_(
                FeeReceipt.tenant_id == tenant_id,
                FeeReceipt.payment_date >= twelve_months_ago
            )
        ).group_by('year', 'month').all()
        
        overview_labels = []
        overview_revenue = []
        overview_expenses = []
        
        # Process last 12 months
        for i in range(11, -1, -1):
            # Calculate date for i months ago
            # Simple approximation for month calculation
            target_month = today.month - i
            target_year = today.year
            while target_month <= 0:
                target_month += 12
                target_year -= 1
                
            month_year = f"{month_names[target_month-1]} {target_year}"
            overview_labels.append(month_year)
            
            # Find revenue for this month
            rev = next((r[2] for r in monthly_revenue if r[0] == target_year and r[1] == target_month), 0)
            overview_revenue.append(float(rev))
            overview_expenses.append(float(total_monthly_salary_expense)) # Assuming constant expense
        
        return render_template('akademi/home_dashboard.html',
                             school=school,
                             current_user=current_user,
                             current_session=current_session,
                             # Statistics
                             total_students=total_students,
                             total_teachers=total_teachers,
                             total_classes=total_classes,
                             upcoming_exams_count=upcoming_exams_count,
                             total_events=total_events,
                             total_foods=total_foods,
                             # Attendance
                             student_attendance=student_attendance_stats,
                             teacher_attendance=teacher_attendance_stats,
                             # Lists
                             upcoming_exams=upcoming_exams,
                             upcoming_holidays=upcoming_holidays,
                             recent_students=recent_students,
                             recent_teachers=recent_teachers,
                             # Charts data
                             attendance_months=json.dumps(attendance_months),
                             attendance_percentages=json.dumps(attendance_percentages),
                             class_labels=json.dumps(class_labels),
                             class_counts=json.dumps(class_counts),
                             # Finance Data
                             this_week_revenue=this_week_revenue,
                             last_week_revenue=last_week_revenue,
                             revenue_dates=json.dumps(revenue_dates),
                             revenue_values=json.dumps(revenue_values),
                             overview_labels=json.dumps(overview_labels),
                             overview_revenue=json.dumps(overview_revenue),
                             overview_expenses=json.dumps(overview_expenses),
                             # Exam stats
                             exam_stats=exam_stats,
                             today=today)
                             
    except Exception as e:
        logger.error(f"Home dashboard error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        return f"Error loading dashboard: {str(e)}", 500
    finally:
        session_db.close()


@home_bp.route('/<tenant_slug>/home/api/attendance-trend')
@require_school_auth
def get_attendance_trend(tenant_slug):
    """API endpoint for attendance trend data"""
    session_db = get_session()
    try:
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        if not school:
            return jsonify({'error': 'School not found'}), 404
        
        tenant_id = school.id
        today = date.today()
        six_months_ago = today - timedelta(days=180)
        
        monthly_attendance = session_db.query(
            StudentAttendanceSummary.month,
            StudentAttendanceSummary.year,
            func.avg(StudentAttendanceSummary.attendance_percentage)
        ).filter(
            and_(
                StudentAttendanceSummary.tenant_id == tenant_id,
                StudentAttendanceSummary.year >= six_months_ago.year
            )
        ).group_by(
            StudentAttendanceSummary.year,
            StudentAttendanceSummary.month
        ).order_by(
            StudentAttendanceSummary.year,
            StudentAttendanceSummary.month
        ).all()
        
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        data = {
            'labels': [f"{month_names[month-1]} {year}" for month, year, _ in monthly_attendance],
            'values': [float(avg_percentage) if avg_percentage else 0 for _, _, avg_percentage in monthly_attendance]
        }
        
        return jsonify(data)
    except Exception as e:
        logger.error(f"Attendance trend API error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session_db.close()
