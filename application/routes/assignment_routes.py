"""
Assignment routes for handling shuttle-celky assignments.
This module provides API endpoints for managing assignments between celky and shuttles.
"""

from flask import Blueprint, request, jsonify
from models.config_module.celky_shuttle import CelkyShuttle
from models.config_module.shuttle_assignment import ShuttleAssignment
from models.config_module.route_optimizer import RouteOptimizer
from models.config_module.shuttle import Shuttle
from models.data_module.celky import Celky
from models.schedule import Schedule
from models.config_module.plant import Plant
from models.config_module.travel_time import TravelTime

# Create a blueprint
assignment_bp = Blueprint('assignments', __name__, url_prefix='/assignments')

@assignment_bp.route('/save_schedule', methods=['POST'])
def save_schedule():
    """
    Save all assignments for a shuttle with their statistics.
    
    Expects JSON data with fields:
    - shuttle_id: ID of the shuttle
    - schedule_id: ID of the schedule
    - celky_ids: List of celky IDs
    - route_order_map: Map of celky_id to route_order
    - start_times_map: Map of celky_id to planned_start_time
    - statistics: Statistics for the shuttle's route
    - ignore_warnings: Boolean flag to ignore RCMPSP impact warnings (optional)
    """
    data = request.json
    
    shuttle_id = int(data.get('shuttle_id'))
    schedule_id = int(data.get('schedule_id'))
    celky_ids = data.get('celky_ids', [])
    route_order_map = data.get('route_order_map', {})
    start_times_map = data.get('start_times_map', {})
    statistics = data.get('statistics', {})
    ignore_warnings = data.get('ignore_warnings', False)
    
    # Validate required parameters
    if not schedule_id:
        return jsonify({
            'success': False,
            'message': 'Missing schedule_id parameter'
        })
    
    # If not ignoring warnings, check for RCMPSP impact
    if not ignore_warnings:
        try:
            from models.rcmpsp.rcmpsp_result import RcmpspResult
            
            # Check if RCMPSP results exist for this schedule
            results = RcmpspResult.get_all_results_for_schedule(schedule_id)
            has_results = results and len(results) > 0
            
            if has_results:
                # Get existing assignments for this shuttle
                existing_assignments = CelkyShuttle.get_assignments_by_schedule(schedule_id)
                current_celky_ids = [
                    a['celky_id'] for a in existing_assignments 
                    if a['shuttle_id'] == shuttle_id
                ]
                
                # Check for significant changes
                additions = [c for c in celky_ids if c not in current_celky_ids]
                removals = [c for c in current_celky_ids if c not in celky_ids]
                
                # If changes are significant, return a warning
                if additions or removals:
                    return jsonify({
                        'success': False,
                        'warning': True,
                        'message': 'Tyto změny mohou ovlivnit existující výpočty jízdních řádů RCMPSP. Chcete pokračovat?',
                        'has_results': True,
                        'results_count': len(results),
                        'changes': {
                            'additions': len(additions),
                            'removals': len(removals)
                        }
                    })
        except Exception as e:
            # Log the error but continue with saving
            print(f"Error checking RCMPSP impact: {str(e)}")
    
    # Save assignments with statistics
    success, message, assignment_ids = ShuttleAssignment.save_assignments_with_statistics(
        shuttle_id=shuttle_id,
        celky_ids=celky_ids,
        route_order_map=route_order_map,
        start_times_map=start_times_map,
        schedule_id=schedule_id,
        statistics=statistics
    )
    
    return jsonify({
        'success': success,
        'message': message,
        'assignment_ids': assignment_ids
    })

@assignment_bp.route('/clear_shuttle', methods=['POST'])
def clear_shuttle_assignments():
    """
    Clear all assignments for a specific shuttle and schedule.
    
    Expects JSON data with fields:
    - shuttle_id: ID of the shuttle
    - schedule_id: ID of the schedule
    """
    data = request.json
    
    shuttle_id = int(data.get('shuttle_id'))
    schedule_id = int(data.get('schedule_id'))
    
    success, message = ShuttleAssignment.clear_shuttle_assignments(shuttle_id, schedule_id)
    
    return jsonify({
        'success': success,
        'message': message
    })

