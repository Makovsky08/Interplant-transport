# application/routes/data_module.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
import pandas as pd
from models import run_analysis, get_all_watra_kody
from models.data_module.celky import Celky
from models.data_module.watra_kod import WatraKod
from models.schedule import Schedule
from models.config_module.celky_shuttle import CelkyShuttle
import os

# Create a blueprint
data_module_bp = Blueprint('data_module', __name__, url_prefix='/data_module')

@data_module_bp.route('/')
def index():
    """Main data module page with options for WATRA codes and celky analysis."""
    # Get WATRA codes data
    watra_data = get_all_watra_kody()
    
    
    # Get schedules
    active_schedule = Schedule.get_active_schedule()
    active_schedule_id = active_schedule['id'] if active_schedule else None

    # Get all celky
    celky_data = Celky.get_all_celky(active_schedule_id)
    
    return render_template(
        'data_module/index.html', 
        watra_data=watra_data,
        celky_data=celky_data,
        active_schedule_id=active_schedule_id,
        active_page='data_module'
    )

@data_module_bp.route('/watra_codes')
def watra_codes():
    """Display WATRA codes management page."""
    # Get WATRA codes data
    watra_data = get_all_watra_kody()
    
    return render_template(
        'data_module/watra_codes.html', 
        watra_data=watra_data,
        active_page='data_module'
    )


@data_module_bp.route('/watra_kody', methods=['GET', 'POST'])
def watra_kody():
    """Admin endpoint for managing WATRA codes database"""
    message = None
    
    if request.method == 'POST':
        # Check if Excel file was uploaded
        if 'excel_file' in request.files:
            file = request.files['excel_file']
            if file.filename != '':
                # Save the uploaded file
                file_path = os.path.join('uploads', file.filename)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                file.save(file_path)
                
                # Import data from Excel to database
                if WatraKod.import_excel(file_path):
                    message = "Data byla úspěšně importována z Excel souboru."
                else:
                    message = "Chyba při importu dat. Zkontrolujte formát Excel souboru."
    
    # Get current data from database
    data = get_all_watra_kody()
    
    return render_template('admin_watra_kody.html', 
                          data=data,
                          message=message,
                          active_page='admin_watra_kody')

@data_module_bp.route('/watra_kody/add', methods=['POST'])
def add_watra_kod_route():
    """Add a new WATRA code"""
    data = request.json
    success, message, new_id = WatraKod.add(data)
    return jsonify({"success": success, "message": message, "id": new_id})

@data_module_bp.route('/watra_kody/update', methods=['POST'])
def update_watra_kod_route():
    """Update an existing WATRA code"""
    data = request.json
    
    # Make sure id exists and is a valid integer
    if 'id' not in data or not data['id']:
        return jsonify({"success": False, "message": "Chybí ID záznamu"})
    
    try:
        id = int(data.pop('id'))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Neplatné ID záznamu"})
    
    success, message = WatraKod.update(id, data)
    return jsonify({"success": success, "message": message})

@data_module_bp.route('/watra_kody/delete/<int:id>', methods=['POST'])
def delete_watra_kod_route(id):
    """Delete a WATRA code"""
    success, message = WatraKod.delete(id)
    return jsonify({"success": success, "message": message})

@data_module_bp.route('/analysis')
def analysis():
    """Display data analysis page."""
    # Get all celky
    active_schedule = Schedule.get_active_schedule()
    active_schedule_id = active_schedule['id'] if active_schedule else None

    celky_data = Celky.get_all_celky(active_schedule_id)
    
    return render_template(
        'data_module/analysis.html', 
        celky_data=celky_data,
        active_schedule_id=active_schedule_id,
        active_page='data_module'
    )

@data_module_bp.route('/check_assigned_celky')
def check_assigned_celky():
    """
    Check if there are any celky assigned to shuttles in the active schedule.
    
    Returns:
        JSON with the count of assigned celky
    """
    try:
        schedule_id = request.args.get('schedule_id')
        if not schedule_id:
            # Get active schedule if none provided
            active_schedule = Schedule.get_active_schedule()
            schedule_id = active_schedule['id'] if active_schedule else None
        else:
            schedule_id = int(schedule_id)
            
        if not schedule_id:
            return jsonify({"assigned_count": 0})
            
        # Get assignments for this schedule
        assignments = CelkyShuttle.get_assignments_by_schedule(schedule_id)
        
        # Get unique celky IDs from assignments
        assigned_celky_ids = set()
        for assignment in assignments:
            assigned_celky_ids.add(assignment.get('celky_id'))
            
        return jsonify({
            "assigned_count": len(assigned_celky_ids),
            "schedule_id": schedule_id
        })
        
    except Exception as e:
        return jsonify({"error": str(e), "assigned_count": 0}), 500

@data_module_bp.route('/analyze_data', methods=['POST'])
def analyze_data():
    """Perform analysis and save results as celky."""
    try:
        # Get parameters from form
        months_back = int(request.form.get('months_back', 6))
        active_schedule = Schedule.get_active_schedule()
        active_schedule_id = active_schedule['id'] if active_schedule else None
        
        # Convert schedule_id to int if provided
        if active_schedule_id:
            try:
                active_schedule_id = int(active_schedule_id)
            except (ValueError, TypeError):
                active_schedule_id = None
        
        # Perform analysis
        results_df = run_analysis(months_back)
        
        if results_df.empty:
            return jsonify({"success": False, "error": "No data found for analysis."}), 404
        
        # Save results as celky (now with schedule_id)
        saved_ids = Celky.save_analysis_results(results_df, months_back, active_schedule_id)
        
        if not saved_ids:
            return jsonify({"success": False, "error": "Failed to save analysis results as celky."}), 404
        
        # Get all celky for display (filtered by schedule if applicable)
        celky_data = Celky.get_all_celky(active_schedule_id)
        
        # Convert celky data to HTML table for display
        celky_html = render_template('data_module/celky_table.html', celky_data=celky_data)
        
        # Check for assigned celky
        assigned_count = 0
        if active_schedule_id:
            # Get assignments for this schedule
            assignments = CelkyShuttle.get_assignments_by_schedule(active_schedule_id)
            
            # Count unique celky IDs
            assigned_celky_ids = set()
            for assignment in assignments:
                assigned_celky_ids.add(assignment.get('celky_id'))
                
            assigned_count = len(assigned_celky_ids)
        
        return jsonify({
            "success": True, 
            "celky_html": celky_html,
            "months_back": months_back,
            "celky_count": len(saved_ids),
            "active_schedule_id": active_schedule_id,
            "assigned_count": assigned_count
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@data_module_bp.route('/celky/<int:celky_id>')
def celky_detail(celky_id):
    """Display detailed view of a specific celky."""
    celky = Celky.get_celky_by_id(celky_id)
    
    if not celky:
        return render_template('error.html', message=f"Celky with ID {celky_id} not found."), 404
    
    return render_template('data_module/celky_detail.html', celky=celky, active_page='data_module')