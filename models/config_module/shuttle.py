"""
Shuttle model for inter-facility transportation system.
"""
from models.base import Model
import sqlite3
import pandas as pd

class Shuttle(Model):
    """Model for shuttles used in transportation."""
    
    table_name = 'shuttles'
    
    @classmethod
    def create_table(cls, force_reset=False):
        """
        Create the shuttles table if it doesn't exist.
        
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
            capacity INTEGER NOT NULL,
            shuttle_type TEXT NOT NULL, 
            shift_length INTEGER NOT NULL,
            break_time INTEGER NOT NULL,
            break_each INTEGER NOT NULL,
            time_for_shift_change INTEGER NOT NULL,
            shift_change_dest INTEGER,
            preprah_length INTEGER DEFAULT 0,
            preprah_destination INTEGER,
            active INTEGER DEFAULT 1,
            color TEXT DEFAULT NULL
        )
        ''')
        
        conn.commit()
        conn.close()
    
    @classmethod
    def init_db(cls, force_reset=False):
        """
        Initialize the database with the shuttles table and sample data if needed.
        
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
            sample_data = [
                (1, 'Shuttle 1', 40, 'naves', 8, 30, 240, 15, 4, 0, None, 1, '#FFFFFF'),
                (2, 'Shuttle 2', 40, 'naves', 8, 30, 240, 15, 4, 0, None, 1, '#FFFFFF'),
                (3, 'Shuttle 3', 40, 'naves', 12, 60, 240, 15, 4, 0, None, 1, '#FFFFFF'),
                (4, 'Shuttle 4', 40, 'preprah', 8, 30, 240, 15, 4, 0, None, 1, '#FFFFFF'),
                (5, 'Shuttle 5', 35, 'preprah', 12, 60, 240, 15, 4, 0, None, 1, '#FFFFFF')
            ]
            
            cursor.executemany(
                f"""
                INSERT INTO {cls.table_name} 
                (id, name, capacity, shuttle_type, shift_length, break_time, break_each, 
                time_for_shift_change, shift_change_dest, preprah_length, preprah_destination, active, color) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                sample_data
            )
        
        conn.commit()
        conn.close()
    
    @classmethod
    def get_all(cls, active_only=False):
        """
        Retrieve all shuttles from the database.
        
        Args:
            active_only (bool): If True, retrieve only active shuttles
            
        Returns:
            list: List of dictionaries containing shuttles
        """
        conn = cls.get_db_connection()
        cursor = conn.cursor()
        
        query = f"SELECT * FROM {cls.table_name}"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY id"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        result = [dict(row) for row in rows]
        
        conn.close()
        return result
    
    @classmethod
    def get_by_id(cls, id):
        """
        Retrieve a specific shuttle by ID.
        
        Args:
            id (int): ID of the shuttle to retrieve
            
        Returns:
            dict: Dictionary containing the shuttle details or None if not found
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
    def add(cls, data):
        """
        Add a new shuttle to the database.
        
        Args:
            data (dict): Dictionary containing the shuttle details
            
        Returns:
            tuple: (success, message/error, id)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Validate required fields
            required_fields = ['name', 'capacity', 'shuttle_type', 'shift_length', 
                             'break_time', 'break_each', 'time_for_shift_change', 'color']
            for field in required_fields:
                if field not in data or not data[field]:
                    return (False, f"Missing required field: {field}", None)
            
            # Validate numeric fields
            numeric_fields = ['capacity', 'shift_length', 'break_time', 'break_each', 'time_for_shift_change']
            for field in numeric_fields:
                if field in data and not str(data[field]).isdigit():
                    return (False, f"Field {field} must be a number", None)
            
            # Validate shuttle_type
            if data['shuttle_type'] not in ['naves', 'preprah']:
                return (False, "Shuttle type must be either 'naves' or 'preprah'", None)
            
            # Validate shift_length
            if data['shift_length'] not in [8, 12]:
                return (False, "Shift length must be either 8 or 12 hours", None)
            
            # Insert shuttle data
            cursor.execute(
                f"""
                INSERT INTO {cls.table_name} 
                (name, capacity, shuttle_type, shift_length, break_time, break_each, 
                time_for_shift_change, shift_change_dest, preprah_length, preprah_destination, active, color) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data['name'],
                    int(data['capacity']),
                    data['shuttle_type'],
                    int(data['shift_length']),
                    int(data['break_time']),
                    int(data['break_each']),
                    int(data['time_for_shift_change']),
                    data.get('shift_change_dest', 4),  # Default to plant 4 (Jipocar C)
                    data.get('preprah_length', 0),     # Default to 0
                    data.get('preprah_destination'),   # Default to NULL
                    data.get('active', 1),
                    data.get('color')
                )
            )
            
            shuttle_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return (True, "Shuttle added successfully", shuttle_id)
        except Exception as e:
            return (False, f"Error adding shuttle: {str(e)}", None)
    
    @classmethod
    def update(cls, id, data):
        """
        Update an existing shuttle in the database.
        
        Args:
            id (int): ID of the shuttle to update
            data (dict): Dictionary containing the updated shuttle details
            
        Returns:
            tuple: (success, message/error)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Check if the shuttle exists
            cursor.execute(f"SELECT * FROM {cls.table_name} WHERE id = ?", (id,))
            if not cursor.fetchone():
                return (False, f"Shuttle with ID {id} not found")
            
            # Prepare update statement
            update_fields = []
            values = []
            
            # Add each field to the update if it exists in the data
            if 'name' in data:
                update_fields.append("name = ?")
                values.append(data['name'])
            
            if 'capacity' in data:
                update_fields.append("capacity = ?")
                values.append(int(data['capacity']))
            
            if 'shuttle_type' in data:
                if data['shuttle_type'] not in ['naves', 'preprah']:
                    return (False, "Shuttle type must be either 'naves' or 'preprah'")
                update_fields.append("shuttle_type = ?")
                values.append(data['shuttle_type'])
            
            if 'shift_length' in data:
                if int(data['shift_length']) not in [8, 12]:
                    return (False, "Shift length must be either 8 or 12 hours")
                update_fields.append("shift_length = ?")
                values.append(int(data['shift_length']))
            
            if 'break_time' in data:
                update_fields.append("break_time = ?")
                values.append(int(data['break_time']))
            
            if 'break_each' in data:
                update_fields.append("break_each = ?")
                values.append(int(data['break_each']))
            
            if 'time_for_shift_change' in data:
                update_fields.append("time_for_shift_change = ?")
                values.append(int(data['time_for_shift_change']))
            
            if 'shift_change_dest' in data:
                update_fields.append("shift_change_dest = ?")
                values.append(int(data['shift_change_dest']))
                
            if 'preprah_length' in data:
                update_fields.append("preprah_length = ?")
                values.append(int(data['preprah_length']))
                
            if 'preprah_destination' in data:
                update_fields.append("preprah_destination = ?")
                values.append(int(data['preprah_destination']) if data['preprah_destination'] else None)
            
            if 'active' in data:
                update_fields.append("active = ?")
                values.append(1 if data['active'] else 0)

            if 'color' in data:
                update_fields.append("color = ?")
                values.append(data['color'])
            
            if not update_fields:
                return (True, "No changes to update")
            
            # Add ID to values for the WHERE clause
            values.append(id)
            
            # Execute update
            cursor.execute(
                f"UPDATE {cls.table_name} SET {', '.join(update_fields)} WHERE id = ?",
                values
            )
            
            conn.commit()
            conn.close()
            
            return (True, "Shuttle updated successfully")
        except Exception as e:
            return (False, f"Error updating shuttle: {str(e)}")
    
    @classmethod
    def delete(cls, id):
        """
        Delete a shuttle from the database.
        
        Args:
            id (int): ID of the shuttle to delete
            
        Returns:
            tuple: (success, message/error)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Check if the shuttle exists
            cursor.execute(f"SELECT * FROM {cls.table_name} WHERE id = ?", (id,))
            if not cursor.fetchone():
                return (False, f"Shuttle with ID {id} not found")
            
            # Delete the shuttle
            cursor.execute(f"DELETE FROM {cls.table_name} WHERE id = ?", (id,))
            
            conn.commit()
            conn.close()
            
            return (True, "Shuttle deleted successfully")
        except Exception as e:
            return (False, f"Error deleting shuttle: {str(e)}")
            
    @classmethod
    def get_as_dataframe(cls, active_only=False):
        """
        Get all shuttles as a pandas DataFrame.
        
        Args:
            active_only (bool): If True, retrieve only active shuttles
            
        Returns:
            pd.DataFrame: DataFrame containing shuttles
        """
        conn = cls.get_db_connection()
        
        query = f"SELECT * FROM {cls.table_name}"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY id"
        
        df = pd.read_sql(query, conn)
        conn.close()
        return df