"""
Library Management Helper Functions
Business logic for library operations
"""

from datetime import datetime, date, timedelta
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session
from library_models import (
    LibraryBook, LibraryCategory, LibraryIssue, LibrarySettings,
    BookStatusEnum, IssueStatusEnum, BookConditionEnum
)
from models import Student
from decimal import Decimal
import re


# ===== ISSUE NUMBER GENERATION =====

def generate_issue_number(session: Session, tenant_id: int) -> str:
    """
    Generate unique issue number in format: ISS-YYYYMM-XXXXX
    Example: ISS-202511-00001
    """
    now = datetime.now()
    prefix = f"ISS-{now.strftime('%Y%m')}"
    
    # Get last issue number for current month
    last_issue = session.query(LibraryIssue).filter(
        LibraryIssue.tenant_id == tenant_id,
        LibraryIssue.issue_number.like(f"{prefix}-%")
    ).order_by(LibraryIssue.issue_number.desc()).first()
    
    if last_issue:
        # Extract sequence number and increment
        match = re.search(r'-(\d+)$', last_issue.issue_number)
        if match:
            sequence = int(match.group(1)) + 1
        else:
            sequence = 1
    else:
        sequence = 1
    
    return f"{prefix}-{sequence:05d}"


# ===== LIBRARY SETTINGS =====

def get_library_settings(session: Session, tenant_id: int) -> LibrarySettings:
    """Get or create library settings for tenant"""
    settings = session.query(LibrarySettings).filter_by(tenant_id=tenant_id).first()
    
    if not settings:
        settings = LibrarySettings(
            tenant_id=tenant_id,
            max_books_per_student=3,
            issue_duration_days=14,
            fine_per_day=Decimal('5.00'),
            max_fine_amount=Decimal('500.00'),
            grace_period_days=0
        )
        session.add(settings)
        session.commit()
    
    return settings


# ===== BOOK MANAGEMENT =====

def add_book(session: Session, tenant_id: int, book_data: dict) -> LibraryBook:
    """Add a new book to library"""
    book = LibraryBook(
        tenant_id=tenant_id,
        **book_data
    )
    
    # Set available copies equal to total copies
    if book.total_copies and not book.available_copies:
        book.available_copies = book.total_copies
    
    session.add(book)
    session.commit()
    session.refresh(book)
    
    return book


def bulk_add_books(session: Session, tenant_id: int, books_data: list) -> dict:
    """
    Bulk add books to library
    Returns: {'success': count, 'failed': count, 'errors': []}
    """
    success_count = 0
    failed_count = 0
    errors = []
    
    for idx, book_data in enumerate(books_data):
        try:
            # Check for duplicate accession number
            existing = session.query(LibraryBook).filter_by(
                tenant_id=tenant_id,
                accession_number=book_data.get('accession_number')
            ).first()
            
            if existing:
                errors.append(f"Row {idx + 1}: Accession number '{book_data.get('accession_number')}' already exists")
                failed_count += 1
                continue
            
            book = LibraryBook(tenant_id=tenant_id, **book_data)
            
            # Set available copies
            if book.total_copies and not book.available_copies:
                book.available_copies = book.total_copies
            
            session.add(book)
            success_count += 1
            
        except Exception as e:
            errors.append(f"Row {idx + 1}: {str(e)}")
            failed_count += 1
    
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        return {'success': 0, 'failed': len(books_data), 'errors': [f"Database error: {str(e)}"]}
    
    return {'success': success_count, 'failed': failed_count, 'errors': errors}


def update_book(session: Session, book_id: int, tenant_id: int, update_data: dict) -> LibraryBook:
    """Update book details"""
    book = session.query(LibraryBook).filter_by(id=book_id, tenant_id=tenant_id).first()
    
    if not book:
        raise ValueError("Book not found")
    
    for key, value in update_data.items():
        if hasattr(book, key):
            setattr(book, key, value)
    
    session.commit()
    session.refresh(book)
    
    return book