@assignment_bp.route('/get_statistics/<int:shuttle_id>', methods=['GET'])
def get_assignment_statistics(shuttle_id):
    """
    Get statistics for a specific shuttle's assignments.
    
    Args:
        shuttle_id (int): ID of the shuttle
    
    Query parameters:
        - schedule_id: Optional ID of the schedule
    """
    schedule_id = request.args.get('schedule_id')
    if schedule_id:
        schedule_id = int(schedule_id)
    else:
        # Get active schedule if none provided
        active_schedule = Schedule.get_active_schedule()
        schedule_id = active_schedule['id'] if active_schedule else None
    
    if not schedule_id:
        return jsonify({
            'success': False,
            'message': 'No active schedule found'
        })
    
    statistics = ShuttleAssignment.get_assignment_statistics(shuttle_id, schedule_id)
    
    if statistics:
        return jsonify({
            'success': True,
            'statistics': statistics
        })
    else:
        return jsonify({
            'success': False,
            'message': 'No statistics found for this shuttle and schedule'
        })

@assignment_bp.route('/calculate_route_statistics', methods=['POST'])
def calculate_route_statistics():
    """
    Calculate statistics for a route with the given celky assignments.
    
    Expects JSON data with fields:
    - shuttle_id: ID of the shuttle
    - celky_ids: List of celky IDs
    - schedule_id: Optional ID of the schedule
    """
    data = request.json
    
    shuttle_id = int(data.get('shuttle_id'))
    celky_ids = data.get('celky_ids', [])
    schedule_id = data.get('schedule_id')
    
    if not celky_ids:
        return jsonify({
            'success': False,
            'message': 'No celky IDs provided'
        })
    
    # Get plants and travel times data for calculations
    plants = Plant.get_all()
    plants_dict = {plant['identifier']: plant for plant in plants}
    
    # Get travel time matrix as a dictionary
    travel_time_matrix = TravelTime.get_matrix()
    travel_times = travel_time_matrix.to_dict() if travel_time_matrix is not None else {}
    
    # Calculate statistics
    statistics = RouteOptimizer.calculate_route_statistics(
        shuttle_id, celky_ids, schedule_id, plants_dict, travel_times
    )
    
    return jsonify({
        'success': True,
        'statistics': statistics
    })

@assignment_bp.route('/check_rcmpsp_impact', methods=['POST'])
def check_rcmpsp_impact():
    """
    Check if changes to shuttle assignments will impact existing RCMPSP results.
    
    Expects JSON data with fields:
    - schedule_id: ID of the schedule
    - shuttle_id: ID of the shuttle (optional)
    - celky_ids: List of celky IDs (optional)
    
    Returns:
        JSON with information about potential impact on RCMPSP results
    """
    try:
        data = request.json
        schedule_id = int(data.get('schedule_id'))
        
        if not schedule_id:
            return jsonify({
                'success': False,
                'message': 'Missing schedule_id parameter'
            })
        
        from models.rcmpsp.rcmpsp_result import RcmpspResult
        
        # Check if RCMPSP results exist for this schedule
        results = RcmpspResult.get_all_results_for_schedule(schedule_id)
        has_results = results and len(results) > 0
        
        # Determine if the changes would have a significant impact
        impact_level = "none"
        
        if has_results:
            # Get existing assignments for this schedule
            existing_assignments = CelkyShuttle.get_assignments_by_schedule(schedule_id)
            
            # Check if we're adding new celky or removing existing ones
            shuttle_id = data.get('shuttle_id')
            celky_ids = data.get('celky_ids', [])
            
            if shuttle_id:
                # Find current assignments for this shuttle
                current_celky_ids = [
                    a['celky_id'] for a in existing_assignments 
                    if a['shuttle_id'] == shuttle_id
                ]
                
                # Check for additions or removals
                additions = [c for c in celky_ids if c not in current_celky_ids]
                removals = [c for c in current_celky_ids if c not in celky_ids]
                
                if additions or removals:
                    impact_level = "moderate"
                    
                    # If more than 25% of assignments are changing, it's high impact
                    if len(current_celky_ids) > 0:
                        change_percentage = (len(additions) + len(removals)) / len(current_celky_ids) * 100
                        if change_percentage > 25:
                            impact_level = "high"
            else:
                # Without specific shuttle info, we can only provide a general warning
                impact_level = "unknown"
        
        return jsonify({
            'success': True,
            'has_results': has_results,
            'results_count': len(results) if has_results else 0,
            'impact_level': impact_level
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error checking RCMPSP impact: {str(e)}'
        })