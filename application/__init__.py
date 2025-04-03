"""
Flask application factory module.
Creates and configures the Flask application.
"""

from flask import Flask, redirect
import logging

def create_app():
    """
    Create and configure the Flask application.
    
    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__, template_folder='../templates', static_folder='../static')

    from simulation import init_dash
    init_dash(app)
    
    # Import and register blueprints
    from application.routes.main import main_bp
    from application.routes.admin import admin_bp
    from application.routes.data_module import data_module_bp
    from application.routes.config_module import config_module_bp
    from application.routes.assignment_routes import assignment_bp
    from application.routes.rcmpsp import rcmpsp_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(data_module_bp)
    app.register_blueprint(config_module_bp)
    app.register_blueprint(assignment_bp)
    app.register_blueprint(rcmpsp_bp)



    # Add global template context
    @app.context_processor
    def inject_active_schedule():
        """
        Inject active schedule data into all templates.
        
        Returns:
            dict: Dictionary with active_schedule_id and schedules
        """
        from models.schedule import Schedule
        active_schedule = Schedule.get_active_schedule()
        schedules = Schedule.get_all()
        return {
            'active_schedule_id': active_schedule['id'] if active_schedule else None,
            'schedules': schedules
        }
    
    # Configure logging
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
    
    return app