def delete_book(session: Session, book_id: int, tenant_id: int) -> bool:
    """Delete book (only if not issued)"""
    book = session.query(LibraryBook).filter_by(id=book_id, tenant_id=tenant_id).first()
    
    if not book:
        raise ValueError("Book not found")
    
    # Check if book has active issues
    active_issues = session.query(LibraryIssue).filter(
        LibraryIssue.book_id == book_id,
        LibraryIssue.status == IssueStatusEnum.ISSUED
    ).count()
    
    if active_issues > 0:
        raise ValueError("Cannot delete book with active issues")
    
    session.delete(book)
    session.commit()
    
    return True


def get_book_details(session: Session, book_id: int, tenant_id: int) -> dict:
    """Get comprehensive book details with issue history"""
    book = session.query(LibraryBook).filter_by(id=book_id, tenant_id=tenant_id).first()
    
    if not book:
        return None
    
    # Get issue history
    issues = session.query(LibraryIssue).filter_by(
        book_id=book_id,
        tenant_id=tenant_id
    ).order_by(LibraryIssue.issue_date.desc()).all()
    
    # Calculate statistics
    total_issues = len(issues)
    active_issues = sum(1 for i in issues if i.status == IssueStatusEnum.ISSUED)
    overdue_issues = sum(1 for i in issues if i.is_overdue)
    
    return {
        'book': book,
        'issues': issues,
        'stats': {
            'total_issues': total_issues,
            'active_issues': active_issues,
            'overdue_issues': overdue_issues
        }
    }


# ===== BOOK ISSUE MANAGEMENT =====

def can_issue_book(session: Session, student_id: int, book_id: int, tenant_id: int) -> tuple:
    """
    Check if book can be issued to student
    Returns: (can_issue: bool, reason: str)
    """
    settings = get_library_settings(session, tenant_id)
    
    # Check if book exists and is available
    book = session.query(LibraryBook).filter_by(id=book_id, tenant_id=tenant_id).first()
    if not book:
        return False, "Book not found"
    
    if book.available_copies <= 0:
        return False, "No copies available"
    
    if book.status != BookStatusEnum.AVAILABLE:
        return False, f"Book is {book.status.value}"
    
    # Check if student exists
    student = session.query(Student).filter_by(id=student_id, tenant_id=tenant_id).first()
    if not student:
        return False, "Student not found"
    
    # Check student's current issues
    current_issues = session.query(LibraryIssue).filter(
        LibraryIssue.student_id == student_id,
        LibraryIssue.tenant_id == tenant_id,
        LibraryIssue.status == IssueStatusEnum.ISSUED
    ).count()
    
    if current_issues >= settings.max_books_per_student:
        return False, f"Student has reached maximum limit ({settings.max_books_per_student} books)"
    
    # Check for unpaid fines
    unpaid_fines = session.query(LibraryIssue).filter(
        LibraryIssue.student_id == student_id,
        LibraryIssue.tenant_id == tenant_id,
        LibraryIssue.fine_amount > 0,
        LibraryIssue.fine_paid == False
    ).count()
    
    if unpaid_fines > 0:
        return False, "Student has unpaid fines"
    
    # Check if student already has this book
    has_book = session.query(LibraryIssue).filter(
        LibraryIssue.student_id == student_id,
        LibraryIssue.book_id == book_id,
        LibraryIssue.tenant_id == tenant_id,
        LibraryIssue.status == IssueStatusEnum.ISSUED
    ).first()
    
    if has_book:
        return False, "Student already has this book"
    
    return True, "Can issue"


