# main.py
"""
Single Database Multi-Tenant School Management System
Path-based routing with tenant scoping
"""

import os
import sys
import logging
from flask import Flask, request, g, redirect, render_template_string
from flask_login import LoginManager

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- local modules ---
from config import Config
from db_single import get_session, init_database, ENGINE
from models import User, Tenant, Base
from cli_commands import register_cli_commands

# Initialize database on startup
print("\n" + "="*60)
print("STARTING APPLICATION - Database Integrity Check")
print("="*60)
try:
    from init_db import run_on_startup
    db_initialized = run_on_startup()
    if not db_initialized:
        print("[WARNING] Database initialization had issues!")
        print("Application will continue but may not work correctly.")
except Exception as e:
    print(f"[WARNING] Could not run database initialization: {e}")
    print("Application will continue with existing database state.")
print("="*60 + "\n")


def create_app() -> Flask:
    """Create main application with single database multi-tenancy"""
    app = Flask(
        __name__,
        static_folder="akademi/static",
        template_folder="akademi/templates",
    )
    app.config.from_object(Config)

    # Logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    # DB init
    engine, session_factory = init_database()

    # Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "admin.login"

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            if "_" in user_id:
                t = user_id.split("_")
                if t[0] == "admin":
                    actual_id = t[1]
                    s = get_session()
                    try:
                        return s.query(User).filter_by(
                            id=int(actual_id), role="portal_admin"
                        ).first()
                    finally:
                        s.close()
                elif t[0] == "school" and len(t) >= 3:
                    tenant_id, actual_id = t[1], t[2]
                    s = get_session()
                    try:
                        return s.query(User).filter_by(
                            id=int(actual_id), tenant_id=tenant_id
                        ).first()
                    finally:
                        s.close()
                elif t[0] == "teacher" and len(t) >= 3:
                    # Teacher authentication
                    tenant_id, auth_id = t[1], t[2]
                    s = get_session()
                    try:
                        from teacher_models import TeacherAuth, Teacher
                        from teacher_auth_routes import TeacherAuthUser
                        
                        teacher_auth = s.query(TeacherAuth).filter_by(
                            id=int(auth_id),
                            tenant_id=int(tenant_id),
                            is_active=True
                        ).first()
                        
                        if teacher_auth:
                            # Get teacher details
                            teacher = s.query(Teacher).filter_by(
                                id=teacher_auth.teacher_id
                            ).first()
                            return TeacherAuthUser(teacher_auth, teacher)
                    finally:
                        s.close()
                elif t[0] == "student" and len(t) >= 3:
                    # Student authentication
                    tenant_id, auth_id = t[1], t[2]
                    s = get_session()
                    try:
                        from student_models import StudentAuth, StudentAuthUser
                        
                        student_auth = s.query(StudentAuth).filter_by(
                            id=int(auth_id),
                            tenant_id=int(tenant_id),
                            is_active=True
                        ).first()
                        
                        if student_auth:
                            return StudentAuthUser(student_auth)
                    finally:
                        s.close()
        except Exception as e:
            logging.getLogger(__name__).error(f"user_loader error: {e}")
        return None

    # CLI
    register_cli_commands(app)

    # Admin blueprint
    try:
        from admin_routes_single import create_admin_blueprint
        app.register_blueprint(create_admin_blueprint(), url_prefix="/admin")
        logger.info("✅ Admin blueprint registered")
    except Exception as e:
        logger.error(f"❌ Admin blueprint failed: {e}")
        from flask import Blueprint
        fb = Blueprint("admin", __name__)

        @fb.route("/")
        def dashboard():
            return "<h1>Admin Dashboard</h1><p>Please fix admin routes.</p>"

        app.register_blueprint(fb, url_prefix="/admin")

    # Dynamic school blueprint
    try:
        from school_routes_dynamic import create_school_blueprint
        app.register_blueprint(create_school_blueprint())
        logger.info("✅ School blueprint registered")
    except Exception as e:
        logger.error(f"❌ School blueprint failed: {e}")

    # Teacher authentication blueprint
    try:
        from teacher_auth_routes import teacher_auth_bp
        app.register_blueprint(teacher_auth_bp)
        logger.info("✅ Teacher authentication blueprint registered")
    except Exception as e:
        logger.error(f"❌ Teacher authentication blueprint failed: {e}")

    # Student authentication blueprint
    try:
        from student_auth_routes import student_auth_bp
        app.register_blueprint(student_auth_bp)
        logger.info("✅ Student authentication blueprint registered")
    except Exception as e:
        logger.error(f"❌ Student authentication blueprint failed: {e}")

    # Home dashboard blueprint
    try:
        from home_routes import home_bp
        app.register_blueprint(home_bp)
        logger.info("✅ Home dashboard blueprint registered")
    except Exception as e:
        logger.error(f"❌ Home dashboard blueprint failed: {e}")

    @app.before_request
    def tenant_scope():
        parts = request.path.strip("/").split("/")
        if not parts:
            return
        p = parts[0]

        # ⬇️ Skip tenant resolution for utility/system routes
        SKIP = {
            "admin",
            "static",
            "",
            "api",
            "debug-routes",
            "favicon.ico",
            "robots.txt",
            "_healthz",
            "_status",
        }
        if p in SKIP or p.startswith("_"):
            return

        s = get_session()
        try:
            tenant = s.query(Tenant).filter_by(slug=p, is_active=True).first()
            if tenant:
                g.current_tenant = tenant
                g.tenant_id = tenant.slug
            else:
                if "." not in p:
                    return (
                        render_template_string(
                            """<h1>School Not Found</h1>
                               <p>{{ slug }} not found or inactive.</p>
                               <p><a href="/admin/">Go to Admin Panel</a></p>""",
                            slug=p,
                        ),
                        404,
                    )
        finally:
            s.close()

    @app.route("/")
    def index():
        from flask import render_template
        return render_template("akademi/edusaint-erp-homepage.html")

    @app.route("/debug-routes")
    def debug_routes():
        return "<br>".join(
            f"<b>{r.endpoint}</b> | {sorted(r.methods)} | {r}"
            for r in app.url_map.iter_rules()
        )

    @app.errorhandler(404)
    def nf(_):
        return (
            render_template_string(
                "<h1>404</h1><p>Not found.</p><p><a href='/admin/'>Admin</a></p>"
            ),
            404,
        )

    @app.errorhandler(500)
    def ie(_):
        return (
            render_template_string(
                "<h1>500</h1><p>Internal error.</p><p><a href='/admin/'>Admin</a></p>"
            ),
            500,
        )

    # ===== OPTIONAL: Start background notification scheduler =====
    # Enable by setting ENABLE_NOTIFICATION_SCHEDULER=1 environment variable
    # For production, use cron job instead: flask send-scheduled-notifications
    if os.environ.get('ENABLE_NOTIFICATION_SCHEDULER', '').lower() in ('1', 'true', 'yes'):
        try:
            from notification_scheduler import start_background_scheduler
            scheduler_interval = int(os.environ.get('NOTIFICATION_SCHEDULER_INTERVAL', '60'))
            start_background_scheduler(scheduler_interval)
            logger.info(f"✅ Notification scheduler started (interval: {scheduler_interval}s)")
        except Exception as e:
            logger.error(f"❌ Failed to start notification scheduler: {e}")

    return app


# Passenger needs this at module level
app = create_app()

if __name__ == "__main__":
    # use_reloader=False prevents server restart which kills email threads
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)
