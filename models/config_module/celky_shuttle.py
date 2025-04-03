"""
CelkyShuttle model for assigning celky (transportation segments) to shuttles.
"""
import json
import math
from models.base import Model
import sqlite3
import pandas as pd
from datetime import datetime

class CelkyShuttle(Model):
    """Model for assigning celky to shuttles."""
    
    table_name = 'celky_shuttle'

    @classmethod
    def create_table(cls, force_reset=False):
        """
        Create the celky_shuttle table if it doesn't exist.
        
        Args:
            force_reset (bool): If True, drop and recreate the table
        """
        conn = cls.get_db_connection()
        cursor = conn.cursor()
        
        if force_reset:
            cursor.execute(f"DROP TABLE IF EXISTS {cls.table_name}")
        
        cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {cls.table_name} (
            id INTEGER PRIMARY KEY,
            shuttle_id INTEGER NOT NULL,
            celky_id INTEGER NOT NULL,
            route_order INTEGER NOT NULL,
            planned_start_time TEXT,
            schedule_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            FOREIGN KEY (shuttle_id) REFERENCES shuttles (id) ON DELETE CASCADE,
            FOREIGN KEY (celky_id) REFERENCES celky (id) ON DELETE CASCADE,
            UNIQUE(shuttle_id, celky_id, schedule_id)
        )
        ''')
        
        # Create indexes for faster lookups
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_shuttle_id ON {cls.table_name}(shuttle_id)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_celky_id ON {cls.table_name}(celky_id)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_schedule_id ON {cls.table_name}(schedule_id)")
        
        conn.commit()
        conn.close()

    @classmethod
    def init_db(cls, force_reset=False):
        """
        Initialize the database with the celky_shuttle table.
        
        Args:
            force_reset (bool): If True, reset the database to default values
        """
        import time
        
        # Create the table first

        cls.create_table(force_reset)
        
        # If force reset, delete data
        if force_reset:
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    conn = cls.get_db_connection()
                    conn.execute("PRAGMA busy_timeout = 5000")  # Set timeout to 5 seconds
                    cursor = conn.cursor()
                    
                    # Delete data
                    cursor.execute(f"DELETE FROM {cls.table_name}")
                    
                    conn.commit()
                    conn.close()
                    break  # Success, exit the retry loop
                    
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e) and attempt < max_attempts - 1:
                        print(f"Database locked during deletion, retrying... (attempt {attempt+1}/{max_attempts})")
                        if 'conn' in locals() and conn:
                            conn.close()
                        time.sleep(1)  # Wait before retrying
                        continue
                    else:
                        print(f"Error deleting data: {e}")
                        if 'conn' in locals() and conn:
                            conn.close()
                        raise
        
        # Wait a moment to let any previous transactions complete
        time.sleep(0.5)
        
        # Import and initialize statistics tables 
        from models.config_module.shuttle_statistics import ShuttleStatistics
        try:
            ShuttleStatistics.init_db(force_reset)
        except Exception as e:
            print(f"Warning during statistics initialization: {e}")
            # Continue anyway


    @classmethod
    def assign_celky_to_shuttle(cls, shuttle_id, celky_id, route_order, planned_start_time=None, 
                               planned_duration=None, schedule_id=None):
        """
        Assign a celky to a shuttle.
        
        Args:
            shuttle_id (int): ID of the shuttle
            celky_id (int): ID of the celky
            route_order (int): Order in the route sequence
            planned_start_time (str, optional): Planned start time in 'HH:MM' format
            planned_duration (int, optional): Planned duration in minutes
            schedule_id (int, optional): ID of the schedule this assignment belongs to
            
        Returns:
            tuple: (success, message, id)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Check if shuttle exists
            cursor.execute("SELECT id FROM shuttles WHERE id = ?", (shuttle_id,))
            if not cursor.fetchone():
                return (False, f"Shuttle with ID {shuttle_id} not found", None)
            
            # Check if celky exists
            cursor.execute("SELECT id FROM celky WHERE id = ?", (celky_id,))
            if not cursor.fetchone():
                return (False, f"Celky with ID {celky_id} not found", None)
            
            # Check if this assignment already exists for the same schedule
            if schedule_id is not None:
                cursor.execute(
                    f"SELECT id FROM {cls.table_name} WHERE shuttle_id = ? AND celky_id = ? AND schedule_id = ?",
                    (shuttle_id, celky_id, schedule_id)
                )
                existing = cursor.fetchone()
                if existing:
                    return (False, f"This celky is already assigned to this shuttle in the same schedule", None)
            
            # Format planned_start_time if provided
            formatted_time = None
            if planned_start_time:
                # Normalize time format to HH:MM
                if isinstance(planned_start_time, str):
                    formatted_time = planned_start_time
                    
            now = datetime.now().isoformat()
            
            # Insert the assignment
            cursor.execute(
                f"""
                INSERT INTO {cls.table_name} 
                (shuttle_id, celky_id, route_order, planned_start_time, 
                planned_duration, schedule_id, created_at, updated_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (shuttle_id, celky_id, route_order, formatted_time, 
                planned_duration, schedule_id, now, now)
            )
            
            assignment_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return (True, "Celky assigned to shuttle successfully", assignment_id)
        except Exception as e:
            return (False, f"Error assigning celky to shuttle: {str(e)}", None)
    
    @classmethod
    def get_assignments_by_schedule(cls, schedule_id):
        """
        Get all assignments for a specific schedule.
        
        Args:
            schedule_id (int): ID of the schedule
            
        Returns:
            list: List of dictionaries containing assignments
        """
        conn = cls.get_db_connection()
        cursor = conn.cursor()
        
        query = f"""
        SELECT cs.*, 
               s.name as shuttle_name, s.capacity, s.shuttle_type, s.shift_length,
               c.name as celky_name, c.source_plant, c.dest_plant, c.transport_type
        FROM {cls.table_name} cs
        JOIN shuttles s ON cs.shuttle_id = s.id
        JOIN celky c ON cs.celky_id = c.id
        WHERE cs.schedule_id = ?
        ORDER BY s.id, cs.route_order
        """
        
        cursor.execute(query, (schedule_id,))
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        result = [dict(row) for row in rows]
        
        conn.close()
        return result
        
    # @classmethod
    # def update_assignment(cls, assignment_id, data):
    #     """
    #     Update a celky-shuttle assignment.
        
    #     Args:
    #         assignment_id (int): ID of the assignment to update
    #         data (dict): Dictionary containing the updated assignment details
            
    #     Returns:
    #         tuple: (success, message)
    #     """
    #     try:
    #         conn = cls.get_db_connection()
    #         cursor = conn.cursor()
            
    #         # Check if assignment exists
    #         cursor.execute(f"SELECT * FROM {cls.table_name} WHERE id = ?", (assignment_id,))
    #         if not cursor.fetchone():
    #             return (False, f"Assignment with ID {assignment_id} not found")
            
    #         # Prepare update statement
    #         update_fields = []
    #         values = []
            
    #         # Add each field to the update if it exists in the data
    #         if 'route_order' in data:
    #             update_fields.append("route_order = ?")
    #             values.append(data['route_order'])
            
    #         if 'planned_start_time' in data:
    #             update_fields.append("planned_start_time = ?")
    #             values.append(data['planned_start_time'])
            
    #         if 'planned_duration' in data:
    #             update_fields.append("planned_duration = ?")
    #             values.append(data['planned_duration'])
            
    #         if 'schedule_id' in data:
    #             update_fields.append("schedule_id = ?")
    #             values.append(data['schedule_id'])
            
    #         if not update_fields:
    #             return (True, "No changes to update")
            
    #         # Add updated_at field
    #         update_fields.append("updated_at = ?")
    #         values.append(datetime.now().isoformat())
            
    #         # Add ID to values for the WHERE clause
    #         values.append(assignment_id)
            
    #         # Execute update
    #         cursor.execute(
    #             f"UPDATE {cls.table_name} SET {', '.join(update_fields)} WHERE id = ?",
    #             values
    #         )
            
    #         conn.commit()
    #         conn.close()
            
    #         return (True, "Assignment updated successfully")
    #     except Exception as e:
    #         return (False, f"Error updating assignment: {str(e)}")
    
    # @classmethod
    # def delete_assignment(cls, assignment_id):
    #     """
    #     Delete a celky-shuttle assignment.
        
    #     Args:
    #         assignment_id (int): ID of the assignment to delete
            
    #     Returns:
    #         tuple: (success, message)
    #     """
    #     try:
    #         conn = cls.get_db_connection()
    #         cursor = conn.cursor()
            
    #         # Check if assignment exists
    #         cursor.execute(f"SELECT * FROM {cls.table_name} WHERE id = ?", (assignment_id,))
    #         if not cursor.fetchone():
    #             return (False, f"Assignment with ID {assignment_id} not found")
            
    #         # Delete the assignment
    #         cursor.execute(f"DELETE FROM {cls.table_name} WHERE id = ?", (assignment_id,))
            
    #         conn.commit()
    #         conn.close()
            
    #         return (True, "Assignment deleted successfully")
    #     except Exception as e:
    #         return (False, f"Error deleting assignment: {str(e)}")
    
    # @classmethod
    # def get_shuttle_assignments(cls, shuttle_id, schedule_id=None):
    #     """
    #     Get all assignments for a specific shuttle.
        
    #     Args:
    #         shuttle_id (int): ID of the shuttle
    #         schedule_id (int, optional): ID of the schedule
            
    #     Returns:
    #         list: List of dictionaries containing assignments
    #     """
    #     conn = cls.get_db_connection()
    #     cursor = conn.cursor()
        
    #     query = f"""
    #     SELECT cs.*, c.name as celky_name, c.source_plant, c.dest_plant, c.transport_type
    #     FROM {cls.table_name} cs
    #     JOIN celky c ON cs.celky_id = c.id
    #     WHERE cs.shuttle_id = ?
    #     """
    #     params = [shuttle_id]
        
    #     if schedule_id is not None:
    #         query += " AND cs.schedule_id = ?"
    #         params.append(schedule_id)
        
    #     query += " ORDER BY cs.route_order"
        
    #     cursor.execute(query, params)
    #     rows = cursor.fetchall()
        
    #     # Convert to list of dictionaries
    #     result = [dict(row) for row in rows]
        
    #     conn.close()
    #     return result
    
    # @classmethod
    # def get_celky_assignments(cls, celky_id):
    #     """
    #     Get all assignments for a specific celky.
        
    #     Args:
    #         celky_id (int): ID of the celky
            
    #     Returns:
    #         list: List of dictionaries containing assignments
    #     """
    #     conn = cls.get_db_connection()
    #     cursor = conn.cursor()
        
    #     query = f"""
    #     SELECT cs.*, s.name as shuttle_name, s.capacity, s.shuttle_type, s.shift_length
    #     FROM {cls.table_name} cs
    #     JOIN shuttles s ON cs.shuttle_id = s.id
    #     WHERE cs.celky_id = ?
    #     ORDER BY cs.schedule_id, cs.route_order
    #     """
        
    #     cursor.execute(query, (celky_id,))
    #     rows = cursor.fetchall()
        
    #     # Convert to list of dictionaries
    #     result = [dict(row) for row in rows]
        
    #     conn.close()
    #     return result

    # @classmethod
    # def get_as_dataframe(cls, schedule_id=None):
    #     """
    #     Get assignments as a pandas DataFrame.
        
    #     Args:
    #         schedule_id (int, optional): ID of the schedule
            
    #     Returns:
    #         pd.DataFrame: DataFrame containing assignments
    #     """
    #     conn = cls.get_db_connection()
        
    #     query = f"""
    #     SELECT cs.*, 
    #            s.name as shuttle_name, s.capacity, s.shuttle_type, s.shift_length,
    #            c.name as celky_name, c.source_plant, c.dest_plant, c.transport_type
    #     FROM {cls.table_name} cs
    #     JOIN shuttles s ON cs.shuttle_id = s.id
    #     JOIN celky c ON cs.celky_id = c.id
    #     """
        
    #     params = None
    #     if schedule_id is not None:
    #         query += " WHERE cs.schedule_id = ?"
    #         params = (schedule_id,)
        
    #     query += " ORDER BY s.id, cs.route_order"
        
    #     if params:
    #         df = pd.read_sql(query, conn, params=params)
    #     else:
    #         df = pd.read_sql(query, conn)
            
    #     conn.close()
    #     return df