def issue_book(session: Session, student_id: int, book_id: int, tenant_id: int, 
               issued_by_user_id: int = None, issue_remarks: str = None, 
               custom_due_date: date = None) -> LibraryIssue:
    """Issue a book to student"""
    
    # Validation
    can_issue, reason = can_issue_book(session, student_id, book_id, tenant_id)
    if not can_issue:
        raise ValueError(reason)
    
    settings = get_library_settings(session, tenant_id)
    book = session.query(LibraryBook).filter_by(id=book_id, tenant_id=tenant_id).first()
    
    # Use custom due date if provided, otherwise use default from settings
    if custom_due_date:
        due_date = custom_due_date
    else:
        due_date = date.today() + timedelta(days=settings.issue_duration_days)
    
    # Create issue record
    issue = LibraryIssue(
        tenant_id=tenant_id,
        book_id=book_id,
        student_id=student_id,
        issue_number=generate_issue_number(session, tenant_id),
        issue_date=date.today(),
        due_date=due_date,
        status=IssueStatusEnum.ISSUED,
        issue_condition=book.condition,
        issued_by_user_id=issued_by_user_id,
        issue_remarks=issue_remarks
    )
    
    session.add(issue)
    
    # Update book availability
    book.available_copies -= 1
    if book.available_copies == 0:
        book.status = BookStatusEnum.ISSUED
    
    session.commit()
    session.refresh(issue)
    
    return issue


def return_book(session: Session, issue_id: int, tenant_id: int, 
                return_condition: BookConditionEnum = None,
                returned_by_user_id: int = None,
                return_remarks: str = None) -> LibraryIssue:
    """Process book return"""
    
    issue = session.query(LibraryIssue).filter_by(id=issue_id, tenant_id=tenant_id).first()
    
    if not issue:
        raise ValueError("Issue record not found")
    
    if issue.status != IssueStatusEnum.ISSUED:
        raise ValueError(f"Book is not currently issued (Status: {issue.status.value})")
    
    book = session.query(LibraryBook).filter_by(id=issue.book_id, tenant_id=tenant_id).first()
    settings = get_library_settings(session, tenant_id)
    
    # Update issue record
    issue.return_date = date.today()
    issue.return_condition = return_condition or issue.issue_condition
    issue.returned_by_user_id = returned_by_user_id
    issue.return_remarks = return_remarks
    
    # Calculate fine if overdue
    if issue.due_date < date.today():
        days_late = (date.today() - issue.due_date).days
        
        # Apply grace period
        if days_late > settings.grace_period_days:
            chargeable_days = days_late - settings.grace_period_days
            fine = min(
                Decimal(chargeable_days) * settings.fine_per_day,
                settings.max_fine_amount
            )
            issue.fine_amount = fine
            issue.status = IssueStatusEnum.OVERDUE
        else:
            issue.status = IssueStatusEnum.RETURNED
    else:
        issue.status = IssueStatusEnum.RETURNED
    
    # Update book availability
    book.available_copies += 1
    if book.status == BookStatusEnum.ISSUED:
        book.status = BookStatusEnum.AVAILABLE
    
    # Update book condition if damaged
    if return_condition and return_condition in [BookConditionEnum.DAMAGED, BookConditionEnum.POOR]:
        book.condition = return_condition
        if return_condition == BookConditionEnum.DAMAGED:
            book.status = BookStatusEnum.DAMAGED
    
    session.commit()
    session.refresh(issue)
    
    return issue


def renew_book(session: Session, issue_id: int, tenant_id: int) -> LibraryIssue:
    """Renew book issue (extend due date)"""
    
    issue = session.query(LibraryIssue).filter_by(id=issue_id, tenant_id=tenant_id).first()
    
    if not issue:
        raise ValueError("Issue record not found")
    
    if issue.status != IssueStatusEnum.ISSUED:
        raise ValueError("Only issued books can be renewed")
    
    # Check for unpaid fines
    if issue.fine_amount > 0 and not issue.fine_paid:
        raise ValueError("Cannot renew with unpaid fines")
    
    settings = get_library_settings(session, tenant_id)
    
    # Extend due date
    issue.due_date = date.today() + timedelta(days=settings.issue_duration_days)
    
    session.commit()
    session.refresh(issue)
    
    return issue


