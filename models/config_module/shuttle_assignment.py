from models.config_module.celky_shuttle import CelkyShuttle
from models.config_module.shuttle_statistics import ShuttleStatistics
from datetime import datetime
import json

class ShuttleAssignment:
    """
    Class for managing assignments of celky to shuttles.
    Provides methods for saving, clearing, and retrieving assignments with statistics.
    """
    
    @staticmethod
    def save_assignments_with_statistics(shuttle_id, celky_ids, route_order_map, start_times_map, schedule_id, statistics):
        """
        Save multiple celky assignments to a shuttle with route statistics.
        
        Args:
            shuttle_id (int): ID of the shuttle
            celky_ids (list): List of celky IDs
            route_order_map (dict): Map of celky_id to route_order
            start_times_map (dict): Map of celky_id to planned_start_time
            schedule_id (int): ID of the schedule
            statistics (dict): Statistics calculated for this route
            
        Returns:
            tuple: (success, message, assignment_ids)
        """
        try:
            conn = CelkyShuttle.get_db_connection()
            cursor = conn.cursor()
            
            # Begin transaction
            conn.execute("BEGIN TRANSACTION")
            
            # First, delete any existing assignments for this shuttle in this schedule
            cursor.execute(
                "DELETE FROM celky_shuttle WHERE shuttle_id = ? AND schedule_id = ?",
                (shuttle_id, schedule_id)
            )
            
            # Insert new assignments
            now = datetime.now().isoformat()
            assignment_ids = []
            
            for celky_id in celky_ids:
                route_order = route_order_map.get(str(celky_id), len(assignment_ids) + 1)
                planned_start_time = start_times_map.get(str(celky_id))
                
                cursor.execute(
                    """
                    INSERT INTO celky_shuttle 
                    (shuttle_id, celky_id, route_order, planned_start_time, 
                    schedule_id, created_at, updated_at) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (shuttle_id, celky_id, route_order, planned_start_time, 
                    schedule_id, now, now)
                )
                
                assignment_id = cursor.lastrowid
                assignment_ids.append(assignment_id)
            
            # Commit the assignments
            conn.commit()
            conn.close()
            
            # If we have valid statistics, save them directly with shuttle_id and schedule_id
            if statistics and len(celky_ids) > 0:
                # Save statistics using ShuttleStatistics class with the new method signature
                success, message, stats_id = ShuttleStatistics.save_statistics(
                    shuttle_id, schedule_id, statistics
                )
                
                if not success:
                    print(f"Warning: Failed to save statistics: {message}")
            
            return (True, "Assignments saved successfully", assignment_ids)
        except Exception as e:
            # Rollback in case of error
            if 'conn' in locals() and conn:
                conn.rollback()
                conn.close()
            return (False, f"Error saving assignments: {str(e)}", [])
    
    @staticmethod
    def clear_shuttle_assignments(shuttle_id, schedule_id):
        """
        Clear all assignments for a specific shuttle in a schedule.
        
        Args:
            shuttle_id (int): ID of the shuttle
            schedule_id (int): ID of the schedule
            
        Returns:
            tuple: (success, message)
        """
        try:
            conn = CelkyShuttle.get_db_connection()
            cursor = conn.cursor()
            
            # Begin transaction
            conn.execute("BEGIN TRANSACTION")
            
            # Delete all assignments for this shuttle in this schedule
            cursor.execute(
                "DELETE FROM celky_shuttle WHERE shuttle_id = ? AND schedule_id = ?",
                (shuttle_id, schedule_id)
            )
            
            conn.commit()
            conn.close()
            
            # Delete associated statistics directly using shuttle_id and schedule_id
            ShuttleStatistics.delete_for_shuttle_and_schedule(shuttle_id, schedule_id)
            
            return (True, "Assignments cleared successfully")
        except Exception as e:
            if 'conn' in locals() and conn:
                conn.rollback()
                conn.close()
            return (False, f"Error clearing assignments: {str(e)}")
    
    @staticmethod
    def get_assignment_statistics(shuttle_id, schedule_id):
        """
        Get statistics for a specific shuttle's assignments.
        
        Args:
            shuttle_id (int): ID of the shuttle
            schedule_id (int): ID of the schedule
            
        Returns:
            dict: Statistics for the shuttle's assignments or None if not found
        """
        return ShuttleStatistics.get_by_shuttle_and_schedule(shuttle_id, schedule_id)
    