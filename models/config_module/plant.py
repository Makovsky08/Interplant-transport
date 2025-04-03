"""
Plant model for inter-facility transportation system.
"""
from models.base import Model
import sqlite3
import pandas as pd

class Plant(Model):
    """Model for plants/facilities."""
    
    table_name = 'plants'
    
    @classmethod
    def create_table(cls, force_reset=False):
        """
        Create the plants table if it doesn't exist.
        
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
            identifier INTEGER NOT NULL UNIQUE,
            ramp_capacity INTEGER NOT NULL DEFAULT 0,
            worker_capacity INTEGER NOT NULL DEFAULT 0
        )
        ''')
        
        conn.commit()
        conn.close()
    
    @classmethod
    def init_db(cls, force_reset=False):
        """
        Initialize the database with the plants table and sample data if needed.
        
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
                (1, 'Humpolecká', 1, 2, 1),
                (2, 'Dolina', 2, 2, 1),
                (3, 'Pávov', 3, 3, 1),
                (4, 'Jipocar C', 4, 10, 5),
                (5, 'Jipocar H', 5, 5, 1),
                (6, 'Logpoint', 6, 4, 1)
            ]
            
            cursor.executemany(
                f"INSERT INTO {cls.table_name} (id, name, identifier, ramp_capacity, worker_capacity) VALUES (?, ?, ?, ?, ?)",
                sample_data
            )
        
        conn.commit()
        conn.close()
    
    @classmethod
    def get_all(cls):
        """
        Retrieve all plants from the database.
        
        Returns:
            list: List of dictionaries containing all plants
        """
        conn = cls.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {cls.table_name} ORDER BY identifier")
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        result = [dict(row) for row in rows]
        
        conn.close()
        return result
    
    @classmethod
    def get_by_id(cls, id):
        """
        Retrieve a specific plant by ID.
        
        Args:
            id (int): ID of the plant to retrieve
            
        Returns:
            dict: Dictionary containing the plant details or None if not found
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
    def get_by_identifier(cls, identifier):
        """
        Retrieve a specific plant by identifier.
        
        Args:
            identifier (int): Identifier of the plant to retrieve
            
        Returns:
            dict: Dictionary containing the plant details or None if not found
        """
        conn = cls.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {cls.table_name} WHERE identifier = ?", (identifier,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    @classmethod
    def add(cls, data):
        """
        Add a new plant to the database.
        
        Args:
            data (dict): Dictionary containing the plant details
            
        Returns:
            tuple: (success, message/error, id)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Validate required fields
            if 'name' not in data or not data['name'] or 'identifier' not in data:
                return (False, "Missing required fields", None)
            
            # Check if identifier already exists
            cursor.execute(f"SELECT id FROM {cls.table_name} WHERE identifier = ?", (data['identifier'],))
            if cursor.fetchone():
                return (False, f"Plant with identifier {data['identifier']} already exists", None)
            
            # Insert data
            cursor.execute(
                f"""
                INSERT INTO {cls.table_name} 
                (name, identifier, ramp_capacity, worker_capacity) 
                VALUES (?, ?, ?, ?)
                """,
                (
                    data['name'],
                    data['identifier'],
                    data.get('ramp_capacity', 0),
                    data.get('worker_capacity', 0)
                )
            )
            
            plant_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return (True, "Plant added successfully", plant_id)
        except Exception as e:
            return (False, f"Error adding plant: {str(e)}", None)
    
    @classmethod
    def update(cls, id, data):
        """
        Update an existing plant in the database.
        
        Args:
            id (int): ID of the plant to update
            data (dict): Dictionary containing the updated plant details
            
        Returns:
            tuple: (success, message/error)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Check if the plant exists
            cursor.execute(f"SELECT * FROM {cls.table_name} WHERE id = ?", (id,))
            if not cursor.fetchone():
                return (False, f"Plant with ID {id} not found")
            
            # Check if identifier is being changed and if it already exists
            if 'identifier' in data:
                cursor.execute(
                    f"SELECT id FROM {cls.table_name} WHERE identifier = ? AND id != ?", 
                    (data['identifier'], id)
                )
                if cursor.fetchone():
                    return (False, f"Plant with identifier {data['identifier']} already exists")
            
            # Update fields
            update_fields = []
            values = []
            
            if 'name' in data and data['name']:
                update_fields.append("name = ?")
                values.append(data['name'])
            
            if 'identifier' in data:
                update_fields.append("identifier = ?")
                values.append(data['identifier'])
            
            if 'ramp_capacity' in data:
                update_fields.append("ramp_capacity = ?")
                values.append(data['ramp_capacity'])
            
            if 'worker_capacity' in data:
                update_fields.append("worker_capacity = ?")
                values.append(data['worker_capacity'])
            
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
            
            return (True, "Plant updated successfully")
        except Exception as e:
            return (False, f"Error updating plant: {str(e)}")
    
    @classmethod
    def delete(cls, id):
        """
        Delete a plant from the database.
        
        Args:
            id (int): ID of the plant to delete
            
        Returns:
            tuple: (success, message/error)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Check if the plant exists
            cursor.execute(f"SELECT * FROM {cls.table_name} WHERE id = ?", (id,))
            if not cursor.fetchone():
                return (False, f"Plant with ID {id} not found")
            
            # Delete the plant
            cursor.execute(f"DELETE FROM {cls.table_name} WHERE id = ?", (id,))
            
            conn.commit()
            conn.close()
            
            return (True, "Plant deleted successfully")
        except Exception as e:
            return (False, f"Error deleting plant: {str(e)}")
    
    @classmethod
    def get_as_dataframe(cls):
        """
        Get all plants as a pandas DataFrame.
        
        Returns:
            pd.DataFrame: DataFrame containing all plants
        """
        conn = cls.get_db_connection()
        df = pd.read_sql(f"SELECT * FROM {cls.table_name} ORDER BY identifier", conn)
        conn.close()
        return df