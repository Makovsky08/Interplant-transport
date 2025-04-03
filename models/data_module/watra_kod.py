"""
WatraKod model for handling WATRA codes in the database.
"""
import pandas as pd
from models.base import Model

class WatraKod(Model):
    """Model for WATRA codes."""
    
    table_name = 'watra_kody'
    fields = [
        'id', 'zasilka', 'pouziti_WATRA', 'example', 'code_description', 
        'regex_pravidlo', 'sql_like_pattern', 'material_WMRFC', 'Kusy_WMRFC', 'Vaha_dodaci_list', 
        'SAP', 'POHday_pravidla_sloupce', 'pri_vice_vysledcich', 
        'pouziti_jizdni_rad', 'pohyby_zdroj_cil_nad'
    ]
    required_fields = ['zasilka', 'regex_pravidlo']
    
    def __init__(self, **kwargs):
        """Initialize a WatraKod instance with the provided attributes."""
        for field in self.fields:
            setattr(self, field, kwargs.get(field, None))
    
    @classmethod
    def create_table(cls, force_reset=False):
        """
        Create the watra_kody table if it doesn't exist.
        
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
            zasilka TEXT NOT NULL,
            pouziti_WATRA TEXT,
            example TEXT,
            code_description TEXT,
            regex_pravidlo TEXT NOT NULL,
            sql_like_pattern TEXT NOT NULL,
            material_WMRFC TEXT,
            Kusy_WMRFC TEXT,
            Vaha_dodaci_list REAL,
            SAP TEXT,
            POHday_pravidla_sloupce TEXT,
            pri_vice_vysledcich TEXT,
            pouziti_jizdni_rad TEXT,
            pohyby_zdroj_cil_nad INTEGER
        )
        ''')
        
        conn.commit()
        conn.close()
    
    @classmethod
    def init_db(cls, force_reset=False):
        """
        Initialize the database with the watra_kody table and sample data if needed.
        
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
                (1, 'Obaly', 'ano', 'L12345678901', 'Obaly pro výrobu', '^[LG]\\d{11}$', '', 'ne', 'ano', 0.5, 'neSAP', 'ano', 'první', 'ano', 500),
                (2, 'selektivní praní', 'ano', 'S60012345678901234', 'Selektivní praní', '', '^S600\\d{14}$', 'ne', 'ano', 0.3, 'neSAP', 'ano', 'první', 'ano', 100),
                (3, 'Balíky SAP', 'ano', '9000123456789', 'SAP zásilky', '^9\\d{13}$', '', 'ano', 'ano', 1.0, 'SAP', 'ano', 'první', 'ano', 200),
                (4, 'MEWA', 'ano', 'M12345678901', 'MEWA utěrky', '^M\\d{11}$', '', 'ne', 'ne', 0.7, 'neSAP', 'ano', 'první', 'ne', 150)
            ]
            
            placeholders = ', '.join(['?'] * len(cls.fields))
            cursor.executemany(
                f"INSERT INTO {cls.table_name} VALUES ({placeholders})",
                sample_data
            )
        
        conn.commit()
        conn.close()
    
    @classmethod
    def get_all(cls):
        """
        Retrieve all WATRA codes from the database.
        
        Returns:
            list: List of dictionaries containing all WATRA codes
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
    def get_by_id(cls, id):
        """
        Retrieve a specific WATRA code by ID.
        
        Args:
            id (int): ID of the WATRA code to retrieve
            
        Returns:
            dict: Dictionary containing the WATRA code details or None if not found
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
        Add a new WATRA code to the database.
        
        Args:
            data (dict): Dictionary containing the WATRA code details
            
        Returns:
            tuple: (success, message/error, id)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Validate required fields
            if not all(field in data for field in cls.required_fields):
                return (False, "Chybí povinná pole", None)
            
            # Get next available ID
            cursor.execute(f"SELECT MAX(id) FROM {cls.table_name}")
            max_id = cursor.fetchone()[0]
            new_id = 1 if max_id is None else max_id + 1
            
            # Prepare values, using defaults for missing fields
            values = [new_id]
            for field in cls.fields[1:]:  # Skip id which we already handled
                if field == 'pohyby_zdroj_cil_nad' and field in data:
                    try:
                        values.append(int(data[field]))
                    except (ValueError, TypeError):
                        values.append(0)
                elif field == 'Vaha_dodaci_list' and field in data:
                    try:
                        values.append(float(data[field]))
                    except (ValueError, TypeError):
                        values.append(0.0)
                else:
                    values.append(data.get(field, ''))
            
            # Insert the data
            placeholders = ', '.join(['?'] * len(cls.fields))
            cursor.execute(
                f"INSERT INTO {cls.table_name} ({', '.join(cls.fields)}) VALUES ({placeholders})",
                values
            )
            
            conn.commit()
            conn.close()
            
            return (True, "Kód byl úspěšně přidán", new_id)
        except Exception as e:
            return (False, f"Chyba při přidávání kódu: {str(e)}", None)
    
    @classmethod
    def update(cls, id, data):
        """
        Update an existing WATRA code in the database.
        
        Args:
            id (int): ID of the WATRA code to update
            data (dict): Dictionary containing the updated WATRA code details
            
        Returns:
            tuple: (success, message/error)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Validate required fields if they are being updated
            for field in cls.required_fields:
                if field in data and not data[field]:
                    return (False, f"Pole '{field}' je povinné")
            
            # Check if the WATRA code exists
            cursor.execute(f"SELECT * FROM {cls.table_name} WHERE id = ?", (id,))
            if not cursor.fetchone():
                return (False, f"Kód s ID {id} nebyl nalezen")
            
            # Prepare fields and values for the update
            fields = [f for f in cls.fields if f != 'id' and f in data]
            values = []
            
            set_clauses = []
            for field in fields:
                set_clauses.append(f"{field} = ?")
                
                # Special handling for numeric fields
                if field == 'pohyby_zdroj_cil_nad':
                    try:
                        values.append(int(data[field]))
                    except (ValueError, TypeError):
                        values.append(0)
                elif field == 'Vaha_dodaci_list':
                    try:
                        values.append(float(data[field]))
                    except (ValueError, TypeError):
                        values.append(0.0)
                else:
                    values.append(data[field])
            
            # Add the ID to the values
            values.append(id)
            
            # Update the data
            cursor.execute(
                f"UPDATE {cls.table_name} SET {', '.join(set_clauses)} WHERE id = ?",
                values
            )
            
            conn.commit()
            conn.close()
            
            return (True, "Kód byl úspěšně aktualizován")
        except Exception as e:
            return (False, f"Chyba při aktualizaci kódu: {str(e)}")
    
    @classmethod
    def delete(cls, id):
        """
        Delete a WATRA code from the database.
        
        Args:
            id (int): ID of the WATRA code to delete
            
        Returns:
            tuple: (success, message/error)
        """
        try:
            conn = cls.get_db_connection()
            cursor = conn.cursor()
            
            # Check if the WATRA code exists
            cursor.execute(f"SELECT * FROM {cls.table_name} WHERE id = ?", (id,))
            if not cursor.fetchone():
                return (False, f"Kód s ID {id} nebyl nalezen")
            
            # Delete the data
            cursor.execute(f"DELETE FROM {cls.table_name} WHERE id = ?", (id,))
            
            conn.commit()
            conn.close()
            
            return (True, "Kód byl úspěšně smazán")
        except Exception as e:
            return (False, f"Chyba při mazání kódu: {str(e)}")
    
    @classmethod
    def import_excel(cls, excel_path):
        """
        Import data from Excel file to the database.
        
        Args:
            excel_path (str): Path to the Excel file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Read Excel file
            df = pd.read_excel(excel_path, sheet_name='WATRA_kody')


            
            # Connect to SQLite
            conn = cls.get_db_connection()

            cursor = conn.cursor()

            cursor.execute(f"DROP TABLE IF EXISTS {cls.table_name}")
        
            cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {cls.table_name} (
                id INTEGER PRIMARY KEY,
                zasilka TEXT NOT NULL,
                pouziti_WATRA TEXT,
                example TEXT,
                code_description TEXT,
                regex_pravidlo TEXT NOT NULL,
                sql_like_pattern TEXT NOT NULL,
                material_WMRFC TEXT,
                Kusy_WMRFC TEXT,
                Vaha_dodaci_list REAL,
                SAP TEXT,
                POHday_pravidla_sloupce TEXT,
                pri_vice_vysledcich TEXT,
                pouziti_jizdni_rad TEXT,
                pohyby_zdroj_cil_nad INTEGER
            )
            ''')
            

            cursor.execute(f"DELETE FROM {cls.table_name}")
            conn.commit()
            
            # Insert data from DataFrame
            df.to_sql(cls.table_name, conn, if_exists='append', index=False)
            
            conn.close()
            return True
        except Exception as e:
            print(f"Error importing Excel file: {e}")
            return False
    
    @classmethod
    def get_config_data(cls):
        """
        Retrieve configuration data from the database.
        
        Returns:
            pandas.DataFrame: DataFrame with configuration data
        """
        conn = cls.get_db_connection()
        
        config_df = pd.read_sql_query(
            f"SELECT * FROM {cls.table_name} WHERE pouziti_jizdni_rad = 'ano'", 
            conn
        )
        
        conn.close()
        return config_df
    
    @classmethod
    def get_filtered_config_data(cls):
        """
        Retrieve only neSAP configuration data with pouziti_jizdni_rad='ano'.
        
        Returns:
            pandas.DataFrame: DataFrame with filtered configuration data
        """
        conn = cls.get_db_connection()
        
        # Fetch filtered data
        query = f"SELECT * FROM {cls.table_name} WHERE SAP = 'neSAP' AND pouziti_jizdni_rad = 'ano'"
        df = pd.read_sql_query(query, conn)
        
        conn.close()
        return df