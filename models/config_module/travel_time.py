"""
Travel Time model for inter-facility transportation system.
"""
from models.base import Model
import sqlite3
import pandas as pd

class TravelTime(Model):
    """Model for travel times between plants."""
    
    table_name = 'travel_times'
    
    @classmethod
    def create_table(cls, force_reset=False):
        """
        Create the travel_times table if it doesn't exist.
        
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
            source_plant INTEGER NOT NULL,
            dest_plant INTEGER NOT NULL,
            time_minutes INTEGER NOT NULL,
            UNIQUE(source_plant, dest_plant)
        )
        ''')
        
        # Create indexes for faster lookups
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_source_plant ON {cls.table_name}(source_plant)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_dest_plant ON {cls.table_name}(dest_plant)")
        
        conn.commit()
        conn.close()
    
    @classmethod
    def init_db(cls, force_reset=False):
        """
        Initialize the database with the travel_times table and sample data if needed.
        
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
            # Sample data - times in minutes
            sample_data = [
                (1, 2, 15),  # Humpolecká -> Dolina
                (1, 3, 20),  # Humpolecká -> Pávov
                (1, 4, 25),  # Humpolecká -> Jipocar C
                (1, 5, 30),  # Humpolecká -> Jipocar H
                (1, 6, 25),  # Humpolecká -> Logpoint
                (2, 3, 10),  # Dolina -> Pávov
                (2, 4, 15),  # Dolina -> Jipocar C
                (2, 5, 20),  # Dolina -> Jipocar H
                (2, 6, 15),  # Dolina -> Logpoint
                (3, 4, 12),  # Pávov -> Jipocar C
                (3, 5, 18),  # Pávov -> Jipocar H
                (3, 6, 8),   # Pávov -> Logpoint
                (4, 5, 10),  # Jipocar C -> Jipocar H
                (4, 6, 15),  # Jipocar C -> Logpoint
                (5, 6, 22)   # Jipocar H -> Logpoint
            ]
            
            # Create reverse routes with same time
            reverse_data = [(dest, source, time) for source, dest, time in sample_data]
            all_data = sample_data + reverse_data
            
            # Insert data
            for source, dest, time in all_data:
                cursor.execute(
                    f"INSERT OR REPLACE INTO {cls.table_name} (source_plant, dest_plant, time_minutes) VALUES (?, ?, ?)",
                    (source, dest, time)
                )
        
        conn.commit()
        conn.close()
    
    @classmethod
    def get_all(cls):
        """
        Retrieve all travel times from the database.
        
        Returns:
            list: List of dictionaries containing all travel times
        """
        conn = cls.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {cls.table_name} ORDER BY source_plant, dest_plant")
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        result = [dict(row) for row in rows]
        
        conn.close()
        return result
    
    @classmethod
    def get_travel_time(cls, source_plant, dest_plant):
        """
        Get the travel time between two plants.
        
        Args:
            source_plant (int): Source plant identifier
            dest_plant (int): Destination plant identifier
            
        Returns:
            int: Travel time in minutes or None if not found
        """
        conn = cls.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT time_minutes FROM {cls.table_name} WHERE source_plant = ? AND dest_plant = ?",
            (source_plant, dest_plant)
        )
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return row['time_minutes']
        return None
    
    @classmethod
    def set_travel_time(cls, source_plant, dest_plant, time_minutes):
        """
        Set the travel time between two plants.
        
        Args:
            source_plant (int): Source plant identifier
            dest_plant (int): Destination plant identifier
            time_minutes (int): Travel time in minutes
            
        Returns:
            tuple: (success, message)
        """
        try:
            if source_plant == dest_plant:
                return (False, "Source and destination plants must be different")
            
            if time_minutes < 0:
                return (False, "Travel time must be non-negative")
            
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Use INSERT OR REPLACE to handle both insert and update cases
            cursor.execute(
                f"INSERT OR REPLACE INTO {cls.table_name} (source_plant, dest_plant, time_minutes) VALUES (?, ?, ?)",
                (source_plant, dest_plant, time_minutes)
            )
            
            # Also update the reverse direction (symmetric travel time)
            cursor.execute(
                f"INSERT OR REPLACE INTO {cls.table_name} (source_plant, dest_plant, time_minutes) VALUES (?, ?, ?)",
                (dest_plant, source_plant, time_minutes)
            )
            
            conn.commit()
            conn.close()
            
            return (True, "Travel time updated successfully")
        except Exception as e:
            return (False, f"Error setting travel time: {str(e)}")
    
    @classmethod
    def delete_travel_time(cls, source_plant, dest_plant):
        """
        Delete the travel time between two plants.
        
        Args:
            source_plant (int): Source plant identifier
            dest_plant (int): Destination plant identifier
            
        Returns:
            tuple: (success, message)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Delete both directions
            cursor.execute(
                f"DELETE FROM {cls.table_name} WHERE (source_plant = ? AND dest_plant = ?) OR (source_plant = ? AND dest_plant = ?)",
                (source_plant, dest_plant, dest_plant, source_plant)
            )
            
            conn.commit()
            conn.close()
            
            return (True, "Travel time deleted successfully")
        except Exception as e:
            return (False, f"Error deleting travel time: {str(e)}")
    
    @classmethod
    def get_matrix(cls):
        """
        Get the travel time matrix as a DataFrame.
        
        Returns:
            pd.DataFrame: DataFrame with source plants as rows and destination plants as columns
        """
        conn = cls.get_db_connection()
        
        # Get distinct plant identifiers
        plant_query = "SELECT DISTINCT identifier FROM plants ORDER BY identifier"
        plants_df = pd.read_sql(plant_query, conn)
        plant_ids = plants_df['identifier'].tolist()
        
        # Get all travel times
        times_df = pd.read_sql(f"SELECT * FROM {cls.table_name}", conn)
        
        conn.close()
        
        # Create empty matrix
        matrix = pd.DataFrame(index=plant_ids, columns=plant_ids)
        
        # Fill the matrix with travel times
        for _, row in times_df.iterrows():
            source = row['source_plant']
            dest = row['dest_plant']
            time = row['time_minutes']
            matrix.at[source, dest] = time
        
        # Fill diagonal with 0 (travel time to self is 0)
        for plant_id in plant_ids:
            matrix.at[plant_id, plant_id] = 0
            
        return matrix
    
    @classmethod
    def get_as_dataframe(cls):
        """
        Get all travel times as a pandas DataFrame.
        
        Returns:
            pd.DataFrame: DataFrame containing all travel times
        """
        conn = cls.get_db_connection()
        df = pd.read_sql(f"SELECT * FROM {cls.table_name} ORDER BY source_plant, dest_plant", conn)
        conn.close()
        return df