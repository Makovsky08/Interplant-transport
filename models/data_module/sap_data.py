# models/sap_data.py
from models.base import Model
import pandas as pd
from datetime import datetime, timedelta

class SAPData(Model):
    """Model for SAP data stored in SQLite."""
    
    table_name = 'sap_data'
    
    @classmethod
    def get_data(cls, months_back=6):
        """
        Retrieve SAP data for the specified number of months back.
        
        Args:
            months_back (int): Number of months to look back
            
        Returns:
            pd.DataFrame: DataFrame with SAP data
        """
        threshold_date = (datetime.now() - timedelta(days=30 * months_back)).strftime('%Y%m%d')
        
        conn = cls.get_db_connection()
        
        query = f"""
        SELECT * FROM {cls.table_name}
        WHERE bdatu >= ?
        """
        
        df = pd.read_sql_query(query, conn, params=(threshold_date,))
        
        conn.close()
        
        return df