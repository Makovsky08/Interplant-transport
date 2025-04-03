"""
Data module for analysis of transport statistics from WATRA system.
"""

import pandas as pd
import numpy as np
import pyodbc
import re
from models.data_module.sap_strategy import SAPDataProcessor
from models.data_module.watra_kod import WatraKod
from sqlalchemy import create_engine, text
from config import DATABASE_FILE
import sqlite3

def get_watra_data(zasilka_typ, like_pattern, months_back):
    """
    Gets data from local SQLite copy of WATRA system for a specific shipment type.
    
    Args:
        zasilka_typ (str): Shipment type
        like_pattern (str): SQL LIKE pattern for identifying shipments
        months_back (int): Number of months back for analysis
        
    Returns:
        pd.DataFrame: DataFrame with WATRA data
    """
    try:
        # Create a connection to the SQLite database
        conn = sqlite3.connect(DATABASE_FILE)
        
        # Calculate the date threshold (months_back months ago from now)
        import datetime
        threshold_date = (datetime.datetime.now() - datetime.timedelta(days=30 * months_back)).strftime('%Y-%m-%d')
        
        # Build SQL query to get data from SQLite
        query = """
        SELECT
            zasilkaID,
            MRzdroj,
            MRcil,
            MRtime
        FROM watra_zasilky
        WHERE
            zasilkaID GLOB ?
            AND MRtime >= ?
        ORDER BY MRtime DESC
        """
        
        # Read the data into a pandas DataFrame
        watra_data = pd.read_sql_query(query, conn, params=(like_pattern, threshold_date))

        watra_data['MRtime'] = pd.to_datetime(watra_data['MRtime'], errors='coerce')
        
        conn.close()
        
        return watra_data
        
    except Exception as e:
        print(f"Error fetching WATRA data from SQLite: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

def aggregate_data(data, min_pohyby, zasilka_typ):
    """
    Aggregates data and calculates statistics similar to the SQL query.
    
    Args:
        data (pd.DataFrame): DataFrame with data
        min_pohyby (int): Minimum number of movements for relevant combinations
        
    Returns:
        pd.DataFrame: DataFrame with aggregated statistics
    """
    # Check if we have data
    if data.empty:
        return pd.DataFrame()
    
    # Create columns for analysis
    data['Datum'] = data['MRtime'].dt.date
    data['Hodina'] = data['MRtime'].dt.hour
    
    # Analyze daily movements
    denni_pohyby = data.groupby(['MRzdroj', 'MRcil', 'Datum', 'Hodina']).size().reset_index(name='PocetPohybu')
    
    # Filter relevant combinations
    relevantni_kombinace = denni_pohyby.groupby(['MRzdroj', 'MRcil']).size().reset_index(name='CelkovyPocet')
    relevantni_kombinace = relevantni_kombinace[relevantni_kombinace['CelkovyPocet'] > min_pohyby]
    
    if relevantni_kombinace.empty:
        return pd.DataFrame()
    
    # Join with relevant combinations
    denni_pohyby = pd.merge(
        denni_pohyby,
        relevantni_kombinace[['MRzdroj', 'MRcil']],
        on=['MRzdroj', 'MRcil'],
        how='inner'
    )
    
    # Calculate statistics for each source-destination-hour combination
    statistiky = denni_pohyby.groupby(['MRzdroj', 'MRcil', 'Hodina']).agg({
        'PocetPohybu': ['count', 'min', 'max', 'mean', np.std]
    }).reset_index()
    
    # Rename columns
    statistiky.columns = ['MRzdroj', 'MRcil', 'Hodina', 'PocetDni', 'MinPocet', 'MaxPocet', 'Prumer', 'SmerodatnaOdchylka']
    
    # Calculate percentiles
    percentily = []
    for (zdroj, cil, hodina), group in denni_pohyby.groupby(['MRzdroj', 'MRcil', 'Hodina']):
        median = np.percentile(group['PocetPohybu'], 50)
        percentil90 = np.percentile(group['PocetPohybu'], 90)
        percentil95 = np.percentile(group['PocetPohybu'], 95)
        percentily.append({
            'MRzdroj': zdroj,
            'MRcil': cil,
            'Hodina': hodina,
            'Median': median,
            'Percentil90': percentil90,
            'Percentil95': percentil95,
            'celek': f"{zdroj}{cil}-{zasilka_typ}"
        })
    
    percentily_df = pd.DataFrame(percentily)
    
    # Join statistics and percentiles
    result = pd.merge(
        statistiky,
        percentily_df,
        on=['MRzdroj', 'MRcil', 'Hodina'],
        how='inner'
    )
    
    # Fill NA values with 0 before converting to int
    numeric_cols = ['Median', 'Percentil90', 'Percentil95', 'MinPocet', 'MaxPocet', 'Prumer', 'SmerodatnaOdchylka']
    result[numeric_cols] = result[numeric_cols].fillna(0)
    
    # Format results - convert to int
    for col in numeric_cols:
        result[col] = result[col].astype(int)
    
    # Calculate variation coefficient
    result['VariacniKoeficient'] = (result['SmerodatnaOdchylka'] / 
                                   (result['Prumer'] + (result['Prumer'] == 0) * 0.0001) * 100).astype(int)
    
    return result

def analyze_transport_statistics(months_back=6):
    """
    Analyzes transport statistics between facilities.
    
    Args:
        months_back (int): Number of months back for analysis
        
    Returns:
        pandas.DataFrame: DataFrame with analysis results
    """
    # Load configuration from database
    config_df = WatraKod.get_config_data()

    print(f"ziskal sem data na config")
    
    # Check if we have data
    if config_df.empty:
        print("Warning: Empty configuration")
        return pd.DataFrame()
    
    # Initialize SAP processor
    from config import DATABASE_FILE
    sqlite_connection_string = f"sqlite:///{DATABASE_FILE}"
    sap_processor = SAPDataProcessor(sqlite_connection_string, months_back)
    
    # Empty list for storing results
    results = []
    
    # For each configuration row
    for _, row in config_df.iterrows():
        zasilka_typ = row['zasilka']
        like_pravidlo = row['sql_like_pattern']
        min_pohyby = row['pohyby_zdroj_cil_nad']
        sap_typ = row['SAP']
        
        try:
            # Get WATRA data
            watra_data = get_watra_data(zasilka_typ, like_pravidlo, months_back)
            
            if watra_data.empty:
                print(f"No WATRA data for {zasilka_typ}")
                continue
            
            # Process data according to SAP/non-SAP type
            if sap_typ == 'SAP':
                # For SAP use strategy
                pohday_pravidlo = row.get('POHday_pravidla_sloupce', '')
                pri_vice_vysledcich = row.get('pri_vice_vysledcich', 'první')
                
                # Process data using appropriate strategy
                processed_data = sap_processor.process_watra_data(
                    watra_data, 
                    strategy_name=pohday_pravidlo, 
                    pri_vice_vysledcich=pri_vice_vysledcich
                )
            elif sap_typ == 'neSAP':
                # For non-SAP use WATRA data directly
                processed_data = watra_data
            
            # Aggregate data and calculate statistics
            aggregated_data = aggregate_data(processed_data, min_pohyby, zasilka_typ[:8])
            
            if aggregated_data.empty:
                print(f"No relevant combinations for {zasilka_typ}")
                continue
            
            # Add information about code type
            aggregated_data['SAP'] = row['SAP']
            aggregated_data['WATRA_kod'] = zasilka_typ
            
            # Add results to list
            results.append(aggregated_data)
            
        except Exception as e:
            print(f"Error processing shipment {zasilka_typ}: {e}")
            import traceback
            traceback.print_exc()
    
    # Combine all results
    if results:
        return pd.concat(results, ignore_index=True)
    else:
        return pd.DataFrame()

# Main function for running analysis
def run_analysis(months_back=6):
    """
    Runs transport analysis.
    
    Args:
        months_back (int): Number of months back for analysis
        
    Returns:
        pandas.DataFrame: DataFrame with analysis results
    """
    # Analyze transports
    results = analyze_transport_statistics(months_back)
    
    return results
