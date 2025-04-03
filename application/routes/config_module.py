from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from models.config_module.plant import Plant
from models.config_module.shuttle import Shuttle
from models.config_module.travel_time import TravelTime
from models.config_module.celky_shuttle import CelkyShuttle
from models.schedule import Schedule
from models.data_module.celky import Celky
import json

# Create a blueprint
config_module_bp = Blueprint('config_module', __name__, url_prefix='/config_module')

@config_module_bp.route('/')
def index():
    """Main configuration module page with different configuration options."""
    # Get plant data
    plants = Plant.get_all()
    
    # Get shuttle data
    shuttles = Shuttle.get_all()
    
    # Get travel times
    travel_times = TravelTime.get_all()
    
    # Get schedules
    schedules = Schedule.get_all()
    active_schedule = Schedule.get_active_schedule()
    active_schedule_id = active_schedule['id'] if active_schedule else None
    
    # Get celky data
    celky_data = Celky.get_all_celky()
    
    return render_template(
        'config_module/index.html', 
        plants=plants,
        shuttles=shuttles,
        travel_times=travel_times,
        schedules=schedules,
        active_schedule_id=active_schedule_id,
        celky_data=celky_data,
        active_page='config_module'
    )

# Plant routes
@config_module_bp.route('/plants')
def plants():
    """Display plants management page."""
    plants = Plant.get_all()
    return render_template(
        'config_module/plants.html', 
        plants=plants,
        active_page='config_module'
    )

@config_module_bp.route('/plants/add', methods=['POST'])
def add_plant():
    """Add a new plant."""
    data = request.form.to_dict()
    
    # Convert string values to integers where needed
    if 'ramp_capacity' in data:
        data['ramp_capacity'] = int(data['ramp_capacity'])
    if 'worker_capacity' in data:
        data['worker_capacity'] = int(data['worker_capacity'])
    if 'identifier' in data:
        data['identifier'] = int(data['identifier'])
    
    success, message, plant_id = Plant.add(data)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': success,
            'message': message,
            'id': plant_id
        })
    else:
        return redirect(url_for('config_module.plants'))

@config_module_bp.route('/plants/update/<int:id>', methods=['POST'])
def update_plant(id):
    """Update a plant."""
    data = request.form.to_dict()
    
    # Convert string values to integers where needed
    if 'ramp_capacity' in data:
        data['ramp_capacity'] = int(data['ramp_capacity'])
    if 'worker_capacity' in data:
        data['worker_capacity'] = int(data['worker_capacity'])
    if 'identifier' in data:
        data['identifier'] = int(data['identifier'])
    
    success, message = Plant.update(id, data)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': success,
            'message': message
        })
    else:
        return redirect(url_for('config_module.plants'))

@config_module_bp.route('/plants/delete/<int:id>', methods=['POST'])
def delete_plant(id):
    """Delete a plant."""
    success, message = Plant.delete(id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': success,
            'message': message
        })
    else:
        return redirect(url_for('config_module.plants'))

# Shuttle routes
@config_module_bp.route('/shuttles')
def shuttles():
    """Display shuttles management page."""
    shuttles = Shuttle.get_all()
    plants = Plant.get_all()
    return render_template(
        'config_module/shuttles.html', 
        shuttles=shuttles,
        plants=plants,
        active_page='config_module'
    )

@config_module_bp.route('/shuttles/add', methods=['POST'])
def add_shuttle():
    """Add a new shuttle."""
    data = request.form.to_dict()
    
    # Convert string values to integers where needed
    int_fields = ['capacity', 'shift_length', 'break_time', 'break_each', 
                  'time_for_shift_change', 'shift_change_dest', 'preprah_length', 'preprah_destination']
    for field in int_fields:
        if field in data and data[field]:
            data[field] = int(data[field])
    
    # Convert active checkbox to boolean
    data['active'] = 'active' in data
    
    success, message, shuttle_id = Shuttle.add(data)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': success,
            'message': message,
            'id': shuttle_id
        })
    else:
        return redirect(url_for('config_module.shuttles'))

