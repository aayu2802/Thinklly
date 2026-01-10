"""
Transport Management Routes
Routes for transport dashboard, routes, vehicles, stops, and student assignments
"""

from flask import request, jsonify, render_template, redirect, url_for, flash, g
from flask_login import current_user
from sqlalchemy import or_, desc, func
from datetime import datetime, time
import logging

from db_single import get_session
from transport_models import (
    TransportRoute, TransportVehicle, TransportStop, TransportAssignment,
    AssignmentTypeEnum, VehicleStatusEnum
)
from models import Student, Class

logger = logging.getLogger(__name__)


def create_transport_routes(school_blueprint, require_school_auth):
    """Add transport management routes to school blueprint"""
    
    # ===== TRANSPORT DASHBOARD =====
    @school_blueprint.route('/<tenant_slug>/transport')
    @require_school_auth
    def transport_dashboard(tenant_slug):
        """Transport dashboard with statistics"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Get statistics
            stats = {
                'total_routes': session.query(TransportRoute).filter_by(tenant_id=tenant_id).count(),
                'active_routes': session.query(TransportRoute).filter_by(tenant_id=tenant_id, is_active=True).count(),
                'total_vehicles': session.query(TransportVehicle).filter_by(tenant_id=tenant_id).count(),
                'active_vehicles': session.query(TransportVehicle).filter_by(tenant_id=tenant_id, is_active=True).count(),
                'total_stops': session.query(TransportStop).filter_by(tenant_id=tenant_id).count(),
                'total_assignments': session.query(TransportAssignment).filter_by(tenant_id=tenant_id, is_active=True).count(),
            }
            
            # Recent routes
            recent_routes = session.query(TransportRoute).filter_by(
                tenant_id=tenant_id
            ).order_by(desc(TransportRoute.created_at)).limit(5).all()
            
            # Recent assignments
            recent_assignments = session.query(TransportAssignment).filter_by(
                tenant_id=tenant_id, is_active=True
            ).order_by(desc(TransportAssignment.created_at)).limit(10).all()
            
            return render_template('akademi/transport/dashboard.html',
                                 school=g.current_tenant,
                                 stats=stats,
                                 recent_routes=recent_routes,
                                 recent_assignments=recent_assignments,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== ROUTES LIST =====
    @school_blueprint.route('/<tenant_slug>/transport/routes')
    @require_school_auth
    def transport_routes_list(tenant_slug):
        """List all transport routes"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Filters
            status = request.args.get('status', '')
            search = request.args.get('search', '').strip()
            
            query = session.query(TransportRoute).filter_by(tenant_id=tenant_id)
            
            if status == 'active':
                query = query.filter(TransportRoute.is_active == True)
            elif status == 'inactive':
                query = query.filter(TransportRoute.is_active == False)
            
            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    or_(
                        TransportRoute.route_name.ilike(search_pattern),
                        TransportRoute.route_code.ilike(search_pattern),
                        TransportRoute.description.ilike(search_pattern)
                    )
                )
            
            routes = query.order_by(TransportRoute.route_name).all()
            
            return render_template('akademi/transport/routes_list.html',
                                 school=g.current_tenant,
                                 routes=routes,
                                 current_filters={'status': status, 'search': search},
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== CREATE ROUTE =====
    @school_blueprint.route('/<tenant_slug>/transport/routes/create', methods=['GET', 'POST'])
    @require_school_auth
    def transport_route_create(tenant_slug):
        """Create a new transport route"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            if request.method == 'POST':
                try:
                    # Parse time fields
                    start_time = None
                    end_time = None
                    return_start_time = None
                    return_end_time = None
                    
                    if request.form.get('start_time'):
                        start_time = datetime.strptime(request.form.get('start_time'), '%H:%M').time()
                    if request.form.get('end_time'):
                        end_time = datetime.strptime(request.form.get('end_time'), '%H:%M').time()
                    if request.form.get('return_start_time'):
                        return_start_time = datetime.strptime(request.form.get('return_start_time'), '%H:%M').time()
                    if request.form.get('return_end_time'):
                        return_end_time = datetime.strptime(request.form.get('return_end_time'), '%H:%M').time()
                    
                    route = TransportRoute(
                        tenant_id=tenant_id,
                        route_name=request.form.get('route_name', '').strip(),
                        route_code=request.form.get('route_code', '').strip() or None,
                        description=request.form.get('description', '').strip() or None,
                        vehicle_id=request.form.get('vehicle_id', type=int) or None,
                        start_time=start_time,
                        end_time=end_time,
                        return_start_time=return_start_time,
                        return_end_time=return_end_time,
                        is_active=request.form.get('is_active') == 'on',
                        notes=request.form.get('notes', '').strip() or None
                    )
                    
                    session.add(route)
                    session.commit()
                    
                    flash('Transport route created successfully!', 'success')
                    return redirect(url_for('school.transport_route_view', tenant_slug=tenant_slug, route_id=route.id))
                    
                except Exception as e:
                    session.rollback()
                    logger.error(f"Error creating transport route: {e}")
                    flash(f'Error creating route: {str(e)}', 'danger')
            
            # GET request - show form
            vehicles = session.query(TransportVehicle).filter_by(
                tenant_id=tenant_id, is_active=True
            ).order_by(TransportVehicle.vehicle_number).all()
            
            return render_template('akademi/transport/route_form.html',
                                 school=g.current_tenant,
                                 vehicles=vehicles,
                                 route=None,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== VIEW ROUTE =====
    @school_blueprint.route('/<tenant_slug>/transport/routes/<int:route_id>')
    @require_school_auth
    def transport_route_view(tenant_slug, route_id):
        """View transport route details"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            route = session.query(TransportRoute).filter_by(
                id=route_id, tenant_id=tenant_id
            ).first()
            
            if not route:
                flash('Route not found', 'danger')
                return redirect(url_for('school.transport_routes_list', tenant_slug=tenant_slug))
            
            return render_template('akademi/transport/route_view.html',
                                 school=g.current_tenant,
                                 route=route,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== EDIT ROUTE =====
    @school_blueprint.route('/<tenant_slug>/transport/routes/<int:route_id>/edit', methods=['GET', 'POST'])
    @require_school_auth
    def transport_route_edit(tenant_slug, route_id):
        """Edit a transport route"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            route = session.query(TransportRoute).filter_by(
                id=route_id, tenant_id=tenant_id
            ).first()
            
            if not route:
                flash('Route not found', 'danger')
                return redirect(url_for('school.transport_routes_list', tenant_slug=tenant_slug))
            
            if request.method == 'POST':
                try:
                    route.route_name = request.form.get('route_name', '').strip()
                    route.route_code = request.form.get('route_code', '').strip() or None
                    route.description = request.form.get('description', '').strip() or None
                    route.vehicle_id = request.form.get('vehicle_id', type=int) or None
                    route.is_active = request.form.get('is_active') == 'on'
                    route.notes = request.form.get('notes', '').strip() or None
                    
                    # Parse time fields
                    if request.form.get('start_time'):
                        route.start_time = datetime.strptime(request.form.get('start_time'), '%H:%M').time()
                    else:
                        route.start_time = None
                    if request.form.get('end_time'):
                        route.end_time = datetime.strptime(request.form.get('end_time'), '%H:%M').time()
                    else:
                        route.end_time = None
                    if request.form.get('return_start_time'):
                        route.return_start_time = datetime.strptime(request.form.get('return_start_time'), '%H:%M').time()
                    else:
                        route.return_start_time = None
                    if request.form.get('return_end_time'):
                        route.return_end_time = datetime.strptime(request.form.get('return_end_time'), '%H:%M').time()
                    else:
                        route.return_end_time = None
                    
                    session.commit()
                    
                    flash('Route updated successfully!', 'success')
                    return redirect(url_for('school.transport_route_view', tenant_slug=tenant_slug, route_id=route.id))
                    
                except Exception as e:
                    session.rollback()
                    logger.error(f"Error updating transport route: {e}")
                    flash(f'Error updating route: {str(e)}', 'danger')
            
            # GET request
            vehicles = session.query(TransportVehicle).filter_by(
                tenant_id=tenant_id, is_active=True
            ).order_by(TransportVehicle.vehicle_number).all()
            
            return render_template('akademi/transport/route_form.html',
                                 school=g.current_tenant,
                                 vehicles=vehicles,
                                 route=route,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== DELETE ROUTE =====
    @school_blueprint.route('/<tenant_slug>/transport/routes/<int:route_id>/delete', methods=['POST'])
    @require_school_auth
    def transport_route_delete(tenant_slug, route_id):
        """Delete a transport route"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            route = session.query(TransportRoute).filter_by(
                id=route_id, tenant_id=tenant_id
            ).first()
            
            if not route:
                flash('Route not found', 'danger')
                return redirect(url_for('school.transport_routes_list', tenant_slug=tenant_slug))
            
            session.delete(route)
            session.commit()
            
            flash('Route deleted successfully!', 'success')
            return redirect(url_for('school.transport_routes_list', tenant_slug=tenant_slug))
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting transport route: {e}")
            flash(f'Error deleting route: {str(e)}', 'danger')
            return redirect(url_for('school.transport_routes_list', tenant_slug=tenant_slug))
        finally:
            session.close()
    
    # ===== VEHICLES LIST =====
    @school_blueprint.route('/<tenant_slug>/transport/vehicles')
    @require_school_auth
    def transport_vehicles_list(tenant_slug):
        """List all transport vehicles"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            status = request.args.get('status', '')
            search = request.args.get('search', '').strip()
            
            query = session.query(TransportVehicle).filter_by(tenant_id=tenant_id)
            
            if status == 'active':
                query = query.filter(TransportVehicle.is_active == True)
            elif status == 'inactive':
                query = query.filter(TransportVehicle.is_active == False)
            
            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    or_(
                        TransportVehicle.vehicle_number.ilike(search_pattern),
                        TransportVehicle.vehicle_name.ilike(search_pattern),
                        TransportVehicle.driver_name.ilike(search_pattern)
                    )
                )
            
            vehicles = query.order_by(TransportVehicle.vehicle_number).all()
            
            return render_template('akademi/transport/vehicles_list.html',
                                 school=g.current_tenant,
                                 vehicles=vehicles,
                                 current_filters={'status': status, 'search': search},
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== CREATE VEHICLE =====
    @school_blueprint.route('/<tenant_slug>/transport/vehicles/create', methods=['GET', 'POST'])
    @require_school_auth
    def transport_vehicle_create(tenant_slug):
        """Create a new transport vehicle"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            if request.method == 'POST':
                try:
                    vehicle = TransportVehicle(
                        tenant_id=tenant_id,
                        vehicle_number=request.form.get('vehicle_number', '').strip(),
                        vehicle_name=request.form.get('vehicle_name', '').strip() or None,
                        vehicle_type=request.form.get('vehicle_type', 'Bus').strip(),
                        model=request.form.get('model', '').strip() or None,
                        capacity=request.form.get('capacity', 40, type=int),
                        driver_name=request.form.get('driver_name', '').strip() or None,
                        driver_phone=request.form.get('driver_phone', '').strip() or None,
                        driver_license=request.form.get('driver_license', '').strip() or None,
                        helper_name=request.form.get('helper_name', '').strip() or None,
                        helper_phone=request.form.get('helper_phone', '').strip() or None,
                        is_active=request.form.get('is_active') == 'on',
                        notes=request.form.get('notes', '').strip() or None
                    )
                    
                    session.add(vehicle)
                    session.commit()
                    
                    flash('Vehicle added successfully!', 'success')
                    return redirect(url_for('school.transport_vehicles_list', tenant_slug=tenant_slug))
                    
                except Exception as e:
                    session.rollback()
                    logger.error(f"Error creating vehicle: {e}")
                    flash(f'Error creating vehicle: {str(e)}', 'danger')
            
            return render_template('akademi/transport/vehicle_form.html',
                                 school=g.current_tenant,
                                 vehicle=None,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== EDIT VEHICLE =====
    @school_blueprint.route('/<tenant_slug>/transport/vehicles/<int:vehicle_id>/edit', methods=['GET', 'POST'])
    @require_school_auth
    def transport_vehicle_edit(tenant_slug, vehicle_id):
        """Edit a transport vehicle"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            vehicle = session.query(TransportVehicle).filter_by(
                id=vehicle_id, tenant_id=tenant_id
            ).first()
            
            if not vehicle:
                flash('Vehicle not found', 'danger')
                return redirect(url_for('school.transport_vehicles_list', tenant_slug=tenant_slug))
            
            if request.method == 'POST':
                try:
                    vehicle.vehicle_number = request.form.get('vehicle_number', '').strip()
                    vehicle.vehicle_name = request.form.get('vehicle_name', '').strip() or None
                    vehicle.vehicle_type = request.form.get('vehicle_type', 'Bus').strip()
                    vehicle.model = request.form.get('model', '').strip() or None
                    vehicle.capacity = request.form.get('capacity', 40, type=int)
                    vehicle.driver_name = request.form.get('driver_name', '').strip() or None
                    vehicle.driver_phone = request.form.get('driver_phone', '').strip() or None
                    vehicle.driver_license = request.form.get('driver_license', '').strip() or None
                    vehicle.helper_name = request.form.get('helper_name', '').strip() or None
                    vehicle.helper_phone = request.form.get('helper_phone', '').strip() or None
                    vehicle.is_active = request.form.get('is_active') == 'on'
                    vehicle.notes = request.form.get('notes', '').strip() or None
                    
                    session.commit()
                    
                    flash('Vehicle updated successfully!', 'success')
                    return redirect(url_for('school.transport_vehicles_list', tenant_slug=tenant_slug))
                    
                except Exception as e:
                    session.rollback()
                    logger.error(f"Error updating vehicle: {e}")
                    flash(f'Error updating vehicle: {str(e)}', 'danger')
            
            return render_template('akademi/transport/vehicle_form.html',
                                 school=g.current_tenant,
                                 vehicle=vehicle,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== DELETE VEHICLE =====
    @school_blueprint.route('/<tenant_slug>/transport/vehicles/<int:vehicle_id>/delete', methods=['POST'])
    @require_school_auth
    def transport_vehicle_delete(tenant_slug, vehicle_id):
        """Delete a transport vehicle"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            vehicle = session.query(TransportVehicle).filter_by(
                id=vehicle_id, tenant_id=tenant_id
            ).first()
            
            if not vehicle:
                flash('Vehicle not found', 'danger')
                return redirect(url_for('school.transport_vehicles_list', tenant_slug=tenant_slug))
            
            # Check if vehicle is assigned to any routes
            if vehicle.routes:
                flash('Cannot delete vehicle that is assigned to routes. Remove route assignments first.', 'warning')
                return redirect(url_for('school.transport_vehicles_list', tenant_slug=tenant_slug))
            
            session.delete(vehicle)
            session.commit()
            
            flash('Vehicle deleted successfully!', 'success')
            return redirect(url_for('school.transport_vehicles_list', tenant_slug=tenant_slug))
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting vehicle: {e}")
            flash(f'Error deleting vehicle: {str(e)}', 'danger')
            return redirect(url_for('school.transport_vehicles_list', tenant_slug=tenant_slug))
        finally:
            session.close()
    
    # ===== ADD STOP TO ROUTE =====
    @school_blueprint.route('/<tenant_slug>/transport/routes/<int:route_id>/stops/add', methods=['POST'])
    @require_school_auth
    def transport_stop_add(tenant_slug, route_id):
        """Add a stop to a route"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            route = session.query(TransportRoute).filter_by(
                id=route_id, tenant_id=tenant_id
            ).first()
            
            if not route:
                flash('Route not found', 'danger')
                return redirect(url_for('school.transport_routes_list', tenant_slug=tenant_slug))
            
            # Get next sequence order
            max_seq = session.query(func.max(TransportStop.sequence_order)).filter_by(
                route_id=route_id
            ).scalar() or 0
            
            # Parse times
            pickup_time = None
            drop_time = None
            if request.form.get('pickup_time'):
                pickup_time = datetime.strptime(request.form.get('pickup_time'), '%H:%M').time()
            if request.form.get('drop_time'):
                drop_time = datetime.strptime(request.form.get('drop_time'), '%H:%M').time()
            
            stop = TransportStop(
                tenant_id=tenant_id,
                route_id=route_id,
                stop_name=request.form.get('stop_name', '').strip(),
                landmark=request.form.get('landmark', '').strip() or None,
                address=request.form.get('address', '').strip() or None,
                pickup_time=pickup_time,
                drop_time=drop_time,
                sequence_order=max_seq + 1,
                is_active=True
            )
            
            session.add(stop)
            session.commit()
            
            flash('Stop added successfully!', 'success')
            return redirect(url_for('school.transport_route_view', tenant_slug=tenant_slug, route_id=route_id))
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding stop: {e}")
            flash(f'Error adding stop: {str(e)}', 'danger')
            return redirect(url_for('school.transport_route_view', tenant_slug=tenant_slug, route_id=route_id))
        finally:
            session.close()
    
    # ===== DELETE STOP =====
    @school_blueprint.route('/<tenant_slug>/transport/stops/<int:stop_id>/delete', methods=['POST'])
    @require_school_auth
    def transport_stop_delete(tenant_slug, stop_id):
        """Delete a stop from a route"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            stop = session.query(TransportStop).filter_by(
                id=stop_id, tenant_id=tenant_id
            ).first()
            
            if not stop:
                flash('Stop not found', 'danger')
                return redirect(url_for('school.transport_routes_list', tenant_slug=tenant_slug))
            
            route_id = stop.route_id
            
            # Check if stop has assignments
            if stop.assignments:
                flash('Cannot delete stop with assigned students. Remove assignments first.', 'warning')
                return redirect(url_for('school.transport_route_view', tenant_slug=tenant_slug, route_id=route_id))
            
            session.delete(stop)
            session.commit()
            
            flash('Stop deleted successfully!', 'success')
            return redirect(url_for('school.transport_route_view', tenant_slug=tenant_slug, route_id=route_id))
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting stop: {e}")
            flash(f'Error deleting stop: {str(e)}', 'danger')
            return redirect(url_for('school.transport_routes_list', tenant_slug=tenant_slug))
        finally:
            session.close()
    
    # ===== ASSIGNMENTS LIST =====
    @school_blueprint.route('/<tenant_slug>/transport/assignments')
    @require_school_auth
    def transport_assignments_list(tenant_slug):
        """List all student transport assignments"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Filters
            route_id = request.args.get('route_id', type=int)
            class_id = request.args.get('class_id', type=int)
            search = request.args.get('search', '').strip()
            
            query = session.query(TransportAssignment).filter_by(tenant_id=tenant_id, is_active=True)
            
            if route_id:
                query = query.filter(TransportAssignment.route_id == route_id)
            
            if class_id:
                query = query.join(Student).filter(Student.class_id == class_id)
            
            if search:
                search_pattern = f"%{search}%"
                query = query.join(Student).filter(
                    or_(
                        Student.full_name.ilike(search_pattern),
                        Student.admission_number.ilike(search_pattern)
                    )
                )
            
            assignments = query.order_by(TransportAssignment.created_at.desc()).all()
            
            # Get routes and classes for filters
            routes = session.query(TransportRoute).filter_by(tenant_id=tenant_id, is_active=True).all()
            classes = session.query(Class).filter_by(tenant_id=tenant_id, is_active=True).order_by(Class.class_name, Class.section).all()
            
            return render_template('akademi/transport/assignments.html',
                                 school=g.current_tenant,
                                 assignments=assignments,
                                 routes=routes,
                                 classes=classes,
                                 current_filters={'route_id': route_id, 'class_id': class_id, 'search': search},
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== ASSIGN STUDENT =====
    @school_blueprint.route('/<tenant_slug>/transport/assign', methods=['GET', 'POST'])
    @require_school_auth
    def transport_assign_student(tenant_slug):
        """Assign multiple students to a transport route"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            if request.method == 'POST':
                try:
                    # Get multiple student IDs
                    student_ids = request.form.getlist('student_ids', type=int)
                    route_id = request.form.get('route_id', type=int)
                    stop_id = request.form.get('stop_id', type=int) or None
                    assignment_type = request.form.get('assignment_type', 'Both')
                    notes = request.form.get('notes', '').strip() or None
                    
                    if not student_ids or not route_id:
                        flash('Please select at least one student and a route', 'danger')
                        raise ValueError('Missing required fields')
                    
                    success_count = 0
                    skip_count = 0
                    
                    for student_id in student_ids:
                        # Check if assignment already exists
                        existing = session.query(TransportAssignment).filter_by(
                            tenant_id=tenant_id,
                            student_id=student_id,
                            route_id=route_id
                        ).first()
                        
                        if existing:
                            skip_count += 1
                            continue
                        
                        assignment = TransportAssignment(
                            tenant_id=tenant_id,
                            student_id=student_id,
                            route_id=route_id,
                            stop_id=stop_id,
                            assignment_type=assignment_type,
                            is_active=True,
                            notes=notes
                        )
                        
                        session.add(assignment)
                        success_count += 1
                    
                    session.commit()
                    
                    if success_count > 0:
                        flash(f'Successfully assigned {success_count} student(s) to transport!', 'success')
                    if skip_count > 0:
                        flash(f'{skip_count} student(s) were already assigned to this route', 'warning')
                    
                    return redirect(url_for('school.transport_assignments_list', tenant_slug=tenant_slug))
                    
                except ValueError:
                    pass
                except Exception as e:
                    session.rollback()
                    logger.error(f"Error assigning students: {e}")
                    flash(f'Error assigning students: {str(e)}', 'danger')
            
            # GET request
            students = session.query(Student).filter_by(tenant_id=tenant_id).order_by(Student.full_name).all()
            routes = session.query(TransportRoute).filter_by(tenant_id=tenant_id, is_active=True).all()
            classes = session.query(Class).filter_by(tenant_id=tenant_id, is_active=True).order_by(Class.class_name, Class.section).all()
            
            assignment_types = [e.value for e in AssignmentTypeEnum]
            
            return render_template('akademi/transport/assign_student.html',
                                 school=g.current_tenant,
                                 students=students,
                                 routes=routes,
                                 classes=classes,
                                 assignment_types=assignment_types,
                                 tenant_slug=tenant_slug)
        finally:
            session.close()
    
    # ===== REMOVE ASSIGNMENT =====
    @school_blueprint.route('/<tenant_slug>/transport/assignments/<int:assignment_id>/delete', methods=['POST'])
    @require_school_auth
    def transport_assignment_delete(tenant_slug, assignment_id):
        """Remove a student transport assignment"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            assignment = session.query(TransportAssignment).filter_by(
                id=assignment_id, tenant_id=tenant_id
            ).first()
            
            if not assignment:
                flash('Assignment not found', 'danger')
                return redirect(url_for('school.transport_assignments_list', tenant_slug=tenant_slug))
            
            session.delete(assignment)
            session.commit()
            
            flash('Assignment removed successfully!', 'success')
            return redirect(url_for('school.transport_assignments_list', tenant_slug=tenant_slug))
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error removing assignment: {e}")
            flash(f'Error removing assignment: {str(e)}', 'danger')
            return redirect(url_for('school.transport_assignments_list', tenant_slug=tenant_slug))
        finally:
            session.close()
    
    # ===== GET STOPS FOR ROUTE (AJAX) =====
    @school_blueprint.route('/<tenant_slug>/transport/routes/<int:route_id>/stops/json')
    @require_school_auth
    def transport_route_stops_json(tenant_slug, route_id):
        """Get stops for a route as JSON (for AJAX)"""
        session = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            stops = session.query(TransportStop).filter_by(
                route_id=route_id, tenant_id=tenant_id, is_active=True
            ).order_by(TransportStop.sequence_order).all()
            
            return jsonify([{
                'id': stop.id,
                'stop_name': stop.stop_name,
                'landmark': stop.landmark,
                'pickup_time': stop.pickup_time.strftime('%H:%M') if stop.pickup_time else None,
                'drop_time': stop.drop_time.strftime('%H:%M') if stop.drop_time else None,
                'sequence_order': stop.sequence_order
            } for stop in stops])
        finally:
            session.close()
