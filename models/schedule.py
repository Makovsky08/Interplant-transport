"""
Schedule model for managing transportation schedules.
"""
from models.base import Model
import sqlite3
import pandas as pd
from datetime import datetime

class Schedule(Model):
    """Model for managing transportation schedules."""
    
    table_name = 'schedules'
    
    @classmethod
    def create_table(cls, force_reset=False):
        """
        Create the schedules table if it doesn't exist.
        
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
            name TEXT NOT NULL,
            description TEXT,
            valid_from TEXT,
            valid_to TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            is_active INTEGER DEFAULT 0,
            is_template INTEGER DEFAULT 0,
            created_by TEXT
        )
        ''')
        
        conn.commit()
        conn.close()
    
    @classmethod
    def init_db(cls, force_reset=False):
        """
        Initialize the database with the schedules table.
        
        Args:
            force_reset (bool): If True, reset the database to default values
        """
        # Create the table
        cls.create_table(force_reset)
        
        conn = cls.get_db_connection()
        cursor = conn.cursor()
        
        # Check if the table is empty
        cursor.execute(f"SELECT COUNT(*) FROM {cls.table_name}")
        count = cursor.fetchone()[0]
        
        # Populate with sample data if empty or force reset is requested
        if count == 0 or force_reset:
            # Sample data
            now = datetime.now().isoformat()
            sample_data = [
                (1, "Default Schedule", "Default weekly schedule", None, None, now, now, 1, 0, "admin"),
                (2, "Summer Template", "Template for summer schedule", None, None, now, now, 0, 1, "admin")
            ]
            
            cursor.executemany(
                f"INSERT INTO {cls.table_name} (id, name, description, valid_from, valid_to, created_at, updated_at, is_active, is_template, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                sample_data
            )
        
        conn.commit()
        conn.close()
    
    @classmethod
    def get_all(cls):
        """
        Retrieve all schedules from the database.
        
        Returns:
            list: List of dictionaries containing all schedules
        """
        conn = cls.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {cls.table_name} ORDER BY id")
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        result = [dict(row) for row in rows]
        
        conn.close()
        return result
    
    @classmethod
    def get_active_schedule(cls):
        """
        Get the currently active schedule.
        
        Returns:
            dict: Dictionary containing the active schedule or None if not found
        """
        conn = cls.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {cls.table_name} WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    @classmethod
    def get_templates(cls):
        """
        Get all schedule templates.
        
        Returns:
            list: List of dictionaries containing all schedule templates
        """
        conn = cls.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {cls.table_name} WHERE is_template = 1 ORDER BY id")
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        result = [dict(row) for row in rows]
        
        conn.close()
        return result
    
    @classmethod
    def get_by_id(cls, id):
        """
        Retrieve a specific schedule by ID.
        
        Args:
            id (int): ID of the schedule to retrieve
            
        Returns:
            dict: Dictionary containing the schedule details or None if not found
        """
        conn = cls.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {cls.table_name} WHERE id = ?", (id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    @classmethod
    def create_schedule(cls, name, description=None, valid_from=None, valid_to=None, 
                       is_template=False, created_by=None):
        """
        Create a new schedule.
        
        Args:
            name (str): Name of the schedule
            description (str, optional): Description of the schedule
            valid_from (str, optional): Start date of validity in ISO format
            valid_to (str, optional): End date of validity in ISO format
            is_template (bool, optional): Whether this is a template schedule
            created_by (str, optional): Username of the creator
            
        Returns:
            tuple: (success, message, id)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            # Insert the schedule
            cursor.execute(
                f"""
                INSERT INTO {cls.table_name} 
                (name, description, valid_from, valid_to, created_at, updated_at, is_active, is_template, created_by) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, description, valid_from, valid_to, now, now, 0, 1 if is_template else 0, created_by)
            )
            
            schedule_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return (True, "Schedule created successfully", schedule_id)
        except Exception as e:
            return (False, f"Error creating schedule: {str(e)}", None)
    
    @classmethod
    def update_schedule(cls, id, data):
        """
        Update an existing schedule.
        
        Args:
            id (int): ID of the schedule to update
            data (dict): Dictionary containing the updated schedule details
            
        Returns:
            tuple: (success, message)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Check if the schedule exists
            cursor.execute(f"SELECT * FROM {cls.table_name} WHERE id = ?", (id,))
            if not cursor.fetchone():
                return (False, f"Schedule with ID {id} not found")
            
            # Prepare update statement
            update_fields = []
            values = []
            
            # Add each field to the update if it exists in the data
            if 'name' in data:
                update_fields.append("name = ?")
                values.append(data['name'])
            
            if 'description' in data:
                update_fields.append("description = ?")
                values.append(data['description'])
            
            if 'valid_from' in data:
                update_fields.append("valid_from = ?")
                values.append(data['valid_from'])
            
            if 'valid_to' in data:
                update_fields.append("valid_to = ?")
                values.append(data['valid_to'])
            
            if 'is_active' in data:
                # If setting this schedule to active, deactivate all others
                if data['is_active']:
                    cursor.execute(f"UPDATE {cls.table_name} SET is_active = 0 WHERE id != ?", (id,))
                
                update_fields.append("is_active = ?")
                values.append(1 if data['is_active'] else 0)
            
            if 'is_template' in data:
                update_fields.append("is_template = ?")
                values.append(1 if data['is_template'] else 0)
            
            if not update_fields:
                return (True, "No changes to update")
            
            # Add updated_at field
            update_fields.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            
            # Add ID to values for the WHERE clause
            values.append(id)
            
            # Execute update
            cursor.execute(
                f"UPDATE {cls.table_name} SET {', '.join(update_fields)} WHERE id = ?",
                values
            )
            
            conn.commit()
            conn.close()
            
            return (True, "Schedule updated successfully")
        except Exception as e:
            return (False, f"Error updating schedule: {str(e)}")
    
    @classmethod
    def delete_schedule(cls, id):
        """
        Delete a schedule.
        
        Args:
            id (int): ID of the schedule to delete
            
        Returns:
            tuple: (success, message)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Check if the schedule exists
            cursor.execute(f"SELECT * FROM {cls.table_name} WHERE id = ?", (id,))
            if not cursor.fetchone():
                return (False, f"Schedule with ID {id} not found")
            
            # Check if it's the active schedule
            cursor.execute(f"SELECT is_active FROM {cls.table_name} WHERE id = ?", (id,))
            is_active = cursor.fetchone()['is_active']
            if is_active:
                return (False, "Cannot delete the active schedule")
            
            # Delete the schedule
            cursor.execute(f"DELETE FROM {cls.table_name} WHERE id = ?", (id,))
            
            conn.commit()
            conn.close()
            
            return (True, "Schedule deleted successfully")
        except Exception as e:
            return (False, f"Error deleting schedule: {str(e)}")
    
    @classmethod
    def copy_schedule(cls, id, new_name, as_template=False):
        """
        Create a copy of an existing schedule.
        
        Args:
            id (int): ID of the schedule to copy
            new_name (str): Name for the new schedule
            as_template (bool, optional): Whether to save as a template
            
        Returns:
            tuple: (success, message, new_id)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Check if the source schedule exists
            cursor.execute(f"SELECT * FROM {cls.table_name} WHERE id = ?", (id,))
            schedule = cursor.fetchone()
            if not schedule:
                return (False, f"Schedule with ID {id} not found", None)
            
            # Create new schedule
            now = datetime.now().isoformat()
            cursor.execute(
                f"""
                INSERT INTO {cls.table_name} 
                (name, description, valid_from, valid_to, created_at, updated_at, 
                is_active, is_template, created_by) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (new_name, f"Copy of {schedule['name']}", schedule['valid_from'], 
                schedule['valid_to'], now, now, 0, 1 if as_template else 0, 
                schedule['created_by'])
            )
            
            new_id = cursor.lastrowid
            
            # Copy assigned celky from source schedule to the new one
            cursor.execute(
                """
                INSERT INTO celky_shuttle 
                (shuttle_id, celky_id, route_order, planned_start_time, planned_duration,
                schedule_id, created_at, updated_at)
                SELECT shuttle_id, celky_id, route_order, planned_start_time, planned_duration,
                ?, ?, ?
                FROM celky_shuttle
                WHERE schedule_id = ?
                """,
                (new_id, now, now, id)
            )
            
            conn.commit()
            conn.close()
            
            return (True, "Schedule copied successfully", new_id)
        except Exception as e:
            return (False, f"Error copying schedule: {str(e)}", None)
    
    @classmethod
    def activate_schedule(cls, id):
        """
        Activate a schedule (set as current active schedule).
        
        Args:
            id (int): ID of the schedule to activate
            
        Returns:
            tuple: (success, message)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Check if the schedule exists
            cursor.execute(f"SELECT * FROM {cls.table_name} WHERE id = ?", (id,))
            if not cursor.fetchone():
                return (False, f"Schedule with ID {id} not found")
            
            # Deactivate all schedules
            cursor.execute(f"UPDATE {cls.table_name} SET is_active = 0")
            
            # Activate the selected schedule
            cursor.execute(f"UPDATE {cls.table_name} SET is_active = 1 WHERE id = ?", (id,))
            
            conn.commit()
            conn.close()
            
            return (True, "Schedule activated successfully")
        except Exception as e:
            return (False, f"Error activating schedule: {str(e)}")
    
    @classmethod
    def get_as_dataframe(cls):
        """
        Get all schedules as a pandas DataFrame.
        
        Returns:
            pd.DataFrame: DataFrame containing all schedules
        """
        conn = cls.get_db_connection()
        df = pd.read_sql(f"SELECT * FROM {cls.table_name} ORDER BY id", conn)
        conn.close()
        return df