@config_module_bp.route('/shuttles/update/<int:id>', methods=['POST'])
def update_shuttle(id):
    """Update a shuttle."""
    data = request.form.to_dict()
    
    # Convert string values to integers where needed
    int_fields = ['capacity', 'shift_length', 'break_time', 'break_each', 
                  'time_for_shift_change', 'shift_change_dest', 'preprah_length', 'preprah_destination']
    for field in int_fields:
        if field in data and data[field]:
            data[field] = int(data[field])
        elif field in data:
            data[field] = None  # Handle empty string case
    
    # Convert active checkbox to boolean
    data['active'] = 'active' in data
    
    success, message = Shuttle.update(id, data)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': success,
            'message': message
        })
    else:
        return redirect(url_for('config_module.shuttles'))

@config_module_bp.route('/shuttles/delete/<int:id>', methods=['POST'])
def delete_shuttle(id):
    """Delete a shuttle."""
    success, message = Shuttle.delete(id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': success,
            'message': message
        })
    else:
        return redirect(url_for('config_module.shuttles'))

# Travel time routes
@config_module_bp.route('/travel_times')
def travel_times():
    """Display travel times management page."""
    plants = Plant.get_all()
    
    # Get travel time matrix
    travel_time_matrix = TravelTime.get_matrix()
    
    return render_template(
        'config_module/travel_times.html', 
        plants=plants,
        travel_time_matrix=travel_time_matrix.to_dict() if travel_time_matrix is not None else None,
        active_page='config_module'
    )

@config_module_bp.route('/travel_times/update', methods=['POST'])
def update_travel_time():
    """Update a travel time."""
    data = request.json
    
    source_plant = int(data.get('source_plant'))
    dest_plant = int(data.get('dest_plant'))
    time_minutes = int(data.get('time_minutes'))
    
    success, message = TravelTime.set_travel_time(source_plant, dest_plant, time_minutes)
    
    return jsonify({
        'success': success,
        'message': message
    })

# Schedule routes
@config_module_bp.route('/schedules')
def schedules():
    """Display schedules management page."""
    schedules = Schedule.get_all()
    active_schedule = Schedule.get_active_schedule()
    active_schedule_id = active_schedule['id'] if active_schedule else None
    
    return render_template(
        'config_module/schedules.html', 
        schedules=schedules,
        active_schedule_id=active_schedule_id,
        active_page='config_module'
    )

@config_module_bp.route('/schedules/add', methods=['POST'])
def add_schedule():
    """Add a new schedule."""
    data = request.form.to_dict()
    
    is_template = 'is_template' in data
    
    success, message, schedule_id = Schedule.create_schedule(
        name=data.get('name'),
        description=data.get('description'),
        valid_from=data.get('valid_from'),
        valid_to=data.get('valid_to'),
        is_template=is_template,
        created_by=data.get('created_by', 'admin')
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': success,
            'message': message,
            'id': schedule_id
        })
    else:
        return redirect(url_for('config_module.schedules'))

@config_module_bp.route('/schedules/update/<int:id>', methods=['POST'])
def update_schedule(id):
    """Update a schedule."""
    data = request.form.to_dict()
    
    # Convert checkboxes to boolean
    data['is_template'] = 'is_template' in data
    data['is_active'] = 'is_active' in data
    
    success, message = Schedule.update_schedule(id, data)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': success,
            'message': message
        })
    else:
        return redirect(url_for('config_module.schedules'))

@config_module_bp.route('/schedules/delete/<int:id>', methods=['POST'])
def delete_schedule(id):
    """Delete a schedule."""
    success, message = Schedule.delete_schedule(id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': success,
            'message': message
        })
    else:
        return redirect(url_for('config_module.schedules'))

@config_module_bp.route('/schedules/copy/<int:id>', methods=['POST'])
def copy_schedule(id):
    """Copy a schedule."""
    data = request.form.to_dict()
    
    success, message, new_id = Schedule.copy_schedule(
        id,
        new_name=data.get('new_name'),
        as_template='as_template' in data
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': success,
            'message': message,
            'id': new_id
        })
    else:
        return redirect(url_for('config_module.schedules'))

@config_module_bp.route('/schedules/activate/<int:id>', methods=['POST'])
def activate_schedule(id):
    """Activate a schedule."""
    success, message = Schedule.activate_schedule(id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': success,
            'message': message
        })
    else:
        return redirect(url_for('config_module.schedules'))