def pay_fine(session: Session, issue_id: int, tenant_id: int) -> LibraryIssue:
    """Mark fine as paid"""
    
    issue = session.query(LibraryIssue).filter_by(id=issue_id, tenant_id=tenant_id).first()
    
    if not issue:
        raise ValueError("Issue record not found")
    
    if issue.fine_amount <= 0:
        raise ValueError("No fine to pay")
    
    issue.fine_paid = True
    issue.fine_paid_date = date.today()
    
    session.commit()
    session.refresh(issue)
    
    return issue


# ===== REPORTS AND QUERIES =====

def get_available_books(session: Session, tenant_id: int, category_id: int = None, search: str = None):
    """Get list of available books"""
    query = session.query(LibraryBook).filter(
        LibraryBook.tenant_id == tenant_id,
        LibraryBook.available_copies > 0,
        LibraryBook.status == BookStatusEnum.AVAILABLE
    )
    
    if category_id:
        query = query.filter(LibraryBook.category_id == category_id)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                LibraryBook.title.like(search_pattern),
                LibraryBook.author.like(search_pattern),
                LibraryBook.accession_number.like(search_pattern),
                LibraryBook.isbn.like(search_pattern)
            )
        )
    
    return query.order_by(LibraryBook.title).all()


def get_issued_books(session: Session, tenant_id: int, student_id: int = None):
    """Get currently issued books"""
    query = session.query(LibraryIssue).filter(
        LibraryIssue.tenant_id == tenant_id,
        LibraryIssue.status == IssueStatusEnum.ISSUED
    )
    
    if student_id:
        query = query.filter(LibraryIssue.student_id == student_id)
    
    return query.order_by(LibraryIssue.issue_date.desc()).all()


def get_overdue_books(session: Session, tenant_id: int):
    """Get overdue book issues"""
    return session.query(LibraryIssue).filter(
        LibraryIssue.tenant_id == tenant_id,
        LibraryIssue.status == IssueStatusEnum.ISSUED,
        LibraryIssue.due_date < date.today()
    ).order_by(LibraryIssue.due_date).all()


def get_student_issue_history(session: Session, student_id: int, tenant_id: int):
    """Get complete issue history for a student"""
    return session.query(LibraryIssue).filter(
        LibraryIssue.student_id == student_id,
        LibraryIssue.tenant_id == tenant_id
    ).order_by(LibraryIssue.issue_date.desc()).all()


def get_library_statistics(session: Session, tenant_id: int) -> dict:
    """Get overall library statistics"""
    
    total_books = session.query(func.sum(LibraryBook.total_copies)).filter(
        LibraryBook.tenant_id == tenant_id
    ).scalar() or 0
    
    available_books = session.query(func.sum(LibraryBook.available_copies)).filter(
        LibraryBook.tenant_id == tenant_id
    ).scalar() or 0
    
    issued_books = session.query(LibraryIssue).filter(
        LibraryIssue.tenant_id == tenant_id,
        LibraryIssue.status == IssueStatusEnum.ISSUED
    ).count()
    
    overdue_books = session.query(LibraryIssue).filter(
        LibraryIssue.tenant_id == tenant_id,
        LibraryIssue.status == IssueStatusEnum.ISSUED,
        LibraryIssue.due_date < date.today()
    ).count()
    
    total_fines = session.query(func.sum(LibraryIssue.fine_amount)).filter(
        LibraryIssue.tenant_id == tenant_id,
        LibraryIssue.fine_paid == False
    ).scalar() or Decimal('0.00')
    
    unique_titles = session.query(LibraryBook).filter(
        LibraryBook.tenant_id == tenant_id
    ).count()
    
    return {
        'total_books': int(total_books),
        'available_books': int(available_books),
        'issued_books': issued_books,
        'overdue_books': overdue_books,
        'total_unpaid_fines': float(total_fines),
        'unique_titles': unique_titles
    }
