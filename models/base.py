"""
Base model functionality for database operations.
This module provides a common interface for models to interact with the database.
"""

import sqlite3
import os
from config import DATABASE_FILE

class Model:
    """Base model class for database operations."""
    
    @staticmethod
    def get_db_connection():
        """Create and return a database connection with timeout."""
        import os
        from config import DATABASE_FILE
        
        os.makedirs(os.path.dirname(DATABASE_FILE) if os.path.dirname(DATABASE_FILE) else '.', exist_ok=True)
        conn = sqlite3.connect(DATABASE_FILE, timeout=10.0)
        conn.row_factory = sqlite3.Row
        
        # Set pragma for better concurrency
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        
        return conn
    
    @staticmethod
    def init_db(force_reset=False):
        """
        Initialize the database and create tables if they don't exist.
        
        Args:
            force_reset (bool): If True, reset the database by dropping and recreating all tables
        """
        raise NotImplementedError("Subclasses must implement init_db method")
    
    @classmethod
    def create_table(cls, force_reset=False):
        """
        Create the table for this model if it doesn't exist.
        
        Args:
            force_reset (bool): If True, drop and recreate the table
        """
        raise NotImplementedError("Subclasses must implement create_table method")