from flask import Blueprint, render_template, jsonify, request

main_bp = Blueprint('main', __name__)

@main_bp.route('/index')
def home():
    return render_template('index.html', active_page='home')

@main_bp.route('/health')
def health():
    """Health check endpoint for container orchestration and monitoring."""
    try:
        return jsonify({
            "status": "healthy",
            "service": "RCMPSP Scheduler"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500