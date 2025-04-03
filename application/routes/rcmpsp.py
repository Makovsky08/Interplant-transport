"""
Flask routes for the RCMPSP Simulation Module.
"""

from flask import Blueprint, flash, redirect, render_template, request, jsonify, Response, send_file, url_for
import json
from datetime import datetime, timedelta

from models.config_module.shuttle import Shuttle
from models.config_module.plant import Plant
from models.config_module.travel_time import TravelTime
from models.schedule import Schedule
from models.config_module.shuttle_statistics import ShuttleStatistics
from models.rcmpsp.rcmpsp_result import RcmpspResult

from simulation import InterFacilityRCMPSP

# Create a blueprint
rcmpsp_bp = Blueprint('rcmpsp', __name__, url_prefix='/rcmpsp')

# Initialize the RCMPSP solver
rcmpsp_solver = InterFacilityRCMPSP()

@rcmpsp_bp.route('/')
def index():
    """Render the RCMPSP module main page."""
    # Get active schedule
    active_schedule = Schedule.get_active_schedule()
    active_schedule_id = active_schedule['id'] if active_schedule else None
    
    # Get shuttles
    shuttles = Shuttle.get_all(active_only=True)
    
    # Get plants
    plants = Plant.get_all()
    
    return render_template(
        'rcmpsp/index.html',
        active_schedule_id=active_schedule_id,
        shuttles=shuttles,
        plants=plants,
        active_page='rcmpsp'
    )

