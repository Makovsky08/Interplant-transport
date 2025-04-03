"""
Database interface module that provides a simplified API 
for interacting with the database models.
"""

import os
from models.data_module.watra_kod import WatraKod
from models.data_module.celky import Celky

def init_db(force_reset=False):
    """
    Initialize the database and create all required tables.
    
    Args:
        force_reset (bool): If True, reset the database to default values
    """
    # Initialize WatraKod table
    WatraKod.init_db(force_reset)
    # Add other model initializations as needed

def import_excel_to_db(excel_path):
    """
    Import data from Excel file to the database.
    
    Args:
        excel_path (str): Path to the Excel file
        
    Returns:
        bool: True if successful, False otherwise
    """
    return WatraKod.import_excel(excel_path)

def get_config_data():
    """
    Retrieve configuration data from the database.
    
    Returns:
        pandas.DataFrame: DataFrame with configuration data
    """
    return WatraKod.get_config_data()

def get_all_watra_kody():
    """
    Retrieve all WATRA codes from the database.
    
    Returns:
        list: List of dictionaries containing all WATRA codes
    """
    return WatraKod.get_all()

def get_watra_kod(id):
    """
    Retrieve a specific WATRA code by ID.
    
    Args:
        id (int): ID of the WATRA code to retrieve
        
    Returns:
        dict: Dictionary containing the WATRA code details or None if not found
    """
    return WatraKod.get_by_id(id)

def add_watra_kod(data):
    """
    Add a new WATRA code to the database.
    
    Args:
        data (dict): Dictionary containing the WATRA code details
        
    Returns:
        tuple: (success, message/error, id)
    """
    return WatraKod.add(data)

def update_watra_kod(id, data):
    """
    Update an existing WATRA code in the database.
    
    Args:
        id (int): ID of the WATRA code to update
        data (dict): Dictionary containing the updated WATRA code details
        
    Returns:
        tuple: (success, message/error)
    """
    return WatraKod.update(id, data)

def delete_watra_kod(id):
    """
    Delete a WATRA code from the database.
    
    Args:
        id (int): ID of the WATRA code to delete
        
    Returns:
        tuple: (success, message/error)
    """
    return WatraKod.delete(id)

def get_filtered_config_data():
    """
    Retrieve only neSAP configuration data with pouziti_jizdni_rad='ano'.
    
    Returns:
        pandas.DataFrame: DataFrame with filtered configuration data
    """
    return WatraKod.get_filtered_config_data()