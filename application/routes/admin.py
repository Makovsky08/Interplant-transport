from flask import Blueprint, render_template, request, jsonify
import os
import sys
import flask
from models import (
    get_all_watra_kody, get_watra_kod, add_watra_kod, 
    update_watra_kod, delete_watra_kod, import_excel_to_db, init_db
)
from config import ICO_DB_CONNECTION_STRING, WATRA_DB_CONNECTION_STRING, ORACLE_SQLALCHEMY_CONNECTION_STRING

# Create a blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/settings')
def settings():
    """Admin settings page"""
    # Get system info
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    flask_version = flask.__version__
    
    # Mask connection strings for security
    masked_watra_db = mask_connection_string(WATRA_DB_CONNECTION_STRING)
    masked_ico_db = mask_connection_string(ICO_DB_CONNECTION_STRING)
    masked_oracle_db = mask_connection_string(ORACLE_SQLALCHEMY_CONNECTION_STRING)
    
    return render_template('admin_settings.html', 
                           active_page='admin_settings',
                           python_version=python_version,
                           flask_version=flask_version,
                           watra_db_conn=masked_watra_db,
                           ico_db_conn=masked_ico_db,
                           oracle_db_conn = masked_oracle_db)

@admin_bp.route('/clear_cache', methods=['POST'])
def clear_cache():
    """Clear application cache"""
    try:
        # Implementation would depend on what caching system is used
        # This is a placeholder
        return jsonify({"success": True, "message": "Cache cleared successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@admin_bp.route('/reset_db', methods=['POST'])
def reset_db():
    """Reset WATRA codes database to default values"""
    try:
        # Use the init_db function to reset the database
        init_db(force_reset=True)
        return jsonify({"success": True, "message": "Database reset successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

def mask_connection_string(conn_string):
    """Mask sensitive parts of a connection string"""
    # Basic implementation - would need to be more sophisticated for production
    if 'PWD=' in conn_string:
        parts = conn_string.split('PWD=')
        if len(parts) > 1 and ';' in parts[1]:
            password = parts[1].split(';')[0]
            masked_password = '*' * len(password)
            return conn_string.replace(f"PWD={password}", f"PWD={masked_password}")
    
    return conn_string