@rcmpsp_bp.route('/load_data', methods=['POST'])
def load_data():
    """Load data for the RCMPSP solver."""
    try:
        data = request.json
        schedule_id = data.get('schedule_id')
        scenario = data.get('scenario', 'median')
        
        if not schedule_id:
            return jsonify({"error": "No schedule ID provided"}), 400
        
        #set scenario of the solver
        rcmpsp_solver.scenario = scenario
        # Get the active shuttles
        shuttles = Shuttle.get_all(active_only=True)
        
        # Get all plants
        plants = Plant.get_all()
        
        # Get travel times as a dictionary
        travel_times_matrix = TravelTime.get_matrix()
        travel_times = travel_times_matrix.to_dict() if travel_times_matrix is not None else {}
        
        # Get route statistics for each shuttle
        route_statistics = {}
        for shuttle in shuttles:
            stats = ShuttleStatistics.get_by_shuttle_and_schedule(shuttle['id'], schedule_id)
            if stats:
                route_statistics[shuttle['id']] = stats
        
        # Load data into the RCMPSP solver
        rcmpsp_solver.load_from_database(shuttles, plants, travel_times, route_statistics)
        
        return jsonify({
            "success": True,
            "message": "Data loaded successfully",
            "shuttles_count": len(shuttles),
            "plants_count": len(plants),
            "stats_count": len(route_statistics)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@rcmpsp_bp.route('/generate_activities', methods=['POST'])
def generate_activities():
    """Generate activities for the RCMPSP solver."""
    try:
        # Generate activities
        rcmpsp_solver.generate_activities()
        
        return jsonify({
            "success": True,
            "message": "Activities generated successfully"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@rcmpsp_bp.route('/solve', methods=['POST'])
def solve():
    """Solve the RCMPSP problem."""
    try:
        data = request.json
        time_horizon = data.get('time_horizon', 480)  # Default to 8 hours
        time_limit = data.get('time_limit', 60)  # Default to 60 seconds
        scenario = data.get('scenario', 'median')  # Get the scenario
        schedule_id = data.get('schedule_id')  # Get the schedule ID
        
        # Solve the model
        success = rcmpsp_solver.solve_model(time_horizon=time_horizon, time_limit=time_limit)
        
        if success:
            # Get summary data
            summary = rcmpsp_solver.get_schedule_summary()
            
            # Save results to database if schedule ID is provided
            result_id = None
            save_success = False
            save_message = "Results not saved (no schedule ID provided)"
            
            if schedule_id:
                save_success, save_message, result_id = RcmpspResult.save_rcmpsp_results(
                    schedule_id, 
                    rcmpsp_solver.get_best_schedule(), 
                    summary, 
                    rcmpsp_solver.get_visualization_data(),
                    scenario
                )
            
            # If we successfully saved, get visualization data from the saved result
            vis_data = None
            if save_success and result_id:
                # Get the saved result
                result = RcmpspResult.get_result_by_id(result_id)
                if result:
                    # Use the model method to get visualization data
                    vis_data = RcmpspResult.process_result_for_visualization(result)
            
            # If we couldn't get vis_data from the saved result, use the solver's data
            if not vis_data:
                vis_data = rcmpsp_solver.get_visualization_data()
            
            return jsonify({
                "success": True,
                "message": "RCMPSP solved successfully",
                "summary": summary,
                "save_success": save_success,
                "save_message": save_message,
                "result_id": result_id,
                "vis_data": vis_data
            })
        else:
            return jsonify({
                "success": False,
                "message": "Failed to find a feasible solution"
            })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@rcmpsp_bp.route('/load_dash_data')
def load_dash_data():
    """API endpoint to generate gantt data for the Dash app."""
    from flask import jsonify
    
    try:
        # Get the active schedule
        active_schedule = Schedule.get_active_schedule()
        if not active_schedule:
            return jsonify({'success': False, 'error': 'No active schedule found'})
        
        # Get the latest result for the active schedule
        result = RcmpspResult.get_latest_result_for_schedule(active_schedule['id'])
        
        if not result:
            return jsonify({'success': False, 'error': 'No results found for active schedule'})
        
        # Get plants for display
        plants = Plant.get_all()
        plants_dict = {plant['identifier']: plant for plant in plants}
        
        # Get shuttles for display
        shuttles = Shuttle.get_all()
        shuttles_dict = {shuttle['id']: shuttle for shuttle in shuttles}
        
        # Import the data processing function from dash_integration
        from simulation import process_results_for_dash
        
        # Process the data for Dash
        dash_data = process_results_for_dash(result, plants_dict, shuttles_dict)
        
        return jsonify({'success': True, 'data': dash_data})
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e), 'traceback': traceback.format_exc()})

@rcmpsp_bp.route('/visualization')
def visualization():
    """Get visualization data for the schedule."""
    try:
        # Get visualization data
        vis_data = rcmpsp_solver.get_visualization_data()
        
        if vis_data:
            return jsonify({
                "success": True,
                "data": vis_data
            })
        else:
            return jsonify({
                "success": False,
                "message": "No visualization data available"
            })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@rcmpsp_bp.route('/check_results/<int:schedule_id>')
def check_results(schedule_id):
    """Check for existing RCMPSP results for a schedule."""
    try:
        # Get all results for this schedule
        results = RcmpspResult.get_all_results_for_schedule(schedule_id)
        
        if not results:
            return jsonify({"has_results": False})
        
        # Format the results for the dropdown
        formatted_results = []
        for result in results:
            run_date = result.get('run_date')
            # Format the run date for display
            try:
                if run_date:
                    dt = datetime.fromisoformat(run_date)
                    run_date = dt.strftime('%Y-%m-%d %H:%M')
            except:
                pass  # Use the original string if parsing fails
                
            formatted_results.append({
                "id": result.get('id'),
                "scenario": result.get('scenario', 'median'),
                "run_date": run_date,
                "total_violations": result.get('total_violations', 0),
                "total_frequencies": result.get('total_frequencies', 0),
                "solution_quality": result.get('solution_quality', 'Unknown')
            })
        
        # Sort by newest first
        formatted_results.sort(key=lambda x: x.get('run_date', ''), reverse=True)
        
        return jsonify({
            "has_results": True,
            "results": formatted_results
        })
        
    except Exception as e:
        return jsonify({"has_results": False, "error": str(e)})

@rcmpsp_bp.route('/get_result/<int:result_id>')
def get_result(result_id):
    """Get a specific RCMPSP result."""
    try:
        
        # Get the result with operation details
        result = RcmpspResult.get_result_by_id(result_id)
        if not result:
            print(f"Result with ID {result_id} not found")
            return jsonify({"success": False, "error": "Result not found"})
        
        
        # Prepare summary data with safe access
        summary = {
            "solution_quality": result.get('solution_quality', 'Unknown'),
            "total_violations": result.get('total_violations', 0),
            "total_frequencies": result.get('total_frequencies', 0),
            "total_idle_time": result.get('total_idle_time', 0),
            "shuttles_scheduled": 0  # We'll count unique shuttles below
        }
        
        # Count unique shuttles
        shuttle_ids = set()
        operations = result.get('operations', [])
        
        for op in operations:
            if 'shuttle_id' in op and op['shuttle_id']:
                shuttle_ids.add(op['shuttle_id'])
                
        summary['shuttles_scheduled'] = len(shuttle_ids)
        
        # Use the model method to process operations and get visualizations
        try:
            vis_data = RcmpspResult.process_result_for_visualization(result)
        except Exception as e:
            import traceback
            print(f"Error generating visualization data: {str(e)}")
            print(traceback.format_exc())
            # Provide empty visualization data on error
            vis_data = {
                "violations": {
                    "ramp": 0,
                    "worker": 0,
                    "details": {
                        "ramp": [],
                        "worker": []
                    }
                }
            }
        
        # Make sure all expected response fields are present
        response_data = {
            "success": True,
            "summary": summary,
            "vis_data": vis_data
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Error in get_result: {str(e)}")
        print(error_traceback)
        
        return jsonify({
            "success": False, 
            "error": str(e),
            "traceback": error_traceback,
            # Provide fallback empty data
            "summary": {
                "solution_quality": "Unknown",
                "total_violations": 0,
                "total_frequencies": 0,
                "total_idle_time": 0,
                "shuttles_scheduled": 0
            },
            "vis_data": {
                "violations": {
                    "ramp": 0,
                    "worker": 0,
                    "details": {
                        "ramp": [],
                        "worker": []
                    }
                }
            }
        })

@rcmpsp_bp.route('/preload_dash_data/<int:result_id>')
def preload_dash_data(result_id):
    """Preload data for the Dash application."""
    try:
        # Get the result with operation details
        result = RcmpspResult.get_result_by_id(result_id)
        if not result:
            return jsonify({"success": False, "error": "Result not found"})
        
        # Get plants for display
        plants = Plant.get_all()
        plants_dict = {plant['identifier']: plant for plant in plants}
        
        # Get shuttles for display
        shuttles = Shuttle.get_all()
        shuttles_dict = {shuttle['id']: shuttle for shuttle in shuttles}
        
        # Process the data for Dash
        from simulation import process_results_for_dash
        dash_data = process_results_for_dash(result, plants_dict, shuttles_dict)
        
        # Prepare summary info for display
        summary_info = {
            'solution_quality': result.get('solution_quality', 'Unknown'),
            'total_frequencies': result.get('total_frequencies', 0),
            'total_violations': result.get('total_violations', 0),
            'total_idle_time': result.get('total_idle_time', 0)
        }
        
        # Add summary info to dash data
        dash_data['summary_info'] = summary_info
        
        # Store in the global cache
        try:
            from simulation.dash_gantt.dash_integration import processed_results_cache
            schedule_id = result.get('schedule_id')
            
            if schedule_id:
                # Prepare shuttle options
                shuttle_options = [
                    {'label': shuttle.get('name', f"Shuttle {shuttle_id}"), 'value': shuttle_id} 
                    for shuttle_id, shuttle in shuttles_dict.items()
                ]
                
                # Prepare plant options
                plant_options = [
                    {'label': plant.get('name', f"Plant {plant_id}"), 'value': plant_id} 
                    for plant_id, plant in plants_dict.items()
                ]
                processed_results_cache['result_id'] = result_id
                processed_results_cache[schedule_id] = {
                    'dash_data': dash_data,
                    'solution_quality': summary_info.get('solution_quality', 'Unknown'),
                    'total_frequencies': str(summary_info.get('total_frequencies', 0)),
                    'total_violations': str(summary_info.get('total_violations', 0)),
                    'total_idle_time': f"{summary_info.get('total_idle_time', 0):.1f} minutes",
                    'shuttle_options': shuttle_options,
                    'plant_options': plant_options
                }
        except Exception as e:
            print(f"Warning: Could not store in processed_results_cache: {e}")
        
        return jsonify({"success": True, "message": "Data preloaded for Dash application"})
        
    except Exception as e:
        import traceback
        return jsonify({
            "success": False, 
            "error": str(e),
            "traceback": traceback.format_exc()
        })
    
@rcmpsp_bp.route('/export_result/<int:result_id>')
def export_result(result_id):
    """Export a specific RCMPSP result to Excel."""
    try:
        success, message, filename = RcmpspResult.export_to_excel(result_id)
       
        if success:
            # Send the file for download
            return send_file(
                filename, 
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'rcmpsp_result_{result_id}.xlsx'
            )
        else:
            # Handle export failure
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": False, "message": message}), 400
            else:
                return render_template('rcmpsp/no_results.html',
                                      message=f"Export failed: {message}",
                                      schedule={"name": "Unknown"},
                                      active_page='rcmpsp'), 400
    except Exception as e:
        # Handle exceptions 
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "message": str(e)}), 500
        else:
            return render_template('rcmpsp/no_results.html',
                                  message=f"Error exporting result: {str(e)}",
                                  schedule={"name": "Unknown"},
                                  active_page='rcmpsp'), 500

@rcmpsp_bp.route('/delete_result/<int:result_id>', methods=['POST'])
def delete_result(result_id):
    """Delete a specific RCMPSP result."""
    try:
        # Call the model method to delete the result
        success, message, schedule_id = RcmpspResult.delete_result(result_id)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": success, "message": message})
        
        if success:
            return redirect(url_for('rcmpsp.index'))
        else:
            return render_template('rcmpsp/no_results.html', 
                                  message=message,
                                  schedule={"name": "Unknown"},
                                  active_page='rcmpsp')
    
    except Exception as e:
        import traceback
        error_message = f"Error in delete route: {str(e)}\n{traceback.format_exc()}"
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "message": error_message})
        
        return render_template('rcmpsp/no_results.html', 
                              message=error_message,
                              schedule={"name": "Unknown"},
                              active_page='rcmpsp')