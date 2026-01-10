"""
Finance Routes for School ERP
Extracted from school_routes_dynamic.py
"""

from flask import render_template, request, redirect, url_for, flash, g, jsonify
from flask_login import current_user
from sqlalchemy import func, extract, or_
from datetime import datetime, date, timedelta
import logging
from fee_models import FeeReceipt, StudentFee, FeeStatusEnum, PaymentModeEnum
from db_single import get_session
from models import Tenant, Student, AcademicSession
from teacher_models import Teacher
from expense_models import Expense, Budget, RecurringExpense, ExpenseCategoryEnum, PaymentMethodEnum, ExpenseStatusEnum

logger = logging.getLogger(__name__)


def register_finance_routes(school_bp, require_school_auth):
    """Register all finance routes to the school blueprint"""
    @school_bp.route('/<tenant_slug>/finance')
    @require_school_auth
    def finance(tenant_slug):
        """Finance dashboard with real data"""
        session_db = get_session()
        try:
            from sqlalchemy import func, extract
            from datetime import date, timedelta
            from expense_models import Expense, Budget, ExpenseStatusEnum, ExpenseCategoryEnum
            from fee_models import FeeReceipt, StudentFee, FeeStatusEnum, PaymentModeEnum
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            today = date.today()
            current_month = today.month
            current_year = today.year
            
            # Get current academic session
            from models import AcademicSession
            current_session = session_db.query(AcademicSession).filter_by(
                tenant_id=school.id, is_current=True
            ).first()
            
            # ===== STUDENT & TEACHER COUNTS =====
            total_students = session_db.query(func.count(Student.id)).filter(
                Student.tenant_id == school.id,
                Student.status == 'Active'
            ).scalar() or 0
            
            total_teachers = session_db.query(func.count(Teacher.id)).filter(
                Teacher.tenant_id == school.id,
                Teacher.employee_status == 'Active'
            ).scalar() or 0
            
            # ===== FEE COLLECTION STATS =====
            # Total fee collected this month
            monthly_fee_collection = session_db.query(func.sum(FeeReceipt.amount_paid)).filter(
                FeeReceipt.tenant_id == school.id,
                FeeReceipt.status == 'Verified',
                extract('month', FeeReceipt.receipt_date) == current_month,
                extract('year', FeeReceipt.receipt_date) == current_year
            ).scalar() or 0
            
            # Total fee collected this year
            yearly_fee_collection = session_db.query(func.sum(FeeReceipt.amount_paid)).filter(
                FeeReceipt.tenant_id == school.id,
                FeeReceipt.status == 'Verified',
                extract('year', FeeReceipt.receipt_date) == current_year
            ).scalar() or 0
            
            # Outstanding/Pending fees
            total_pending_fees = session_db.query(func.sum(StudentFee.balance_amount)).filter(
                StudentFee.tenant_id == school.id,
                StudentFee.status.in_(['Pending', 'Partially Paid', 'Overdue'])
            ).scalar() or 0
            
            # Fee collection by payment mode
            fee_by_mode = session_db.query(
                FeeReceipt.payment_mode,
                func.sum(FeeReceipt.amount_paid)
            ).filter(
                FeeReceipt.tenant_id == school.id,
                FeeReceipt.status == 'Verified',
                extract('year', FeeReceipt.receipt_date) == current_year
            ).group_by(FeeReceipt.payment_mode).all()
            
            cash_collection = 0
            online_collection = 0
            cheque_collection = 0
            for mode, amount in fee_by_mode:
                if mode and hasattr(mode, 'value'):
                    mode_val = mode.value
                else:
                    mode_val = str(mode) if mode else ''
                if mode_val == 'Cash':
                    cash_collection = float(amount or 0)
                elif mode_val in ['UPI', 'Bank Transfer', 'Online', 'Debit Card', 'Credit Card']:
                    online_collection += float(amount or 0)
                elif mode_val == 'Cheque':
                    cheque_collection = float(amount or 0)
            
            # ===== EXPENSE STATS =====
            # Total expenses this month
            monthly_expenses = session_db.query(func.sum(Expense.amount)).filter(
                Expense.tenant_id == school.id,
                extract('month', Expense.expense_date) == current_month,
                extract('year', Expense.expense_date) == current_year
            ).scalar() or 0
            
            # Total expenses this year
            yearly_expenses = session_db.query(func.sum(Expense.amount)).filter(
                Expense.tenant_id == school.id,
                extract('year', Expense.expense_date) == current_year
            ).scalar() or 0
            
            # Expenses by category (for chart)
            expense_by_category = session_db.query(
                Expense.category,
                func.sum(Expense.amount)
            ).filter(
                Expense.tenant_id == school.id,
                extract('year', Expense.expense_date) == current_year
            ).group_by(Expense.category).all()
            
            expense_categories = []
            expense_amounts = []
            for cat, amount in expense_by_category:
                if cat and hasattr(cat, 'value'):
                    expense_categories.append(cat.value)
                else:
                    expense_categories.append(str(cat) if cat else 'Other')
                expense_amounts.append(float(amount or 0))
            
            # ===== BUDGET STATS =====
            financial_year = f"{current_year}-{current_year+1}" if current_month >= 4 else f"{current_year-1}-{current_year}"
            
            total_budget = session_db.query(func.sum(Budget.allocated_amount)).filter(
                Budget.tenant_id == school.id,
                Budget.financial_year == financial_year,
                Budget.is_active == True
            ).scalar() or 0
            
            total_budget_spent = session_db.query(func.sum(Budget.spent_amount)).filter(
                Budget.tenant_id == school.id,
                Budget.financial_year == financial_year,
                Budget.is_active == True
            ).scalar() or 0
            
            # ===== MONTHLY TREND (Last 6 months) =====
            monthly_income_trend = []
            monthly_expense_trend = []
            month_labels = []
            
            for i in range(5, -1, -1):
                target_date = today - timedelta(days=i*30)
                m = target_date.month
                y = target_date.year
                month_labels.append(target_date.strftime('%b'))
                
                # Fee collection for month
                month_fee = session_db.query(func.sum(FeeReceipt.amount_paid)).filter(
                    FeeReceipt.tenant_id == school.id,
                    FeeReceipt.status == 'Verified',
                    extract('month', FeeReceipt.receipt_date) == m,
                    extract('year', FeeReceipt.receipt_date) == y
                ).scalar() or 0
                monthly_income_trend.append(float(month_fee))
                
                # Expenses for month
                month_exp = session_db.query(func.sum(Expense.amount)).filter(
                    Expense.tenant_id == school.id,
                    extract('month', Expense.expense_date) == m,
                    extract('year', Expense.expense_date) == y
                ).scalar() or 0
                monthly_expense_trend.append(float(month_exp))
            
            # ===== STUDENTS WITH UNPAID FEES =====
            unpaid_students = session_db.query(StudentFee).filter(
                StudentFee.tenant_id == school.id,
                StudentFee.status.in_(['Pending', 'Partially Paid', 'Overdue']),
                StudentFee.balance_amount > 0
            ).order_by(StudentFee.balance_amount.desc()).limit(10).all()
            
            # ===== RECENT TRANSACTIONS =====
            recent_receipts = session_db.query(FeeReceipt).filter(
                FeeReceipt.tenant_id == school.id
            ).order_by(FeeReceipt.created_at.desc()).limit(5).all()
            
            recent_expenses = session_db.query(Expense).filter(
                Expense.tenant_id == school.id
            ).order_by(Expense.created_at.desc()).limit(5).all()
            
            # Calculate school balance (income - expenses)
            school_balance = float(yearly_fee_collection or 0) - float(yearly_expenses or 0)
            
            return render_template('akademi/expenses/finance.html', 
                school=school,
                current_user=current_user,
                current_session=current_session,
                today=today,
                # Counts
                total_students=total_students,
                total_teachers=total_teachers,
                # Fee stats
                monthly_fee_collection=float(monthly_fee_collection or 0),
                yearly_fee_collection=float(yearly_fee_collection or 0),
                total_pending_fees=float(total_pending_fees or 0),
                cash_collection=cash_collection,
                online_collection=online_collection,
                cheque_collection=cheque_collection,
                # Expense stats
                monthly_expenses=float(monthly_expenses or 0),
                yearly_expenses=float(yearly_expenses or 0),
                expense_categories=expense_categories,
                expense_amounts=expense_amounts,
                # Budget stats
                total_budget=float(total_budget or 0),
                total_budget_spent=float(total_budget_spent or 0),
                financial_year=financial_year,
                # Trend data
                month_labels=month_labels,
                monthly_income_trend=monthly_income_trend,
                monthly_expense_trend=monthly_expense_trend,
                # Lists
                unpaid_students=unpaid_students,
                recent_receipts=recent_receipts,
                recent_expenses=recent_expenses,
                # Balance
                school_balance=school_balance
            )
                                 
        except Exception as e:
            logger.error(f"Finance error for {tenant_slug}: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading finance page', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    # ===== EXPENSE MANAGEMENT ROUTES =====
    
    @school_bp.route('/<tenant_slug>/expenses/dashboard')
    @require_school_auth
    def expense_dashboard(tenant_slug):
        """Expense management dashboard"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            from sqlalchemy import func, extract
            from datetime import date
            
            today = date.today()
            current_month = today.month
            current_year = today.year
            
            # Total expenses this month
            monthly_expenses = session_db.query(func.sum(Expense.amount)).filter(
                Expense.tenant_id == school.id,
                extract('month', Expense.expense_date) == current_month,
                extract('year', Expense.expense_date) == current_year
            ).scalar() or 0
            
            # Total expenses this year
            yearly_expenses = session_db.query(func.sum(Expense.amount)).filter(
                Expense.tenant_id == school.id,
                extract('year', Expense.expense_date) == current_year
            ).scalar() or 0
            
            # Pending approvals
            pending_count = session_db.query(func.count(Expense.id)).filter(
                Expense.tenant_id == school.id,
                Expense.status == ExpenseStatusEnum.PENDING
            ).scalar() or 0
            
            # Category-wise expenses (current month)
            category_expenses = session_db.query(
                Expense.category,
                func.sum(Expense.amount)
            ).filter(
                Expense.tenant_id == school.id,
                extract('month', Expense.expense_date) == current_month,
                extract('year', Expense.expense_date) == current_year
            ).group_by(Expense.category).all()
            
            # Recent expenses
            recent_expenses = session_db.query(Expense).filter(
                Expense.tenant_id == school.id
            ).order_by(Expense.created_at.desc()).limit(10).all()
            
            # Budget vs Actual
            budgets = session_db.query(Budget).filter(
                Budget.tenant_id == school.id,
                Budget.is_active == True
            ).all()
            
            return render_template('akademi/expenses/dashboard.html',
                                 school=school,
                                 current_user=current_user,
                                 monthly_expenses=monthly_expenses,
                                 yearly_expenses=yearly_expenses,
                                 pending_count=pending_count,
                                 category_expenses=category_expenses,
                                 recent_expenses=recent_expenses,
                                 budgets=budgets,
                                 today=today)
                                 
        except Exception as e:
            logger.error(f"Expense dashboard error for {tenant_slug}: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading expense dashboard', 'error')
            return redirect(url_for('school.finance', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/expenses/add', methods=['GET', 'POST'])
    @require_school_auth
    def add_expense(tenant_slug):
        """Add new expense"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            if request.method == 'POST':
                expense_date = datetime.strptime(request.form.get('expense_date'), '%Y-%m-%d').date()
                category = ExpenseCategoryEnum[request.form.get('category')]
                title = request.form.get('title')
                description = request.form.get('description', '')
                amount = float(request.form.get('amount'))
                payment_method = PaymentMethodEnum[request.form.get('payment_method')]
                invoice_number = request.form.get('invoice_number', '')
                receipt_number = request.form.get('receipt_number', '')
                vendor_name = request.form.get('vendor_name', '')
                vendor_contact = request.form.get('vendor_contact', '')
                remarks = request.form.get('remarks', '')
                
                new_expense = Expense(
                    tenant_id=school.id,
                    expense_date=expense_date,
                    category=category,
                    title=title,
                    description=description,
                    amount=amount,
                    payment_method=payment_method,
                    invoice_number=invoice_number,
                    receipt_number=receipt_number,
                    vendor_name=vendor_name,
                    vendor_contact=vendor_contact,
                    remarks=remarks,
                    status=ExpenseStatusEnum.PENDING,
                    created_by=current_user.id
                )
                
                session_db.add(new_expense)
                session_db.commit()
                
                flash('Expense added successfully', 'success')
                return redirect(url_for('school.expense_list', tenant_slug=tenant_slug))
            
            categories = [cat for cat in ExpenseCategoryEnum]
            payment_methods = [pm for pm in PaymentMethodEnum]
            
            return render_template('akademi/expenses/add_expense.html',
                                 school=school,
                                 current_user=current_user,
                                 categories=categories,
                                 payment_methods=payment_methods)
                                 
        except Exception as e:
            logger.error(f"Add expense error for {tenant_slug}: {e}")
            import traceback
            traceback.print_exc()
            flash('Error adding expense', 'error')
            return redirect(url_for('school.expense_list', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/expenses/list')
    @require_school_auth
    def expense_list(tenant_slug):
        """List all expenses with filters"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            # Get filter parameters
            category_filter = request.args.get('category', '')
            status_filter = request.args.get('status', '')
            start_date = request.args.get('start_date', '')
            end_date = request.args.get('end_date', '')
            search = request.args.get('search', '')
            
            # Base query
            query = session_db.query(Expense).filter(Expense.tenant_id == school.id)
            
            # Apply filters
            if category_filter:
                query = query.filter(Expense.category == ExpenseCategoryEnum[category_filter])
            if status_filter:
                query = query.filter(Expense.status == ExpenseStatusEnum[status_filter])
            if start_date:
                query = query.filter(Expense.expense_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
            if end_date:
                query = query.filter(Expense.expense_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
            if search:
                query = query.filter(
                    or_(
                        Expense.title.ilike(f'%{search}%'),
                        Expense.description.ilike(f'%{search}%'),
                        Expense.vendor_name.ilike(f'%{search}%')
                    )
                )
            
            # Get expenses
            expenses = query.order_by(Expense.expense_date.desc()).all()
            
            categories = [cat for cat in ExpenseCategoryEnum]
            statuses = [st for st in ExpenseStatusEnum]
            
            return render_template('akademi/expenses/expense_list.html',
                                 school=school,
                                 current_user=current_user,
                                 expenses=expenses,
                                 categories=categories,
                                 statuses=statuses,
                                 filters={
                                     'category': category_filter,
                                     'status': status_filter,
                                     'start_date': start_date,
                                     'end_date': end_date,
                                     'search': search
                                 })
                                 
        except Exception as e:
            logger.error(f"Expense list error for {tenant_slug}: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading expenses', 'error')
            return redirect(url_for('school.expense_dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/expenses/budget', methods=['GET', 'POST'])
    @require_school_auth
    def budget_setup(tenant_slug):
        """Budget setup and management"""
        session_db = get_session()
        try:
            from sqlalchemy import func
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            if request.method == 'POST':
                financial_year = request.form.get('financial_year')
                month = request.form.get('month')
                category = ExpenseCategoryEnum[request.form.get('category')]
                allocated_amount = float(request.form.get('allocated_amount'))
                description = request.form.get('description', '')
                
                new_budget = Budget(
                    tenant_id=school.id,
                    financial_year=financial_year,
                    month=int(month) if month else None,
                    category=category,
                    allocated_amount=allocated_amount,
                    description=description,
                    created_by=current_user.id
                )
                
                session_db.add(new_budget)
                session_db.commit()
                
                flash('Budget created successfully', 'success')
                return redirect(url_for('school.budget_setup', tenant_slug=tenant_slug))
            
            # Get all budgets and recalculate spent amounts
            budgets = session_db.query(Budget).filter(
                Budget.tenant_id == school.id
            ).order_by(Budget.financial_year.desc(), Budget.category).all()
            
            # Recalculate spent amounts for each budget
            for budget in budgets:
                total_spent = session_db.query(func.sum(Expense.amount)).filter(
                    Expense.tenant_id == school.id,
                    Expense.category == budget.category,
                    Expense.status.in_([ExpenseStatusEnum.APPROVED, ExpenseStatusEnum.PAID]),
                    func.extract('year', Expense.expense_date) >= int(budget.financial_year.split('-')[0]),
                    func.extract('year', Expense.expense_date) <= int(budget.financial_year.split('-')[1])
                ).scalar() or 0
                budget.spent_amount = float(total_spent)
            
            session_db.commit()
            
            categories = [cat for cat in ExpenseCategoryEnum]
            
            return render_template('akademi/expenses/budget_setup.html',
                                 school=school,
                                 current_user=current_user,
                                 budgets=budgets,
                                 categories=categories)
                                 
        except Exception as e:
            logger.error(f"Budget setup error for {tenant_slug}: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading budget setup', 'error')
            return redirect(url_for('school.expense_dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/expenses/budget/<int:budget_id>/delete', methods=['POST'])
    @require_school_auth
    def delete_budget(tenant_slug, budget_id):
        """Delete a budget"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            budget = session_db.query(Budget).filter(
                Budget.id == budget_id,
                Budget.tenant_id == school.id
            ).first()
            
            if not budget:
                return jsonify({'success': False, 'message': 'Budget not found'}), 404
            
            session_db.delete(budget)
            session_db.commit()
            
            flash('Budget deleted successfully', 'success')
            return jsonify({'success': True, 'message': 'Budget deleted successfully'})
            
        except Exception as e:
            logger.error(f"Delete budget error: {e}")
            session_db.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/expenses/reports')
    @require_school_auth
    def expense_reports(tenant_slug):
        """Expense reports and analytics"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            from sqlalchemy import func, extract
            from datetime import date, timedelta
            
            today = date.today()
            current_year = today.year
            
            # Monthly expenses for the year
            monthly_data = []
            for month in range(1, 13):
                total = session_db.query(func.sum(Expense.amount)).filter(
                    Expense.tenant_id == school.id,
                    extract('year', Expense.expense_date) == current_year,
                    extract('month', Expense.expense_date) == month
                ).scalar() or 0
                monthly_data.append(float(total))
            
            # Category-wise yearly expenses
            category_data = session_db.query(
                Expense.category,
                func.sum(Expense.amount)
            ).filter(
                Expense.tenant_id == school.id,
                extract('year', Expense.expense_date) == current_year
            ).group_by(Expense.category).all()
            
            # Payment method distribution
            payment_data = session_db.query(
                Expense.payment_method,
                func.count(Expense.id)
            ).filter(
                Expense.tenant_id == school.id,
                extract('year', Expense.expense_date) == current_year
            ).group_by(Expense.payment_method).all()
            
            # Top vendors
            vendor_data = session_db.query(
                Expense.vendor_name,
                func.sum(Expense.amount)
            ).filter(
                Expense.tenant_id == school.id,
                Expense.vendor_name != None,
                Expense.vendor_name != '',
                extract('year', Expense.expense_date) == current_year
            ).group_by(Expense.vendor_name).order_by(func.sum(Expense.amount).desc()).limit(10).all()
            
            return render_template('akademi/expenses/reports.html',
                                 school=school,
                                 current_user=current_user,
                                 monthly_data=monthly_data,
                                 category_data=category_data,
                                 payment_data=payment_data,
                                 vendor_data=vendor_data,
                                 current_year=current_year)
                                 
        except Exception as e:
            logger.error(f"Expense reports error for {tenant_slug}: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading expense reports', 'error')
            return redirect(url_for('school.expense_dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/expenses/<int:expense_id>/approve', methods=['POST'])
    @require_school_auth
    def approve_expense(tenant_slug, expense_id):
        """Approve an expense"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            expense = session_db.query(Expense).filter(
                Expense.id == expense_id,
                Expense.tenant_id == school.id
            ).first()
            
            if not expense:
                return jsonify({'success': False, 'message': 'Expense not found'}), 404
            
            expense.status = ExpenseStatusEnum.APPROVED
            expense.approved_by = current_user.id
            expense.approved_at = datetime.utcnow()
            
            # Update budget spent_amount
            financial_year = f"{expense.expense_date.year}-{expense.expense_date.year+1}" if expense.expense_date.month >= 4 else f"{expense.expense_date.year-1}-{expense.expense_date.year}"
            budget = session_db.query(Budget).filter(
                Budget.tenant_id == school.id,
                Budget.financial_year == financial_year,
                Budget.category == expense.category,
                Budget.month == None  # Only update yearly budgets for now
            ).first()
            
            if budget:
                budget.spent_amount = float(budget.spent_amount) + float(expense.amount)
            
            session_db.commit()
            
            return jsonify({'success': True, 'message': 'Expense approved successfully'})
            
        except Exception as e:
            logger.error(f"Approve expense error: {e}")
            session_db.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()
    @school_bp.route('/<tenant_slug>/expenses/<int:expense_id>/delete', methods=['POST'])
    @require_school_auth
    def delete_expense(tenant_slug, expense_id):
        """Delete an expense"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            expense = session_db.query(Expense).filter(
                Expense.id == expense_id,
                Expense.tenant_id == school.id
            ).first()
            
            if not expense:
                return jsonify({'success': False, 'message': 'Expense not found'}), 404
            
            session_db.delete(expense)
            session_db.commit()
            
            return jsonify({'success': True, 'message': 'Expense deleted successfully'})
            
        except Exception as e:
            logger.error(f"Delete expense error: {e}")
            session_db.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()
    
    