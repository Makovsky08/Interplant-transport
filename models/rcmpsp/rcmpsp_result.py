# models/rcmpsp_result.py
from models.base import Model
import sqlite3
from datetime import datetime

class RcmpspResult(Model):
    """Model for RCMPSP optimization results and details."""
    
    results_table = 'rcmpsp_results'
    details_table = 'rcmpsp_operation_details'
    
    @classmethod
    def create_table(cls, force_reset=False):
        """
        Create the tables for RCMPSP results if they don't exist.
        
        Args:
            force_reset (bool): If True, drop and recreate the tables
        """
        conn = cls.get_db_connection()
        cursor = conn.cursor()
        
        if force_reset:
            cursor.execute(f"DROP TABLE IF EXISTS {cls.details_table}")
            cursor.execute(f"DROP TABLE IF EXISTS {cls.results_table}")
        
        # Create results table
        cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {cls.results_table} (
            id INTEGER PRIMARY KEY,
            schedule_id INTEGER NOT NULL,
            run_date TEXT NOT NULL,
            scenario TEXT NOT NULL,
            total_violations INTEGER NOT NULL,
            total_frequencies INTEGER NOT NULL,
            total_idle_time REAL NOT NULL,
            solution_quality TEXT NOT NULL,
            FOREIGN KEY (schedule_id) REFERENCES schedules (id)
        )
        ''')
        
        # Create operation details table
        cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {cls.details_table} (
            id INTEGER PRIMARY KEY,
            result_id INTEGER NOT NULL,
            shuttle_id INTEGER NOT NULL,
            operation_type TEXT NOT NULL,
            plant_id INTEGER,
            from_plant_id INTEGER,
            to_plant_id INTEGER,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            duration INTEGER NOT NULL,
            frequency_num INTEGER NOT NULL,
            is_preprah_operation INTEGER NOT NULL DEFAULT 0,
            has_violation INTEGER NOT NULL DEFAULT 0,
            violation_type TEXT,
            FOREIGN KEY (result_id) REFERENCES {cls.results_table} (id) ON DELETE CASCADE
        )
        ''')
        
        conn.commit()
        conn.close()
    
    @classmethod
    def init_db(cls, force_reset=False):
        """Initialize the database with RCMPSP result tables."""
        cls.create_table(force_reset)
    
    @classmethod
    def save_rcmpsp_results(cls, schedule_id, best_schedule, schedule_summary, visualization_data, scenario='median'):
        """
        Save RCMPSP optimization results to the database.
        
        Args:
            schedule_id (int): ID of the schedule
            best_schedule (dict): Best schedule found by the optimizer
            schedule_summary (dict): Summary statistics of the schedule
            visualization_data (dict): Visualization data including violations
            scenario (str): Scenario used for optimization
            
        Returns:
            tuple: (success, message, result_id)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Begin transaction
            conn.execute("BEGIN TRANSACTION")
            
            # Insert main result record
            cursor.execute(
                f"""
                INSERT INTO {cls.results_table} 
                (schedule_id, run_date, scenario, total_violations, total_frequencies, 
                total_idle_time, solution_quality)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule_id,
                    datetime.now().isoformat(),
                    scenario,
                    schedule_summary.get('total_violations', 0),
                    schedule_summary.get('total_frequencies', 0),
                    schedule_summary.get('total_idle_time', 0.0),
                    schedule_summary.get('solution_quality', 'Unknown')
                )
            )
            
            result_id = cursor.lastrowid
            
            # Process violations data for lookup
            violations = {}
            if visualization_data and 'violations' in visualization_data:
                for violation_type, violation_list in visualization_data['violations'].get('details', {}).items():
                    for violation in violation_list:
                        shuttle_id = violation.get('shuttle_id')
                        operation_num = violation.get('operation_num')
                        
                        if shuttle_id is not None and operation_num is not None:
                            key = (shuttle_id, operation_num)
                            if key not in violations:
                                violations[key] = []
                            violations[key].append(violation_type)
            
            # Insert operation details for each shuttle
            for shuttle_id, schedule in best_schedule.items():
                for op in schedule['operations']:
                    # Determine violation status
                    has_violation = 0
                    violation_type = None
                    operation_num = op.get('operation_num')
                    
                    if operation_num is not None:
                        key = (shuttle_id, operation_num)
                        if key in violations:
                            has_violation = 1
                            violation_type = ','.join(violations[key])
                    
                    # Format datetime objects to ISO strings
                    start_time = op['start_time'].isoformat() if hasattr(op['start_time'], 'isoformat') else op['start_time']
                    end_time = op['end_time'].isoformat() if hasattr(op['end_time'], 'isoformat') else op['end_time']
                    
                    # Insert operation detail
                    cursor.execute(
                        f"""
                        INSERT INTO {cls.details_table}
                        (result_id, shuttle_id, operation_type, plant_id, from_plant_id, to_plant_id,
                         start_time, end_time, duration, frequency_num, is_preprah_operation, 
                         has_violation, violation_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            result_id,
                            shuttle_id,
                            op['type'],
                            op.get('plant'),
                            op.get('from_plant'),
                            op.get('to_plant'),
                            start_time,
                            end_time,
                            op['duration'],
                            op.get('frequency_num', 0),
                            1 if op.get('is_preprah_operation', False) else 0,
                            has_violation,
                            violation_type
                        )
                    )
            
            # Commit transaction
            conn.commit()
            conn.close()
            
            return (True, "RCMPSP results saved successfully", result_id)
            
        except Exception as e:
            # Rollback on error
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            
            return (False, f"Error saving RCMPSP results: {str(e)}", None)
    
    @classmethod
    def get_result_by_id(cls, result_id):
        """
        Get a specific RCMPSP result by ID.
        
        Args:
            result_id (int): ID of the result to retrieve
            
        Returns:
            dict: Result data with operation details or None if not found
        """
        conn = cls.get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get the main result record
        cursor.execute(
            f"SELECT * FROM {cls.results_table} WHERE id = ?",
            (result_id,)
        )
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return None
        
        result_dict = dict(result)
        
        # Get operation details
        cursor.execute(
            f"SELECT * FROM {cls.details_table} WHERE result_id = ? ORDER BY shuttle_id, start_time",
            (result_id,)
        )
        
        details = [dict(row) for row in cursor.fetchall()]
        result_dict['operations'] = details
        
        conn.close()
        return result_dict
    
    @classmethod
    def get_latest_result_for_schedule(cls, schedule_id):
        """
        Get the latest RCMPSP result for a specific schedule.
        
        Args:
            schedule_id (int): ID of the schedule
            
        Returns:
            dict: Latest result data with operation details or None if not found
        """
        conn = cls.get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get the most recent result for this schedule
        cursor.execute(
            f"SELECT id FROM {cls.results_table} WHERE schedule_id = ? ORDER BY run_date DESC LIMIT 1",
            (schedule_id,)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return cls.get_result_by_id(row['id'])
        
        return None
    
    @classmethod
    def get_all_results_for_schedule(cls, schedule_id):
        """
        Get all RCMPSP results for a specific schedule.
        
        Args:
            schedule_id (int): ID of the schedule
            
        Returns:
            list: List of result data without operation details
        """
        conn = cls.get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all results for this schedule
        cursor.execute(
            f"SELECT * FROM {cls.results_table} WHERE schedule_id = ? ORDER BY run_date DESC",
            (schedule_id,)
        )
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    @classmethod
    def get_latest_result_for_schedule_by_scenario(cls, schedule_id, scenario='median'):
        """
        Get the latest RCMPSP result for a specific schedule and scenario.
        
        Args:
            schedule_id (int): ID of the schedule
            scenario (str): Scenario name (median, peak_median, p90, peak_p90)
            
        Returns:
            dict: Latest result data with operation details or None if not found
        """
        conn = cls.get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get the most recent result for this schedule and scenario
        cursor.execute(
            f"""
            SELECT id FROM {cls.results_table}
            WHERE schedule_id = ? AND scenario = ?
            ORDER BY run_date DESC LIMIT 1
            """,
            (schedule_id, scenario)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return cls.get_result_by_id(row['id'])
        
        return None
    
    @classmethod
    def delete_result(cls, result_id):
        """
        Delete a specific RCMPSP result and its details.
        
        Args:
            result_id (int): ID of the result to delete
            
        Returns:
            tuple: (success, message, schedule_id)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # First check if the result exists and get its schedule_id
            cursor.execute(
                f"SELECT schedule_id FROM {cls.results_table} WHERE id = ?",
                (result_id,)
            )
            
            row = cursor.fetchone()
            if not row:
                conn.close()
                return (False, f"Result with ID {result_id} not found", None)
            
            schedule_id = row['schedule_id']
            
            # Begin transaction
            conn.execute("BEGIN TRANSACTION")
            
            # Delete operation details first (due to foreign key constraint)
            cursor.execute(
                f"DELETE FROM {cls.details_table} WHERE result_id = ?",
                (result_id,)
            )
            
            # Delete the main result
            cursor.execute(
                f"DELETE FROM {cls.results_table} WHERE id = ?",
                (result_id,)
            )
            
            # Commit transaction
            conn.commit()
            conn.close()
            
            return (True, "Result deleted successfully", schedule_id)
            
        except Exception as e:
            # Rollback on error
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            
            import traceback
            error_message = f"Error deleting result: {str(e)}\n{traceback.format_exc()}"
            return (False, error_message, None)

    @classmethod
    def get_all_results_by_scenario(cls, schedule_id, scenario):
        """
        Get all RCMPSP results for a specific schedule and scenario.
        
        Args:
            schedule_id (int): ID of the schedule
            scenario (str): Scenario name
            
        Returns:
            list: List of result data without operation details
        """
        conn = cls.get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all results for this schedule and scenario
        cursor.execute(
            f"""
            SELECT * FROM {cls.results_table}
            WHERE schedule_id = ? AND scenario = ?
            ORDER BY run_date DESC
            """,
            (schedule_id, scenario)
        )
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    @classmethod
    def process_result_for_visualization(cls, result):
        """
        Process RCMPSP result data for visualization with proper time formatting.
        
        Args:
            result (dict): RCMPSP result with operations
            
        Returns:
            dict: Data for visualization
        """
        # Get plants for display
        from models.config_module.plant import Plant
        plants = Plant.get_all()
        plants_dict = {plant['identifier']: plant for plant in plants}
        
        # Get shuttles for better naming
        from models.config_module.shuttle import Shuttle
        shuttles = Shuttle.get_all()
        shuttles_dict = {shuttle['id']: shuttle for shuttle in shuttles}
        
        # Track violations by resource type
        violations = {
            "ramp": [],
            "worker": []
        }
        
        # Identify preprah shuttles and their destinations
        preprah_shuttles = {}  # shuttle_id -> preprah_destination
        preprah_destinations = {}  # plant_id -> set(shuttle_ids)
        
        for op in result.get('operations', []):
            shuttle_id = op.get('shuttle_id')
            if shuttle_id and shuttle_id in shuttles_dict:
                shuttle = shuttles_dict[shuttle_id]
                if shuttle.get('shuttle_type') == 'preprah':
                    preprah_destination = shuttle.get('preprah_destination')
                    if preprah_destination:
                        preprah_shuttles[shuttle_id] = preprah_destination
                        if preprah_destination not in preprah_destinations:
                            preprah_destinations[preprah_destination] = set()
                        preprah_destinations[preprah_destination].add(shuttle_id)
        
        # First pass: extract all operations and their start/end times
        operations_by_shuttle = {}
        operations_by_plant = {}
        
        for op in result.get('operations', []):
            shuttle_id = op.get('shuttle_id')
            plant_id = op.get('plant_id')
            
            # Skip operations without shuttle or plant
            if not shuttle_id or not plant_id:
                continue
            
            # Format times correctly
            start_time = op.get('start_time')
            end_time = op.get('end_time')
            
            # Handle string or datetime objects
            if isinstance(start_time, str):
                try:
                    from datetime import datetime
                    # Try to parse ISO format
                    start_time = datetime.fromisoformat(start_time).strftime('%H:%M')
                except:
                    # If parsing fails, extract just the time portion if possible
                    if 'T' in start_time:
                        time_part = start_time.split('T')[1]
                        if '.' in time_part:
                            time_part = time_part.split('.')[0]
                        if len(time_part) >= 5:
                            start_time = time_part[:5]  # Get HH:MM
            
            if isinstance(end_time, str):
                try:
                    from datetime import datetime
                    # Try to parse ISO format
                    end_time = datetime.fromisoformat(end_time).strftime('%H:%M')
                except:
                    # If parsing fails, extract just the time portion if possible
                    if 'T' in end_time:
                        time_part = end_time.split('T')[1]
                        if '.' in time_part:
                            time_part = time_part.split('.')[0]
                        if len(time_part) >= 5:
                            end_time = time_part[:5]  # Get HH:MM
            
            # Store by shuttle
            if shuttle_id not in operations_by_shuttle:
                operations_by_shuttle[shuttle_id] = []
            
            # Check if this is a preprah operation or at a preprah destination
            is_preprah_op = op.get('is_preprah_operation', False)
            is_preprah_shuttle = shuttle_id in preprah_shuttles
            preprah_destination = preprah_shuttles.get(shuttle_id)
            
            # Skip load/unload operations at preprah destinations
            if is_preprah_shuttle and is_preprah_op and op.get('operation_type') in ['load', 'unload'] and plant_id == preprah_destination:
                continue
            
            operations_by_shuttle[shuttle_id].append({
                'operation_num': op.get('id', len(operations_by_shuttle[shuttle_id])),
                'type': op.get('operation_type'),
                'plant_id': plant_id,
                'start_time': start_time,
                'end_time': end_time,
                'has_violation': op.get('has_violation', False),
                'violation_type': op.get('violation_type')
            })
            
            # Store by plant
            if plant_id not in operations_by_plant:
                operations_by_plant[plant_id] = []
            
            operations_by_plant[plant_id].append({
                'shuttle_id': shuttle_id,
                'operation_num': op.get('id', len(operations_by_plant[plant_id])),
                'type': op.get('operation_type'),
                'start_time': start_time,
                'end_time': end_time,
                'has_violation': op.get('has_violation', False),
                'violation_type': op.get('violation_type'),
                'is_preprah_shuttle': is_preprah_shuttle,
                'is_preprah_op': is_preprah_op
            })
        
        # Add permanent ramp reservations for preprah destinations
        for plant_id, shuttle_ids in preprah_destinations.items():
            if plant_id not in operations_by_plant:
                operations_by_plant[plant_id] = []
            
            for shuttle_id in shuttle_ids:
                if shuttle_id in shuttles_dict:
                    shuttle = shuttles_dict[shuttle_id]
                    shift_hours = shuttle.get('shift_length', 8)
                    
                    # Create a permanent ramp reservation
                    operations_by_plant[plant_id].append({
                        'shuttle_id': shuttle_id,
                        'type': 'preprah_reserved',
                        'start_time': '06:00',  # Assuming shift starts at 6 AM
                        'end_time': f"{6+shift_hours:02d}:00",  # End time based on shift length
                        'is_permanent': True
                    })
        
        # Second pass: identify violations by checking resource usage at each time point
        # Track which operations already have violations to avoid duplicates
        operation_violations = set()
        
        for plant_id, operations in operations_by_plant.items():
            # Sort operations by start time
            operations.sort(key=lambda op: op['start_time'])
            
            # Get plant capacity
            ramp_capacity = 2  # Default
            worker_capacity = 2  # Default
            
            if plant_id in plants_dict:
                plant = plants_dict[plant_id]
                ramp_capacity = plant.get('ramp_capacity', 2)
                worker_capacity = plant.get('worker_capacity', 2)
            
            # Find all time points where resource usage might change
            time_points = []
            for op in operations:
                if op['start_time'] not in time_points:
                    time_points.append(op['start_time'])
                if op['end_time'] not in time_points:
                    time_points.append(op['end_time'])
            
            time_points.sort()
            
            # Check usage at each time interval
            for i in range(len(time_points) - 1):
                start = time_points[i]
                end = time_points[i+1]
                
                # Skip zero-length intervals
                if start == end:
                    continue
                
                # Count active operations during this interval
                active_ops = []
                permanent_reservations = set()  # Set of shuttle IDs with permanent reservations
                
                for op in operations:
                    if op['start_time'] <= start and op['end_time'] >= end:
                        if op.get('is_permanent'):
                            permanent_reservations.add(op['shuttle_id'])
                        else:
                            active_ops.append(op)
                
                # Count ramp usage
                ramp_usage = 0
                for op in active_ops:
                    if op['type'] in ['load', 'unload', 'preprah']:
                        ramp_usage += 1
                
                # Add permanent reservations (1 per preprah destination)
                ramp_usage += len(permanent_reservations)
                
                # Count worker usage
                worker_usage = 0
                for op in active_ops:
                    if op['type'] in ['load', 'unload', 'preprah']:
                        worker_usage += 1
                
                # Check for ramp violations
                if ramp_usage > ramp_capacity:
                    # Create ramp violations for operations that use ramps
                    for op in active_ops:
                        if op['type'] in ['load', 'unload', 'preprah']:
                            # Create a unique key for this operation
                            op_key = (op['shuttle_id'], op['operation_num'], 'ramp')
                            
                            # Only add if we haven't already added a violation for this operation
                            if op_key not in operation_violations:
                                operation_violations.add(op_key)
                                
                                # Get plant name
                                plant_name = f"Plant {plant_id}"
                                if plant_id in plants_dict:
                                    plant_name = plants_dict[plant_id].get('name', plant_name)
                                
                                # Get shuttle name
                                shuttle_name = f"Shuttle {op['shuttle_id']}"
                                if op['shuttle_id'] in shuttles_dict:
                                    shuttle_name = shuttles_dict[op['shuttle_id']].get('name', shuttle_name)
                                
                                violations['ramp'].append({
                                    'plant_id': plant_id,
                                    'plant_name': plant_name,
                                    'start_time': start,
                                    'end_time': end,
                                    'capacity': ramp_capacity,
                                    'total_usage': ramp_usage,
                                    'shuttles': [op['shuttle_id']],
                                    'shuttle_names': [shuttle_name]
                                })
                
                # Check for worker violations
                if worker_usage > worker_capacity:
                    # Create worker violations for operations that use workers
                    for op in active_ops:
                        if op['type'] in ['load', 'unload', 'preprah']:
                            # Create a unique key for this operation
                            op_key = (op['shuttle_id'], op['operation_num'], 'worker')
                            
                            # Only add if we haven't already added a violation for this operation
                            if op_key not in operation_violations:
                                operation_violations.add(op_key)
                                
                                # Get plant name
                                plant_name = f"Plant {plant_id}"
                                if plant_id in plants_dict:
                                    plant_name = plants_dict[plant_id].get('name', plant_name)
                                
                                # Get shuttle name
                                shuttle_name = f"Shuttle {op['shuttle_id']}"
                                if op['shuttle_id'] in shuttles_dict:
                                    shuttle_name = shuttles_dict[op['shuttle_id']].get('name', shuttle_name)
                                
                                violations['worker'].append({
                                    'plant_id': plant_id,
                                    'plant_name': plant_name,
                                    'start_time': start,
                                    'end_time': end,
                                    'capacity': worker_capacity,
                                    'total_usage': worker_usage,
                                    'shuttles': [op['shuttle_id']],
                                    'shuttle_names': [shuttle_name]
                                })
        
        return {
            "violations": {
                "ramp": len(violations["ramp"]),
                "worker": len(violations["worker"]),
                "details": violations
            }
        }
    
    @classmethod
    def export_to_excel(cls, result_id, filename=None):
        """
        Export a RCMPSP result to Excel, with one sheet per shuttle.
        
        Args:
            result_id (int): ID of the result to export
            filename (str, optional): Target filename, if None one will be generated
            
        Returns:
            tuple: (success, message, filename)
        """
        try:
            import pandas as pd
            import os
            from datetime import datetime
            from models import Shuttle
            from models import Plant
            
            # Get the result with operation details
            result = cls.get_result_by_id(result_id)
            if not result:
                return (False, "Result not found", None)
            
            # Generate filename if not provided
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                
                # Get the absolute path to the exports directory
                # First get the directory of the current file
                current_dir = os.path.dirname(os.path.abspath(__file__))
                
                # Then navigate to the static/exports directory
                # Go up one level from current directory (models/rcmpsp) to models
                parent_dir = os.path.dirname(current_dir)
                # Go up one more level to application root
                app_root = os.path.dirname(parent_dir)
                
                # Create the exports directory path
                exports_dir = os.path.join(app_root, 'static', 'exports')
                
                # Ensure directory exists
                os.makedirs(exports_dir, exist_ok=True)
                
                # Create full filename path
                filename = os.path.join(exports_dir, f"rcmpsp_result_{result_id}_{timestamp}.xlsx")
            
            # Get plants for display
            plants = Plant.get_all()
            plants_dict = {plant['identifier']: plant for plant in plants}
            
            # Get shuttles for display
            shuttles = Shuttle.get_all()
            shuttles_dict = {shuttle['id']: shuttle for shuttle in shuttles}
            
            # Group operations by shuttle_id
            operations_by_shuttle = {}
            for op in result.get('operations', []):
                shuttle_id = op.get('shuttle_id')
                if not shuttle_id:
                    continue
                    
                if shuttle_id not in operations_by_shuttle:
                    operations_by_shuttle[shuttle_id] = []
                    
                operations_by_shuttle[shuttle_id].append(op)
            
            # Create Excel writer
            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                # Rest of the method remains the same
                # Process each shuttle
                for shuttle_id, operations in operations_by_shuttle.items():
                    shuttle = shuttles_dict.get(shuttle_id, {'name': f"Shuttle {shuttle_id}"})
                    shuttle_name = shuttle.get('name', f"Shuttle {shuttle_id}")
                    shuttle_type = shuttle.get('shuttle_type', 'Unknown')
                    shift_length = shuttle.get('shift_length', 8)
                    capacity = shuttle.get('capacity', 40)
                    
                    # Sort operations by start_time
                    operations.sort(key=lambda x: x.get('start_time', ''))
                    
                    # Create a list for DataFrame rows
                    rows = []
                    
                    # Track the current plant to properly associate operations
                    current_plant = None
                    load_unload_ops = []
                    
                    # First pass - extract all operations chronologically
                    chronological_ops = []
                    for op in operations:
                        operation_type = op.get('operation_type', '')
                        
                        # Skip operations without type
                        if not operation_type:
                            continue
                            
                        # Get operation start/end time in HH:MM format
                        start_time = op.get('start_time', '')
                        end_time = op.get('end_time', '')
                        
                        # Convert ISO format to HH:MM if needed
                        if isinstance(start_time, str) and 'T' in start_time:
                            start_time = start_time.split('T')[1][:5]  # Extract HH:MM
                        if isinstance(end_time, str) and 'T' in end_time:
                            end_time = end_time.split('T')[1][:5]  # Extract HH:MM
                        
                        # Round duration to integer
                        duration = round(op.get('duration', 0))
                        
                        # Create a standardized operation record
                        op_record = {
                            'type': operation_type,
                            'start_time': start_time,
                            'end_time': end_time,
                            'duration': duration,
                            'plant_id': op.get('plant_id'),
                            'from_plant_id': op.get('from_plant_id'),
                            'to_plant_id': op.get('to_plant_id'),
                            'frequency_num': op.get('frequency_num', 0),
                            'raw_op': op  # Keep reference to original operation
                        }
                        
                        chronological_ops.append(op_record)
                    
                    # Second pass - process operations into rows with proper grouping
                    for i, op in enumerate(chronological_ops):
                        operation_type = op['type']
                        
                        if operation_type == 'travel':
                            # If we have accumulated load/unload operations, process them first
                            if load_unload_ops:
                                process_load_unload_ops(rows, load_unload_ops, current_plant, plants_dict)
                                load_unload_ops = []
                            
                            # Add travel operation
                            from_plant_id = op['from_plant_id']
                            to_plant_id = op['to_plant_id']
                            
                            from_plant_name = "Unknown"
                            to_plant_name = "Unknown"
                            
                            if from_plant_id in plants_dict:
                                from_plant_name = plants_dict[from_plant_id].get('name', f"Plant {from_plant_id}")
                            
                            if to_plant_id in plants_dict:
                                to_plant_name = plants_dict[to_plant_id].get('name', f"Plant {to_plant_id}")
                            
                            rows.append({
                                'Operation': 'Travel',
                                'Start Time': op['start_time'],
                                'End Time': op['end_time'],
                                'Duration': op['duration'],
                                'From Plant': from_plant_name,
                                'To Plant': to_plant_name,
                                'Plant': ""  # Empty for travel operations
                            })
                            
                            # Update current plant after travel
                            current_plant = to_plant_id
                            
                        elif operation_type in ['load', 'unload']:
                            # Accumulate load/unload operations at the current plant
                            plant_id = op['plant_id']
                            
                            # If this operation is at a different plant, process previous operations first
                            if current_plant is not None and plant_id != current_plant and load_unload_ops:
                                process_load_unload_ops(rows, load_unload_ops, current_plant, plants_dict)
                                load_unload_ops = []
                                current_plant = plant_id
                            
                            # Set current plant if not set yet
                            if current_plant is None:
                                current_plant = plant_id
                                
                            # Add to accumulated operations
                            load_unload_ops.append(op)
                            
                        elif operation_type == 'break' and op['duration'] >= 10:
                            # Process any pending load/unload operations
                            if load_unload_ops:
                                process_load_unload_ops(rows, load_unload_ops, current_plant, plants_dict)
                                load_unload_ops = []
                            
                            # Add break operation directly
                            plant_id = op['plant_id']
                            plant_name = "Unknown"
                            
                            if plant_id in plants_dict:
                                plant_name = plants_dict[plant_id].get('name', f"Plant {plant_id}")
                            
                            rows.append({
                                'Operation': 'Break',
                                'Start Time': op['start_time'],
                                'End Time': op['end_time'],
                                'Duration': op['duration'],
                                'From Plant': "",
                                'To Plant': "",
                                'Plant': plant_name
                            })
                            
                        elif operation_type == 'preprah':
                            # Process any pending load/unload operations
                            if load_unload_ops:
                                process_load_unload_ops(rows, load_unload_ops, current_plant, plants_dict)
                                load_unload_ops = []
                            
                            # Add preprah operation directly
                            plant_id = op['plant_id']
                            plant_name = "Unknown"
                            
                            if plant_id in plants_dict:
                                plant_name = plants_dict[plant_id].get('name', f"Plant {plant_id}")
                            
                            rows.append({
                                'Operation': 'Preprah',
                                'Start Time': op['start_time'],
                                'End Time': op['end_time'],
                                'Duration': op['duration'],
                                'From Plant': "",
                                'To Plant': "",
                                'Plant': plant_name
                            })
                            
                        elif operation_type == 'shift_change':
                            # Process any pending load/unload operations
                            if load_unload_ops:
                                process_load_unload_ops(rows, load_unload_ops, current_plant, plants_dict)
                                load_unload_ops = []
                            
                            # Add shift change operation directly
                            plant_id = op['plant_id']
                            plant_name = "Unknown"
                            
                            if plant_id in plants_dict:
                                plant_name = plants_dict[plant_id].get('name', f"Plant {plant_id}")
                            
                            rows.append({
                                'Operation': 'Shift Change',
                                'Start Time': op['start_time'],
                                'End Time': op['end_time'],
                                'Duration': op['duration'],
                                'From Plant': "",
                                'To Plant': "",
                                'Plant': plant_name
                            })
                    
                    # Process any remaining load/unload operations
                    if load_unload_ops:
                        process_load_unload_ops(rows, load_unload_ops, current_plant, plants_dict)
                    
                    # Create DataFrame and write to Excel
                    if rows:
                        # Define column order and names
                        columns = [
                            'Operation', 
                            'Start Time', 
                            'End Time', 
                            'Duration', 
                            'From Plant', 
                            'To Plant', 
                            'Plant'
                        ]
                        
                        df = pd.DataFrame(rows, columns=columns)
                        
                        # Get shuttle color for styling
                        shuttle_color = shuttle.get('color', '#0d6efd')
                        
                        # Create sheet with shuttle name
                        sheet_name = f"Shuttle {shuttle_id}"
                        if len(sheet_name) > 31:  # Excel limitation
                            sheet_name = sheet_name[:31]
                            
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        
                        # Get workbook and sheet references
                        workbook = writer.book
                        worksheet = writer.sheets[sheet_name]
                        
                        # Add header with shuttle name and details
                        header_format = workbook.add_format({
                            'bold': True,
                            'font_size': 14,
                            'bg_color': shuttle_color,
                            'font_color': '#FFFFFF',
                            'align': 'center',
                            'valign': 'vcenter',
                            'border': 1
                        })
                        
                        # Create shuttle info text
                        shuttle_info = f"Type: {shuttle_type.capitalize()}, Shift: {shift_length} hours, Capacity: {capacity} pallets"
                        
                        # Merge cells for header and info
                        worksheet.merge_range('A1:G1', f"Schedule for {shuttle_name}", header_format)
                        
                        # Add shuttle info row
                        info_format = workbook.add_format({
                            'italic': True,
                            'bg_color': '#F0F0F0',
                            'align': 'center',
                            'valign': 'vcenter',
                            'border': 1
                        })
                        worksheet.merge_range('A2:G2', shuttle_info, info_format)
                        
                        # Add column headers
                        header_format = workbook.add_format({
                            'bold': True,
                            'bg_color': '#D9D9D9',
                            'border': 1
                        })
                        
                        # Set column headers manually for better control
                        for col_num, column in enumerate(columns):
                            worksheet.write(2, col_num, column, header_format)
                        
                        # Set column widths
                        worksheet.set_column('A:A', 15)  # Operation
                        worksheet.set_column('B:C', 12)  # Start/End Time
                        worksheet.set_column('D:D', 10)  # Duration
                        worksheet.set_column('E:F', 20)  # From/To Plant
                        worksheet.set_column('G:G', 20)  # Plant
                        
                        # Apply data format to all rows
                        data_format = workbook.add_format({
                            'border': 1,
                            'valign': 'vcenter'
                        })
                        
                        # Apply formatting to data cells
                        for row_num in range(3, len(df) + 3):
                            for col_num in range(len(columns)):
                                worksheet.write(row_num, col_num, df.iloc[row_num-3, col_num], data_format)
            
            return (True, "Export successful", filename)
            
        except Exception as e:
            import traceback
            return (False, f"Error exporting to Excel: {str(e)}\n{traceback.format_exc()}", None)

def process_load_unload_ops(rows_list, operations, plant_id, plants_dict):
    """
    Process accumulated load/unload operations at a single plant.
    
    Args:
        rows_list (list): List to append rows to
        operations (list): List of operations at the plant
        plant_id: Plant identifier
        plants_dict: Dictionary of plants by identifier
    """
    if not operations:
        return
    
    # Get plant name
    plant_name = "Unknown"
    if plant_id in plants_dict:
        plant_name = plants_dict[plant_id].get('name', f"Plant {plant_id}")
    
    # Group by operation type
    load_ops = [op for op in operations if op['type'] == 'load']
    unload_ops = [op for op in operations if op['type'] == 'unload']
    
    # Process unloads first (chronologically they typically happen before loading)
    if unload_ops:
        # Get first start time and last end time
        start_time = min(unload_ops, key=lambda x: x['start_time'])['start_time']
        end_time = max(unload_ops, key=lambda x: x['end_time'])['end_time']
        total_duration = sum(op['duration'] for op in unload_ops)
        
        rows_list.append({
            'Operation': 'Unload',
            'Start Time': start_time,
            'End Time': end_time,
            'Duration': round(total_duration),
            'From Plant': "",
            'To Plant': "",
            'Plant': plant_name
        })
    
    # Process loads
    if load_ops:
        # Get first start time and last end time
        start_time = min(load_ops, key=lambda x: x['start_time'])['start_time']
        end_time = max(load_ops, key=lambda x: x['end_time'])['end_time']
        total_duration = sum(op['duration'] for op in load_ops)
        
        rows_list.append({
            'Operation': 'Load',
            'Start Time': start_time,
            'End Time': end_time,
            'Duration': round(total_duration),
            'From Plant': "",
            'To Plant': "",
            'Plant': plant_name
        })