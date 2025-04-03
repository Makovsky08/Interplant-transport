import sqlite3
from models.base import Model
import json
from datetime import datetime

class ShuttleStatistics(Model):
    # Methods for route statistics
    @classmethod
    def create_table(cls, force_reset=False):
        """
        Create the tables needed for storing shuttle route statistics.
        
        Args:
            force_reset (bool): If True, drop and recreate all tables
        """
        import time
        
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                conn = cls.get_db_connection()
                cursor = conn.cursor()

                if force_reset:
                    try:
                        # Add a timeout for the lock operations
                        conn.execute("PRAGMA busy_timeout = 5000")
                        cursor.execute("DROP TABLE IF EXISTS shuttle_route_statistics")
                        cursor.execute("DROP TABLE IF EXISTS route_details")
                        cursor.execute("DROP TABLE IF EXISTS once_per_shift_details")
                    except Exception as e:
                        print(f"Warning during table drop (attempt {attempt+1}/{max_attempts}): {e}")
                        conn.close()
                        time.sleep(1)
                        continue
                
                # Create route statistics table with new peak scenario fields
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS shuttle_route_statistics (
                    id INTEGER PRIMARY KEY,
                    shuttle_id INTEGER NOT NULL,
                    schedule_id INTEGER NOT NULL,
                    total_time INTEGER NOT NULL,
                    active_time INTEGER NOT NULL,
                    break_time INTEGER NOT NULL,
                    
                    median_frequency_time REAL NOT NULL,
                    median_frequencies INTEGER NOT NULL,
                    median_max_capacity REAL NOT NULL,
                    median_max_interval INTEGER NOT NULL,
                    median_active_time INTEGER NOT NULL,
                    
                    peak_median_frequency_time REAL NOT NULL,
                    peak_median_frequencies INTEGER NOT NULL,
                    peak_median_max_capacity REAL NOT NULL,
                    peak_median_active_time INTEGER NOT NULL,
                    
                    p90_frequency_time REAL NOT NULL,
                    p90_frequencies INTEGER NOT NULL,
                    p90_max_capacity REAL NOT NULL,
                    p90_max_interval INTEGER NOT NULL,
                    p90_active_time INTEGER NOT NULL,
                    
                    peak_p90_frequency_time REAL NOT NULL,
                    peak_p90_frequencies INTEGER NOT NULL,
                    peak_p90_max_capacity REAL NOT NULL,
                    peak_p90_active_time INTEGER NOT NULL,
                    
                    once_per_shift_time INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (shuttle_id) REFERENCES shuttles (id) ON DELETE CASCADE,
                    FOREIGN KEY (schedule_id) REFERENCES schedules (id) ON DELETE CASCADE,
                    UNIQUE(shuttle_id, schedule_id)
                )
                """)
                
                # Create route details table with scenario field
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS route_details (
                    id INTEGER PRIMARY KEY,
                    shuttle_route_statistics_id INTEGER NOT NULL,
                    scenario TEXT NOT NULL,
                    detail_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (shuttle_route_statistics_id) REFERENCES shuttle_route_statistics (id) ON DELETE CASCADE
                )
                """)
                
                # Create once-per-shift details table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS once_per_shift_details (
                    id INTEGER PRIMARY KEY,
                    shuttle_route_statistics_id INTEGER NOT NULL,
                    detail_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (shuttle_route_statistics_id) REFERENCES shuttle_route_statistics (id) ON DELETE CASCADE
                )
                """)
                
                conn.commit()
                conn.close()
                return  # Success, exit the retry loop
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_attempts - 1:
                    print(f"Database locked, retrying... (attempt {attempt+1}/{max_attempts})")
                    time.sleep(1)  # Wait before retrying
                    continue
                else:
                    print(f"Error creating tables: {e}")
                    raise

    @classmethod
    def init_db(cls, force_reset=False):
        """
        Initialize the database with tables for shuttle route statistics.
        
        Args:
            force_reset (bool): If True, reset the database by dropping and recreating tables
        """
        # Create the tables
        cls.create_table(force_reset)
        
        # If force reset is requested, ensure all statistics data is cleared
        if force_reset:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM shuttle_route_statistics")
            cursor.execute("DELETE FROM route_details")
            cursor.execute("DELETE FROM once_per_shift_details")
            
            
            conn.commit()
            conn.close()
            cls.create_table(force_reset)


    @classmethod
    def save_statistics(cls, shuttle_id, schedule_id, statistics):
        """
        Save statistics for a shuttle route.
        
        Args:
            shuttle_id (int): ID of the shuttle
            schedule_id (int): ID of the schedule
            statistics (dict): Dictionary containing the statistics
            
        Returns:
            tuple: (success, message, statistics_id)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Begin transaction
            conn.execute("BEGIN TRANSACTION")
            
            # First delete any existing statistics for this shuttle/schedule combination
            cursor.execute(
                """
                SELECT id FROM shuttle_route_statistics
                WHERE shuttle_id = ? AND schedule_id = ?
                """,
                (shuttle_id, schedule_id)
            )
            
            existing_stats = cursor.fetchone()
            if existing_stats:
                stats_id = existing_stats[0]
                
                # Delete associated details
                cursor.execute(
                    "DELETE FROM route_details WHERE shuttle_route_statistics_id = ?",
                    (stats_id,)
                )
                cursor.execute(
                    "DELETE FROM once_per_shift_details WHERE shuttle_route_statistics_id = ?",
                    (stats_id,)
                )
                
                # Delete the statistics record
                cursor.execute(
                    "DELETE FROM shuttle_route_statistics WHERE id = ?",
                    (stats_id,)
                )
            
            # Insert new statistics
            now = datetime.now().isoformat()
            
            cursor.execute(
                """
                INSERT INTO shuttle_route_statistics
                (shuttle_id, schedule_id, total_time, active_time, break_time, 
                median_frequency_time, median_frequencies, median_max_capacity, median_max_interval, median_active_time,
                peak_median_frequency_time, peak_median_frequencies, peak_median_max_capacity, peak_median_active_time,
                p90_frequency_time, p90_frequencies, p90_max_capacity, p90_max_interval, p90_active_time,
                peak_p90_frequency_time, peak_p90_frequencies, peak_p90_max_capacity, peak_p90_active_time,
                once_per_shift_time, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    shuttle_id,
                    schedule_id,
                    statistics.get('total_time', 0),
                    statistics.get('active_time', 0),
                    statistics.get('break_time', 0),
                    
                    statistics.get('median_frequency_time', 0),
                    statistics.get('median_frequencies', 0),
                    statistics.get('median_max_capacity', 0),
                    statistics.get('median_max_interval', 0),
                    statistics.get('median_active_time', statistics.get('active_time', 0)),  # Default to active_time if median_active_time not specified
                    
                    statistics.get('peak_median_frequency_time', 0),
                    statistics.get('peak_median_frequencies', 0),
                    statistics.get('peak_median_max_capacity', 0),
                    statistics.get('peak_median_active_time', 0),
                    
                    statistics.get('p90_frequency_time', 0),
                    statistics.get('p90_frequencies', 0),
                    statistics.get('p90_max_capacity', 0),
                    statistics.get('p90_max_interval', 0),
                    statistics.get('p90_active_time', 0),
                    
                    statistics.get('peak_p90_frequency_time', 0),
                    statistics.get('peak_p90_frequencies', 0),
                    statistics.get('peak_p90_max_capacity', 0),
                    statistics.get('peak_p90_active_time', 0),
                    
                    statistics.get('once_per_shift_time', 0),
                    now, now
                )
            )
            
            stats_id = cursor.lastrowid
            
            # Save route details for all four scenarios
            # 1. Average Median scenario
            if 'median_route_details' in statistics and statistics['median_route_details']:
                cursor.execute(
                    """
                    INSERT INTO route_details
                    (shuttle_route_statistics_id, scenario, detail_json, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        stats_id,
                        'median',
                        json.dumps(statistics['median_route_details']),
                        now
                    )
                )
            
            # 2. Peak Median scenario
            if 'peak_median_route_details' in statistics and statistics['peak_median_route_details']:
                cursor.execute(
                    """
                    INSERT INTO route_details
                    (shuttle_route_statistics_id, scenario, detail_json, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        stats_id,
                        'peak_median',
                        json.dumps(statistics['peak_median_route_details']),
                        now
                    )
                )
            
            # 3. Average P90 scenario
            if 'p90_route_details' in statistics and statistics['p90_route_details']:
                cursor.execute(
                    """
                    INSERT INTO route_details
                    (shuttle_route_statistics_id, scenario, detail_json, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        stats_id,
                        'p90',
                        json.dumps(statistics['p90_route_details']),
                        now
                    )
                )
            
            # 4. Peak P90 scenario
            if 'peak_p90_route_details' in statistics and statistics['peak_p90_route_details']:
                cursor.execute(
                    """
                    INSERT INTO route_details
                    (shuttle_route_statistics_id, scenario, detail_json, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        stats_id,
                        'peak_p90',
                        json.dumps(statistics['peak_p90_route_details']),
                        now
                    )
                )
            
            # Save once-per-shift details
            if 'once_per_shift_details' in statistics and statistics['once_per_shift_details']:
                cursor.execute(
                    """
                    INSERT INTO once_per_shift_details
                    (shuttle_route_statistics_id, detail_json, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (
                        stats_id,
                        json.dumps(statistics['once_per_shift_details']),
                        now
                    )
                )
            
            conn.commit()
            conn.close()
            
            return (True, "Statistics saved successfully", stats_id)
        except Exception as e:
            # Rollback on error
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return (False, f"Error saving statistics: {str(e)}", None)
    
    @classmethod
    def get_by_shuttle_and_schedule(cls, shuttle_id, schedule_id):
        """
        Get statistics for a specific shuttle and schedule.
        
        Args:
            shuttle_id (int): ID of the shuttle
            schedule_id (int): ID of the schedule
            
        Returns:
            dict: Dictionary containing the statistics or None if not found
        """
        try:
            conn = cls.get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get the statistics record directly using shuttle_id and schedule_id
            cursor.execute(
                """
                SELECT * FROM shuttle_route_statistics
                WHERE shuttle_id = ? AND schedule_id = ?
                """,
                (shuttle_id, schedule_id)
            )
            
            stats_row = cursor.fetchone()
            if not stats_row:
                conn.close()
                return None
            
            stats_dict = dict(stats_row)
            stats_id = stats_dict['id']
            
            # Get route details for all scenarios
            cursor.execute(
                """
                SELECT scenario, detail_json FROM route_details
                WHERE shuttle_route_statistics_id = ?
                """,
                (stats_id,)
            )
            
            scenario_details = cursor.fetchall()
            for row in scenario_details:
                scenario = row['scenario']
                detail_json = row['detail_json']
                
                if scenario == 'median':
                    stats_dict['median_route_details'] = json.loads(detail_json)
                elif scenario == 'peak_median':
                    stats_dict['peak_median_route_details'] = json.loads(detail_json)
                elif scenario == 'p90':
                    stats_dict['p90_route_details'] = json.loads(detail_json)
                elif scenario == 'peak_p90':
                    stats_dict['peak_p90_route_details'] = json.loads(detail_json)
            
            # Get once-per-shift details
            cursor.execute(
                """
                SELECT detail_json FROM once_per_shift_details
                WHERE shuttle_route_statistics_id = ?
                """,
                (stats_id,)
            )
            
            ops_details_row = cursor.fetchone()
            if ops_details_row:
                stats_dict['once_per_shift_details'] = json.loads(ops_details_row[0])
            
            conn.close()
            return stats_dict
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return None
    
    @classmethod
    def delete_for_shuttle_and_schedule(cls, shuttle_id, schedule_id):
        """
        Delete statistics for a specific shuttle and schedule.
        
        Args:
            shuttle_id (int): ID of the shuttle
            schedule_id (int): ID of the schedule
            
        Returns:
            tuple: (success, message)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Get the statistics ID
            cursor.execute(
                """
                SELECT id FROM shuttle_route_statistics
                WHERE shuttle_id = ? AND schedule_id = ?
                """,
                (shuttle_id, schedule_id)
            )
            
            stats_row = cursor.fetchone()
            if not stats_row:
                conn.close()
                return (True, "No statistics found to delete")
            
            stats_id = stats_row[0]
            
            # Delete all related records
            cursor.execute(
                "DELETE FROM route_details WHERE shuttle_route_statistics_id = ?",
                (stats_id,)
            )
            cursor.execute(
                "DELETE FROM once_per_shift_details WHERE shuttle_route_statistics_id = ?",
                (stats_id,)
            )
            cursor.execute(
                "DELETE FROM shuttle_route_statistics WHERE id = ?",
                (stats_id,)
            )
            
            conn.commit()
            conn.close()
            
            return (True, "Statistics deleted successfully")
        except Exception as e:
            return (False, f"Error deleting statistics: {str(e)}")


