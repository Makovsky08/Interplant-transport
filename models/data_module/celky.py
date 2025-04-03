# models/celky.py
from models.base import Model
import pandas as pd
import sqlite3
from datetime import datetime

class Celky(Model):
    """Model for storing celky (transport segments) data."""
    
    @classmethod
    def create_tables(cls, force_reset=False):
        """Create the necessary tables for celky data."""
        conn = cls.get_db_connection()
        cursor = conn.cursor()
        
        if force_reset:
            cursor.execute("DROP TABLE IF EXISTS celky")
            cursor.execute("DROP TABLE IF EXISTS celky_hourly_stats")
        
        # Main celky table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS celky (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            source_plant INTEGER NOT NULL,
            dest_plant INTEGER NOT NULL,
            transport_type TEXT NOT NULL,
            watra_kod TEXT NOT NULL,
            sap_type TEXT NOT NULL,
            last_analysis_date TEXT NOT NULL,
            months_analyzed INTEGER NOT NULL,
            creation_date TEXT NOT NULL,
            schedule_id INTEGER,
            FOREIGN KEY (schedule_id) REFERENCES schedules (id) ON DELETE CASCADE
        )
        ''')
        
        # Hourly statistics for each celky
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS celky_hourly_stats (
            id INTEGER PRIMARY KEY,
            celky_id INTEGER NOT NULL,
            hour INTEGER NOT NULL,
            median_moves INTEGER NOT NULL,
            percentile_90 INTEGER NOT NULL,
            percentile_95 INTEGER NOT NULL,
            avg_moves REAL NOT NULL,
            std_dev REAL NOT NULL,
            variation_coef REAL NOT NULL,
            max_moves INTEGER NOT NULL,
            min_moves INTEGER NOT NULL,
            days_count INTEGER NOT NULL,
            FOREIGN KEY (celky_id) REFERENCES celky (id) ON DELETE CASCADE
        )
        ''')
        
        conn.commit()
        conn.close()
    
    @classmethod
    def save_analysis_results(cls, df, months_back, schedule_id=None):
        """
        Process analysis results and save as celky records associated with a schedule.
        If celky are already assigned to shuttles, they won't be deleted.
        
        Args:
            df (pd.DataFrame): Analysis results DataFrame
            months_back (int): Number of months analyzed
            schedule_id (int, optional): ID of the schedule to associate celky with
            
        Returns:
            list: IDs of the saved celky records
        """
        if df.empty:
            return []
        
        saved_ids = []
        conn = cls.get_db_connection()
        cursor = conn.cursor()
        
        # Check if we have any celky associated with shuttles
        if schedule_id:
            cursor.execute("""
                SELECT DISTINCT cs.celky_id 
                FROM celky_shuttle cs
                JOIN celky c ON cs.celky_id = c.id
                WHERE cs.schedule_id = ? AND c.schedule_id = ?
            """, (schedule_id, schedule_id))
            
            assigned_celky_ids = [row[0] for row in cursor.fetchall()]
        else:
            assigned_celky_ids = []
        
        # If we have a schedule ID, only delete celky associated with this schedule 
        # that aren't assigned to shuttles
        if schedule_id:
            # For safety, delete with specific WHERE clauses rather than all celky
            if assigned_celky_ids:
                placeholders = ','.join(['?'] * len(assigned_celky_ids))
                cursor.execute(f"""
                    DELETE FROM celky 
                    WHERE schedule_id = ? AND id NOT IN ({placeholders})
                """, [schedule_id] + assigned_celky_ids)
            else:
                cursor.execute("DELETE FROM celky WHERE schedule_id = ?", (schedule_id,))
        else:
            # If no schedule_id provided, only delete celky that aren't associated with any schedule
            # and aren't assigned to shuttles
            cursor.execute("""
                DELETE FROM celky 
                WHERE schedule_id IS NULL AND id NOT IN (
                    SELECT DISTINCT celky_id FROM celky_shuttle
                )
            """)
        
        # Group by source, destination, and watra_kod to create celky
        for (source, dest, watra_kod), group in df.groupby(['MRzdroj', 'MRcil', 'WATRA_kod']):
            # Create a name for the celky
            name = f"{source}-{dest}-{watra_kod[:8]}"
            sap_type = group['SAP'].iloc[0]
            transport_type = watra_kod  # Using full WATRA code as transport type for now
            
            # First check if this celky already exists for this schedule
            if schedule_id:
                cursor.execute(
                    """
                    SELECT id FROM celky 
                    WHERE source_plant = ? AND dest_plant = ? AND watra_kod = ? AND schedule_id = ?
                    """,
                    (int(source), int(dest), watra_kod, schedule_id)
                )
            else:
                cursor.execute(
                    """
                    SELECT id FROM celky 
                    WHERE source_plant = ? AND dest_plant = ? AND watra_kod = ? AND schedule_id IS NULL
                    """,
                    (int(source), int(dest), watra_kod)
                )
                
            existing_celky = cursor.fetchone()
            
            if existing_celky:
                # If it exists and is assigned to a shuttle, keep it and update stats
                celky_id = existing_celky[0]
                
                # Update the celky record with new analysis data
                cursor.execute(
                    """
                    UPDATE celky
                    SET last_analysis_date = ?, months_analyzed = ?
                    WHERE id = ?
                    """,
                    (
                        datetime.now().strftime('%Y-%m-%d'),
                        months_back,
                        celky_id
                    )
                )
                
                # Delete old hourly stats for this celky
                cursor.execute("DELETE FROM celky_hourly_stats WHERE celky_id = ?", (celky_id,))
                
            else:
                # Store the main celky record
                cursor.execute(
                    """
                    INSERT INTO celky 
                    (name, source_plant, dest_plant, transport_type, watra_kod, sap_type, 
                    last_analysis_date, months_analyzed, creation_date, schedule_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name, int(source), int(dest), transport_type, watra_kod, sap_type,
                        datetime.now().strftime('%Y-%m-%d'),
                        months_back,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        schedule_id
                    )
                )
                
                celky_id = cursor.lastrowid
            
            saved_ids.append(celky_id)
            
            # Store hourly statistics
            for hour, hour_group in group.groupby('Hodina'):
                # Get the first row which should have all the stats for this hour
                stat_row = hour_group.iloc[0]
                
                cursor.execute(
                    """
                    INSERT INTO celky_hourly_stats
                    (celky_id, hour, median_moves, percentile_90, percentile_95, 
                    avg_moves, std_dev, variation_coef, max_moves, min_moves, days_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        celky_id, hour, 
                        int(stat_row['Median']), 
                        int(stat_row['Percentil90']),
                        int(stat_row['Percentil95']),
                        float(stat_row['Prumer']),
                        float(stat_row['SmerodatnaOdchylka']),
                        float(stat_row['VariacniKoeficient']),
                        int(stat_row['MaxPocet']),
                        int(stat_row['MinPocet']),
                        int(stat_row['PocetDni'])
                    )
                )
        
        conn.commit()
        conn.close()
        
        return saved_ids
    
    # This represents an addition to the existing Celky class in models/data_module/celky.py
    @classmethod
    def get_all_celky(cls, schedule_id=None):
        """
        Get all celky with their hourly stats and assignment status.
        
        Args:
            schedule_id (int, optional): ID of the schedule to filter by
                
        Returns:
            list: List of dictionaries containing celky data
        """
        conn = cls.get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if schedule_id:
            cursor.execute("SELECT * FROM celky WHERE schedule_id = ? ORDER BY name", (schedule_id,))
        else:
            cursor.execute("SELECT * FROM celky ORDER BY name")
            
        celky_rows = cursor.fetchall()
        
        # Get all celky_shuttle assignments for this schedule
        assigned_celky_ids = set()
        if schedule_id:
            cursor.execute("""
                SELECT DISTINCT celky_id 
                FROM celky_shuttle 
                WHERE schedule_id = ?
            """, (schedule_id,))
            
            assigned_celky_ids = {row[0] for row in cursor.fetchall()}
        
        result = []
        for celky in celky_rows:
            celky_dict = dict(celky)
            
            # Add flag indicating if this celky is assigned to a shuttle
            celky_dict['is_assigned'] = celky_dict['id'] in assigned_celky_ids
            
            # Get hourly stats for this celky
            cursor.execute(
                "SELECT * FROM celky_hourly_stats WHERE celky_id = ? ORDER BY hour",
                (celky['id'],)
            )
            hourly_stats = [dict(row) for row in cursor.fetchall()]
            
            celky_dict['hourly_stats'] = hourly_stats
            result.append(celky_dict)
        
        conn.close()
        return result
        
    @classmethod
    def get_celky_by_id(cls, celky_id):
        """
        Get a specific celky by ID with its hourly stats.
        
        Args:
            celky_id (int): ID of the celky to retrieve
            
        Returns:
            dict: Dictionary containing the celky data or None if not found
        """
        conn = cls.get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM celky WHERE id = ?", (celky_id,))
        celky = cursor.fetchone()
        
        if not celky:
            conn.close()
            return None
        
        celky_dict = dict(celky)
        
        # Get hourly stats for this celky
        cursor.execute(
            "SELECT * FROM celky_hourly_stats WHERE celky_id = ? ORDER BY hour",
            (celky_id,)
        )
        hourly_stats = [dict(row) for row in cursor.fetchall()]
        
        celky_dict['hourly_stats'] = hourly_stats
        
        conn.close()
        return celky_dict
    
    @classmethod
    def init_db(cls, force_reset=False):
        """Initialize the database with celky tables."""
        cls.create_tables(force_reset)