"""
Library Management Routes
Routes for book management, issue tracking, and library operations
"""

from flask import request, jsonify, render_template, redirect, url_for, flash, g
from flask_login import current_user
from sqlalchemy import or_, func
from datetime import datetime, date, timedelta
from decimal import Decimal
import csv
import io

from db_single import get_session
from library_models import (
    LibraryBook, LibraryCategory, LibraryIssue, LibrarySettings,
    BookStatusEnum, IssueStatusEnum, BookConditionEnum
)
from library_helpers import (
    add_book, bulk_add_books, update_book, delete_book, get_book_details,
    can_issue_book, issue_book, return_book, renew_book, pay_fine,
    get_available_books, get_issued_books, get_overdue_books,
    get_student_issue_history, get_library_statistics, get_library_settings
)
from models import Student, User


def create_library_routes(school_blueprint, require_school_auth):
    """Add library management routes to school blueprint"""
    
    # ===== DASHBOARD =====
    @school_blueprint.route('/<tenant_slug>/library')
    @require_school_auth
    def library_dashboard(tenant_slug):
        """Library dashboard with statistics"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            stats = get_library_statistics(session, tenant_id)
            
            # Recent issues
            recent_issues = session.query(LibraryIssue).filter(
                LibraryIssue.tenant_id == tenant_id
            ).order_by(LibraryIssue.issue_date.desc()).limit(10).all()
            
            # Overdue books
            overdue = get_overdue_books(session, tenant_id)[:10]
            
            return render_template('akademi/library/library_dashboard.html',
                                 school=g.current_tenant,
                                 stats=stats,
                                 recent_issues=recent_issues,
                                 overdue=overdue,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== CATEGORIES =====
    @school_blueprint.route('/<tenant_slug>/library/categories')
    @require_school_auth
    def library_categories(tenant_slug):
        """List all library categories"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            categories = session.query(LibraryCategory).filter_by(
                tenant_id=tenant_id
            ).order_by(LibraryCategory.name).all()
            
            return render_template('akademi/library/library_categories.html',
                                 school=g.current_tenant,
                                 categories=categories,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    @school_blueprint.route('/<tenant_slug>/library/categories/add', methods=['GET', 'POST'])
    @require_school_auth
    def add_library_category(tenant_slug):
        """Add new category"""
        if request.method == 'POST':
            session = get_session()
            try:
                tenant_id = g.current_tenant.id
                
                category = LibraryCategory(
                    tenant_id=tenant_id,
                    name=request.form.get('name'),
                    description=request.form.get('description'),
                    is_active=True
                )
                
                session.add(category)
                session.commit()
                
                flash('Category added successfully!', 'success')
                return redirect(url_for('school.library_categories', tenant_slug=tenant_slug))
            except Exception as e:
                session.rollback()
                flash(f'Error: {str(e)}', 'danger')
            finally:
                session.close()
        
        return render_template('akademi/library/add_library_category.html', school=g.current_tenant, tenant_slug=tenant_slug)
    
    @school_blueprint.route('/<tenant_slug>/library/categories/delete/<int:category_id>', methods=['POST'])
    @require_school_auth
    def delete_library_category(tenant_slug, category_id):
        """Delete a library category"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Get the category
            category = session.query(LibraryCategory).filter_by(
                id=category_id, tenant_id=tenant_id
            ).first()
            
            if not category:
                flash('Category not found', 'danger')
                return redirect(url_for('school.library_categories', tenant_slug=tenant_slug))
            
            # Check if any books are using this category
            books_count = session.query(LibraryBook).filter_by(
                category_id=category_id, tenant_id=tenant_id
            ).count()
            
            if books_count > 0:
                flash(f'Cannot delete category. {books_count} book(s) are using this category.', 'warning')
                return redirect(url_for('school.library_categories', tenant_slug=tenant_slug))
            
            # Delete the category
            session.delete(category)
            session.commit()
            
            flash(f'Category "{category.name}" deleted successfully!', 'success')
            return redirect(url_for('school.library_categories', tenant_slug=tenant_slug))
            
        except Exception as e:
            session.rollback()
            flash(f'Error deleting category: {str(e)}', 'danger')
            return redirect(url_for('school.library_categories', tenant_slug=tenant_slug))
        finally:
            session.close()
    
    # ===== BOOKS =====
    @school_blueprint.route('/<tenant_slug>/library/books')
    @require_school_auth
    def library_books(tenant_slug):
        """List all books"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Filters
            category_id = request.args.get('category_id', type=int)
            status = request.args.get('status')
            search = request.args.get('search', '').strip()
            
            query = session.query(LibraryBook).filter_by(tenant_id=tenant_id)
            
            if category_id:
                query = query.filter_by(category_id=category_id)
            
            if status:
                query = query.filter_by(status=status)
            
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
            
            books = query.order_by(LibraryBook.title).all()
            categories = session.query(LibraryCategory).filter_by(
                tenant_id=tenant_id, is_active=True
            ).all()
            
            return render_template('akademi/library/library_books.html',
                                 school=g.current_tenant,
                                 books=books,
                                 categories=categories,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    @school_blueprint.route('/<tenant_slug>/library/books/add', methods=['GET', 'POST'])
    @require_school_auth
    def add_library_book(tenant_slug):
        """Add single book"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            if request.method == 'POST':
                try:
                    book_data = {
                        'accession_number': request.form.get('accession_number'),
                        'isbn': request.form.get('isbn') or None,
                        'title': request.form.get('title'),
                        'author': request.form.get('author'),
                        'publisher': request.form.get('publisher') or None,
                        'publication_year': int(request.form.get('publication_year')) if request.form.get('publication_year') else None,
                        'edition': request.form.get('edition') or None,
                        'language': request.form.get('language', 'English'),
                        'pages': int(request.form.get('pages')) if request.form.get('pages') else None,
                        'price': Decimal(request.form.get('price')) if request.form.get('price') else None,
                        'condition': request.form.get('condition', 'Good'),
                        'rack_number': request.form.get('rack_number') or None,
                        'total_copies': int(request.form.get('total_copies', 1)),
                        'available_copies': int(request.form.get('total_copies', 1)),
                        'category_id': int(request.form.get('category_id')) if request.form.get('category_id') else None,
                        'description': request.form.get('description') or None
                    }
                    
                    book = add_book(session, tenant_id, book_data)
                    flash(f'Book "{book.title}" added successfully!', 'success')
                    return redirect(url_for('school.library_books', tenant_slug=tenant_slug))
                    
                except Exception as e:
                    flash(f'Error adding book: {str(e)}', 'danger')
            
            categories = session.query(LibraryCategory).filter_by(
                tenant_id=tenant_id, is_active=True
            ).all()
            
            return render_template('akademi/library/add_library_book.html',
                                 school=g.current_tenant,
                                 categories=categories,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    @school_blueprint.route('/<tenant_slug>/library/books/bulk-add', methods=['GET', 'POST'])
    @require_school_auth
    def bulk_add_library_books(tenant_slug):
        """Bulk add books via CSV"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            if request.method == 'POST':
                if 'csv_file' not in request.files:
                    flash('No file uploaded!', 'danger')
                    return redirect(request.url)
                
                file = request.files['csv_file']
                
                if file.filename == '':
                    flash('No file selected!', 'danger')
                    return redirect(request.url)
                
                if not file.filename.endswith('.csv'):
                    flash('Please upload a CSV file!', 'danger')
                    return redirect(request.url)
                
                try:
                    # Read CSV
                    stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
                    csv_reader = csv.DictReader(stream)
                    
                    books_data = []
                    for row in csv_reader:
                        book_data = {
                            'accession_number': row.get('accession_number', '').strip(),
                            'isbn': row.get('isbn', '').strip() or None,
                            'title': row.get('title', '').strip(),
                            'author': row.get('author', '').strip(),
                            'publisher': row.get('publisher', '').strip() or None,
                            'publication_year': int(row.get('publication_year')) if row.get('publication_year', '').strip() else None,
                            'edition': row.get('edition', '').strip() or None,
                            'language': row.get('language', 'English').strip(),
                            'pages': int(row.get('pages')) if row.get('pages', '').strip() else None,
                            'price': Decimal(row.get('price')) if row.get('price', '').strip() else None,
                            'condition': row.get('condition', 'Good').strip(),
                            'rack_number': row.get('rack_number', '').strip() or None,
                            'total_copies': int(row.get('total_copies', 1)),
                            'available_copies': int(row.get('total_copies', 1)),
                            'description': row.get('description', '').strip() or None
                        }
                        
                        # Handle category by name
                        category_name = row.get('category', '').strip()
                        if category_name:
                            category = session.query(LibraryCategory).filter_by(
                                tenant_id=tenant_id, name=category_name
                            ).first()
                            book_data['category_id'] = category.id if category else None
                        else:
                            book_data['category_id'] = None
                        
                        books_data.append(book_data)
                    
                    # Bulk add
                    result = bulk_add_books(session, tenant_id, books_data)
                    
                    if result['success'] > 0:
                        flash(f"Successfully added {result['success']} books!", 'success')
                    
                    if result['failed'] > 0:
                        flash(f"Failed to add {result['failed']} books. Check errors below.", 'warning')
                        for error in result['errors']:
                            flash(error, 'danger')
                    
                    return redirect(url_for('school.library_books', tenant_slug=tenant_slug))
                    
                except Exception as e:
                    flash(f'Error processing CSV: {str(e)}', 'danger')
            
            return render_template('akademi/library/bulk_add_library_books.html', school=g.current_tenant, tenant_slug=tenant_slug)
        finally:
            session.close()
    
    @school_blueprint.route('/<tenant_slug>/library/books/<int:book_id>')
    @require_school_auth
    def view_library_book(tenant_slug, book_id):
        """View book details"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            book_details = get_book_details(session, book_id, tenant_id)
            
            if not book_details:
                flash('Book not found!', 'danger')
                return redirect(url_for('school.library_books', tenant_slug=tenant_slug))
            
            return render_template('akademi/library/view_library_book.html',
                                 school=g.current_tenant,
                                 book=book_details['book'],
                                 issues=book_details['issues'],
                                 stats=book_details['stats'],
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    @school_blueprint.route('/<tenant_slug>/library/books/<int:book_id>/edit', methods=['GET', 'POST'])
    @require_school_auth
    def edit_library_book(tenant_slug, book_id):
        """Edit book details"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            book = session.query(LibraryBook).filter_by(id=book_id, tenant_id=tenant_id).first()
            
            if not book:
                flash('Book not found!', 'danger')
                return redirect(url_for('school.library_books', tenant_slug=tenant_slug))
            
            if request.method == 'POST':
                try:
                    update_data = {
                        'title': request.form.get('title'),
                        'author': request.form.get('author'),
                        'publisher': request.form.get('publisher') or None,
                        'publication_year': int(request.form.get('publication_year')) if request.form.get('publication_year') else None,
                        'edition': request.form.get('edition') or None,
                        'language': request.form.get('language', 'English'),
                        'pages': int(request.form.get('pages')) if request.form.get('pages') else None,
                        'price': Decimal(request.form.get('price')) if request.form.get('price') else None,
                        'condition': request.form.get('condition'),
                        'rack_number': request.form.get('rack_number') or None,
                        'category_id': int(request.form.get('category_id')) if request.form.get('category_id') else None,
                        'description': request.form.get('description') or None
                    }
                    
                    update_book(session, book_id, tenant_id, update_data)
                    flash('Book updated successfully!', 'success')
                    return redirect(url_for('school.view_library_book', tenant_slug=tenant_slug, book_id=book_id))
                    
                except Exception as e:
                    flash(f'Error updating book: {str(e)}', 'danger')
            
            categories = session.query(LibraryCategory).filter_by(
                tenant_id=tenant_id, is_active=True
            ).all()
            
            return render_template('akademi/library/edit_library_book.html',
                                 school=g.current_tenant,
                                 book=book,
                                 categories=categories,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    @school_blueprint.route('/<tenant_slug>/library/books/<int:book_id>/delete', methods=['POST'])
    @require_school_auth
    def delete_library_book(tenant_slug, book_id):
        """Delete book"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            delete_book(session, book_id, tenant_id)
            flash('Book deleted successfully!', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            session.close()
        
        return redirect(url_for('school.library_books', tenant_slug=tenant_slug))
    
    # ===== ISSUE MANAGEMENT =====
    @school_blueprint.route('/<tenant_slug>/library/issue', methods=['GET', 'POST'])
    @require_school_auth
    def issue_library_book(tenant_slug):
        """Issue book to student"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            settings = get_library_settings(session, tenant_id)
            
            if request.method == 'POST':
                try:
                    student_id = int(request.form.get('student_id'))
                    book_id = int(request.form.get('book_id'))
                    remarks = request.form.get('remarks')
                    due_date_str = request.form.get('due_date')
                    
                    # Parse custom due date if provided
                    custom_due_date = None
                    if due_date_str:
                        try:
                            custom_due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            flash('Invalid due date format', 'danger')
                            raise ValueError('Invalid due date format')
                    
                    # Validate inputs
                    if not student_id or not book_id:
                        flash('Please select both student and book', 'danger')
                    else:
                        issue = issue_book(
                            session, student_id, book_id, tenant_id,
                            issued_by_user_id=current_user.id if current_user.is_authenticated else None,
                            issue_remarks=remarks,
                            custom_due_date=custom_due_date
                        )
                        
                        flash(f'Book issued successfully! Issue Number: {issue.issue_number}', 'success')
                        return redirect(url_for('school.library_issued_books', tenant_slug=tenant_slug))
                    
                except ValueError as ve:
                    # Business logic errors (validation failures)
                    flash(f'{str(ve)}', 'warning')
                    session.rollback()
                except Exception as e:
                    # Technical errors
                    flash(f'Error issuing book: {str(e)}', 'danger')
                    session.rollback()
            
            # Get available books and students
            books = get_available_books(session, tenant_id)
            students = session.query(Student).filter_by(tenant_id=tenant_id).order_by(Student.full_name).all()
            
            # Calculate default due date
            default_due_date = (date.today() + timedelta(days=settings.issue_duration_days)).strftime('%Y-%m-%d')
            
            return render_template('akademi/library/issue_library_book.html',
                                 school=g.current_tenant,
                                 books=books,
                                 students=students,
                                 default_due_date=default_due_date,
                                 issue_duration_days=settings.issue_duration_days,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    @school_blueprint.route('/<tenant_slug>/library/issued')
    @require_school_auth
    def library_issued_books(tenant_slug):
        """View all issued books"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            student_id = request.args.get('student_id', type=int)
            issues = get_issued_books(session, tenant_id, student_id)
            
            return render_template('akademi/library/library_issued_books.html',
                                 school=g.current_tenant,
                                 issues=issues,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    @school_blueprint.route('/<tenant_slug>/library/return/<int:issue_id>', methods=['GET', 'POST'])
    @require_school_auth
    def return_library_book(tenant_slug, issue_id):
        """Return book"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            if request.method == 'POST':
                try:
                    condition = request.form.get('condition')
                    remarks = request.form.get('remarks')
                    
                    issue = return_book(
                        session, issue_id, tenant_id,
                        return_condition=BookConditionEnum[condition] if condition else None,
                        returned_by_user_id=current_user.id if current_user.is_authenticated else None,
                        return_remarks=remarks
                    )
                    
                    if issue.fine_amount > 0:
                        flash(f'Book returned! Fine charged: ₹{issue.fine_amount}', 'warning')
                    else:
                        flash('Book returned successfully!', 'success')
                    
                    return redirect(url_for('school.library_issued_books', tenant_slug=tenant_slug))
                    
                except Exception as e:
                    flash(f'Error: {str(e)}', 'danger')
            
            issue = session.query(LibraryIssue).filter_by(id=issue_id, tenant_id=tenant_id).first()
            
            if not issue:
                flash('Issue record not found!', 'danger')
                return redirect(url_for('school.library_issued_books', tenant_slug=tenant_slug))
            
            return render_template('akademi/library/return_library_book.html',
                                 school=g.current_tenant,
                                 issue=issue,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    @school_blueprint.route('/<tenant_slug>/library/overdue')
    @require_school_auth
    def library_overdue_books(tenant_slug):
        """View overdue books"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            overdue = get_overdue_books(session, tenant_id)
            
            return render_template('akademi/library/library_overdue_books.html',
                                 school=g.current_tenant,
                                 overdue=overdue,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    @school_blueprint.route('/<tenant_slug>/library/student/<int:student_id>')
    @require_school_auth
    def student_library_history(tenant_slug, student_id):
        """View student's library history"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            student = session.query(Student).filter_by(id=student_id, tenant_id=tenant_id).first()
            if not student:
                flash('Student not found!', 'danger')
                return redirect(url_for('school.library_dashboard', tenant_slug=tenant_slug))
            
            history = get_student_issue_history(session, student_id, tenant_id)
            current_issues = get_issued_books(session, tenant_id, student_id)
            
            return render_template('akademi/library/student_library_history.html',
                                 school=g.current_tenant,
                                 student=student,
                                 history=history,
                                 current_issues=current_issues,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    @school_blueprint.route('/<tenant_slug>/library/students-history')
    @require_school_auth
    def students_issue_history(tenant_slug):
        """View all students with their issue history"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Get search parameter
            search = request.args.get('search', '').strip()
            
            # Query students with their total issue counts
            students_query = session.query(
                Student,
                func.count(LibraryIssue.id).label('total_issues')
            ).outerjoin(
                LibraryIssue, 
                (LibraryIssue.student_id == Student.id) & (LibraryIssue.tenant_id == tenant_id)
            ).filter(
                Student.tenant_id == tenant_id
            ).group_by(Student.id)
            
            # Apply search filter
            if search:
                students_query = students_query.filter(
                    or_(
                        Student.full_name.ilike(f'%{search}%'),
                        Student.admission_number.ilike(f'%{search}%')
                    )
                )
            
            students_result = students_query.order_by(Student.full_name).all()
            
            # Process results to calculate current issues for each student
            processed_data = []
            for student, total_issues in students_result:
                # Count current issued books
                current_count = session.query(func.count(LibraryIssue.id)).filter(
                    LibraryIssue.student_id == student.id,
                    LibraryIssue.tenant_id == tenant_id,
                    LibraryIssue.status == IssueStatusEnum.ISSUED
                ).scalar() or 0
                
                processed_data.append((student, total_issues or 0, current_count))
            
            return render_template('akademi/library/students_issue_history.html',
                                 school=g.current_tenant,
                                 students_data=processed_data,
                                 search=search,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    @school_blueprint.route('/<tenant_slug>/library/settings', methods=['GET', 'POST'])
    @require_school_auth
    def library_settings(tenant_slug):
        """Library settings"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            settings = get_library_settings(session, tenant_id)
            
            if request.method == 'POST':
                try:
                    settings.max_books_per_student = int(request.form.get('max_books_per_student', 3))
                    settings.issue_duration_days = int(request.form.get('issue_duration_days', 14))
                    settings.fine_per_day = Decimal(request.form.get('fine_per_day', '5.00'))
                    settings.max_fine_amount = Decimal(request.form.get('max_fine_amount', '500.00'))
                    settings.grace_period_days = int(request.form.get('grace_period_days', 0))
                    
                    session.commit()
                    flash('Settings updated successfully!', 'success')
                    
                except Exception as e:
                    session.rollback()
                    flash(f'Error: {str(e)}', 'danger')
            
            return render_template('akademi/library/library_settings.html',
                                 school=g.current_tenant,
                                 settings=settings,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