# Celky assignment routes
@config_module_bp.route('/planner')
def planner():
    """Display schedule planner page."""
    schedules = Schedule.get_all()
    active_schedule = Schedule.get_active_schedule()
    active_schedule_id = active_schedule['id'] if active_schedule else None
    
    shuttles = Shuttle.get_all(active_only=True)
    
    celky_data = Celky.get_all_celky(active_schedule_id)
    
    plants = Plant.get_all()
    
    travel_time_matrix = TravelTime.get_matrix()
    
    # Get existing assignments for active schedule
    assignments = []
    if active_schedule_id:
        assignments = CelkyShuttle.get_assignments_by_schedule(active_schedule_id)
    
    return render_template(
        'config_module/planner.html', 
        schedules=schedules,
        active_schedule_id=active_schedule_id,
        shuttles=shuttles,
        celky_data=celky_data,
        plants=plants,
        travel_time_matrix=travel_time_matrix.to_dict() if travel_time_matrix is not None else None,
        assignments=assignments,
        active_page='config_module_planner'
    )

@config_module_bp.route('/check_shuttle_assignments', methods=['GET'])
def check_shuttle_assignments():
    """
    Check if the shuttle assignments for a schedule are used in any RCMPSP results.
    This helps warn users before they modify assignments that could break existing
    RCMPSP schedules.
    
    Query parameters:
        - schedule_id: ID of the schedule to check
        
    Returns:
        JSON with information about existing assignments and RCMPSP results
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
            return jsonify({
                "has_assignments": False,
                "has_rcmpsp_results": False
            })
        
        # Check for existing assignments
        assignments = CelkyShuttle.get_assignments_by_schedule(schedule_id)
        has_assignments = len(assignments) > 0
        
        # Check for existing RCMPSP results
        has_rcmpsp_results = False
        
        # Import the RcmpspResult model only if needed
        if has_assignments:
            from models.rcmpsp.rcmpsp_result import RcmpspResult
            results = RcmpspResult.get_all_results_for_schedule(schedule_id)
            has_rcmpsp_results = results and len(results) > 0
        
        return jsonify({
            "has_assignments": has_assignments,
            "has_rcmpsp_results": has_rcmpsp_results,
            "assignments_count": len(assignments) if has_assignments else 0
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "has_assignments": False,
            "has_rcmpsp_results": False
        }), 500

# @config_module_bp.route('/assignments/add', methods=['POST'])
# def add_assignment():
#     """Assign a celky to a shuttle."""
#     data = request.json
    
#     shuttle_id = int(data.get('shuttle_id'))
#     celky_id = int(data.get('celky_id'))
#     route_order = int(data.get('route_order'))
#     planned_start_time = data.get('planned_start_time')
#     planned_duration = int(data.get('planned_duration')) if data.get('planned_duration') else None
#     schedule_id = int(data.get('schedule_id'))
    
#     success, message, assignment_id = CelkyShuttle.assign_celky_to_shuttle(
#         shuttle_id=shuttle_id,
#         celky_id=celky_id,
#         route_order=route_order,
#         planned_start_time=planned_start_time,
#         planned_duration=planned_duration,
#         schedule_id=schedule_id
#     )
    
#     return jsonify({
#         'success': success,
#         'message': message,
#         'id': assignment_id
#     })

# @config_module_bp.route('/assignments/update/<int:id>', methods=['POST'])
# def update_assignment(id):
#     """Update a celky assignment."""
#     data = request.json
    
#     # Convert string values to integers where needed
#     if 'route_order' in data:
#         data['route_order'] = int(data['route_order'])
#     if 'planned_duration' in data and data['planned_duration']:
#         data['planned_duration'] = int(data['planned_duration'])
    
#     success, message = CelkyShuttle.update_assignment(id, data)
    
#     return jsonify({
#         'success': success,
#         'message': message
#     })

# @config_module_bp.route('/assignments/delete/<int:id>', methods=['POST'])
# def delete_assignment(id):
#     """Delete a celky assignment."""
#     success, message = CelkyShuttle.delete_assignment(id)
    
#     return jsonify({
#         'success': success,
#         'message': message
#     })

# @config_module_bp.route('/assignments/shuttle/<int:shuttle_id>')
# def get_shuttle_assignments(shuttle_id):
#     """Get all assignments for a specific shuttle."""
#     schedule_id = request.args.get('schedule_id')
#     if schedule_id:
#         schedule_id = int(schedule_id)
    
#     assignments = CelkyShuttle.get_shuttle_assignments(shuttle_id, schedule_id)
    
#     return jsonify({
#         'success': True,
#         'assignments': assignments
#     })