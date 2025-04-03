"""
SAP Strategy Module for processing SAP data with different strategies.
This module provides a strategy pattern implementation for handling
different SAP data processing approaches based on POHday_pravidla_sloupce column.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
from abc import ABC, abstractmethod
from sqlalchemy import create_engine, text
import os
import time
from models.data_module.sap_data import SAPData
from config import WATRA_DB_CONNECTION_STRING



class SAPStrategy(ABC):
    """Base abstract class for SAP data processing strategies."""
    
    @abstractmethod
    def process_data(self, watra_df, sap_df, pri_vice_vysledcich, months_back=6):
        """
        Process SAP data according to the specific strategy.
        
        Args:
            watra_df (pd.DataFrame): DataFrame with WATRA data
            sap_df (pd.DataFrame): DataFrame with SAP data from Oracle
            pri_vice_vysledcich (str): Strategy to handle multiple results
            
        Returns:
            pd.DataFrame: Processed and filtered data
        """
        pass


class TANUMTPOSNormalizedStrategy(SAPStrategy):
    """Strategy for TANUM+TAPOS (normalized) format."""
    
    def process_data(self, watra_df, sap_df, pri_vice_vysledcich, months_back=6):
        """Process data for TANUM+TAPOS (normalized) format."""
        # Extract TANUM (first 9 digits) and TAPOS (next 4 digits) from zasilkaID
        watra_df['extracted_tanum'] = watra_df['zasilkaID'].str[0:10]
        watra_df['extracted_tapos'] = watra_df['zasilkaID'].str[10:14]
        
        # Merge with SAP data on TANUM and TAPOS
        merged_df = pd.merge(
            watra_df,
            sap_df,
            left_on=['extracted_tanum', 'extracted_tapos'],
            right_on=['tanum', 'tapos'],
            how='left'
        )
        
        # Apply filtering based on pri_vice_vysledcich
        if pri_vice_vysledcich == 'první':
            # Take the first match for each zasilkaID
            merged_df = merged_df.sort_values('zasilkaID').groupby('zasilkaID').first().reset_index()
        elif pri_vice_vysledcich == 'poslední':
            # Take the last match for each zasilkaID
            merged_df = merged_df.sort_values('zasilkaID').groupby('zasilkaID').last().reset_index()
        
        return merged_df


class TANUMTPOSSlashStrategy(SAPStrategy):
    """Strategy for TANUM/TAPOS format with slash."""
    
    def process_data(self, watra_df, sap_df, pri_vice_vysledcich, months_back=6):
        """Process data for TANUM/TAPOS format with slash."""
        # Extract TANUM and TAPOS from zasilkaID with slash format
        watra_df['extracted_tanum'] = watra_df['zasilkaID'].str.split('/').str[0].str[1:]
        watra_df['extracted_tapos'] = watra_df['zasilkaID'].str.split('/').str[1]
        
        # Merge with SAP data on TANUM and TAPOS
        merged_df = pd.merge(
            watra_df,
            sap_df,
            left_on=['extracted_tanum', 'extracted_tapos'],
            right_on=['tanum', 'tapos'],
            how='left'
        )
        
        # Apply filtering based on pri_vice_vysledcich
        if pri_vice_vysledcich == 'první':
            # Take the first match for each zasilkaID
            merged_df = merged_df.sort_values('zasilkaID').groupby('zasilkaID').first().reset_index()
        elif pri_vice_vysledcich == 'poslední':
            # Take the last match for each zasilkaID
            merged_df = merged_df.sort_values('zasilkaID').groupby('zasilkaID').last().reset_index()
        
        return merged_df


class LEStrategy(SAPStrategy):
    """Strategy for LE format."""
    
    def process_data(self, watra_df, sap_df, pri_vice_vysledcich, months_back=6):
        """Process data for LE format."""
        # Pad VLENR and NLENR with leading zeros to match zasilkaID format
        watra_df['zasilkaID'] = watra_df['zasilkaID'].astype(str).apply(lambda x: x.zfill(20))
        
        # Merge with both VLENR and NLENR columns
        merged_vlenr = pd.merge(
            watra_df,
            sap_df,
            left_on='zasilkaID',
            right_on='vlenr',
            how='inner'
        )
        
        merged_nlenr = pd.merge(
            watra_df,
            sap_df,
            left_on='zasilkaID',
            right_on='nlenr',
            how='inner'
        )
        
        # Combine results
        merged_df = pd.concat([merged_vlenr, merged_nlenr], ignore_index=True)
        
        # Handle multiple results
        if pri_vice_vysledcich == 'první':
            # Take the first match for each zasilkaID
            merged_df = merged_df.sort_values('zasilkaID').groupby('zasilkaID').first().reset_index()
        elif pri_vice_vysledcich == 'poslední':
            # Take the last match for each zasilkaID
            merged_df = merged_df.sort_values('zasilkaID').groupby('zasilkaID').last().reset_index()
        elif pri_vice_vysledcich == 'po_MRTIME_nejblizsi':
            # Find records with nearest date/time to WATRA MRtime
            
            # Convert BDATU and BZEIT to datetime
            def convert_to_datetime(row):
                try:
                    if pd.notna(row['bdatu']) and pd.notna(row['bzeit']):
                        bdatu = str(row['bdatu'])
                        bzeit = str(row['bzeit'])
                        
                        # Format: YYYYMMDD and HHMMSS
                        year = int(bdatu[:4])
                        month = int(bdatu[4:6])
                        day = int(bdatu[6:8])
                        
                        hour = int(bzeit[:2])
                        minute = int(bzeit[2:4])
                        second = int(bzeit[4:6]) if len(bzeit) >= 6 else 0
                        
                        return datetime(year, month, day, hour, minute, second)
                except:
                    return None
                return None
            
            merged_df['sap_datetime'] = merged_df.apply(convert_to_datetime, axis=1)
            
            # Calculate time difference
            merged_df['time_diff'] = merged_df.apply(
                lambda row: abs((row['MRtime'] - row['sap_datetime']).total_seconds()) 
                if pd.notna(row['sap_datetime']) else float('inf'), 
                axis=1
            )
            
            # Get the record with minimal time difference for each zasilkaID
            merged_df = merged_df.sort_values('time_diff').groupby('zasilkaID').first().reset_index()
        
        return merged_df


class MATNRStrategy(SAPStrategy):
    """Strategy for extracting MATNR from SAP data."""
    
    def process_data(self, watra_df, sap_df, pri_vice_vysledcich, months_back=6):
        """Process data to extract MATNR from SAP data."""
        # This strategy could work with various zasilkaID formats
        # We'll implement a flexible approach to match zasilkaID with SAP data
        
        # Check TANUM+TAPOS format
        if watra_df['zasilkaID'].str.match(r'^9\d{13}$').any():
            # Extract TANUM and TAPOS
            watra_df['extracted_tanum'] = watra_df['zasilkaID'].str[0:10]
            watra_df['extracted_tapos'] = watra_df['zasilkaID'].str[10:14]
            
            # Merge with SAP data
            merged_df = pd.merge(
                watra_df,
                sap_df,
                left_on=['extracted_tanum', 'extracted_tapos'],
                right_on=['tanum', 'tapos'],
                how='left'
            )
        
        # Check TANUM/TAPOS format
        elif watra_df['zasilkaID'].str.match(r'^9\d{9}/\d{4}$').any():
            # Extract TANUM and TAPOS
            watra_df['extracted_tanum'] = watra_df['zasilkaID'].str.split('/').str[0].str[1:]
            watra_df['extracted_tapos'] = watra_df['zasilkaID'].str.split('/').str[1]
            
            # Merge with SAP data
            merged_df = pd.merge(
                watra_df,
                sap_df,
                left_on=['extracted_tanum', 'extracted_tapos'],
                right_on=['tanum', 'tapos'],
                how='left'
            )
        
        # Check LE format
        elif watra_df['zasilkaID'].str.match(r'^\d{10,20}$').any():
            # Implement LE matching logic
            # Similar to LEStrategy
            merged_df = LEStrategy().process_data(watra_df, sap_df, pri_vice_vysledcich)
        
        else:
            # Default case - just return WATRA data
            merged_df = watra_df.copy()
        
        # Apply filtering rules based on pri_vice_vysledcich
        if pri_vice_vysledcich == 'první':
            merged_df = merged_df.sort_values('zasilkaID').groupby('zasilkaID').first().reset_index()
        elif pri_vice_vysledcich == 'poslední':
            merged_df = merged_df.sort_values('zasilkaID').groupby('zasilkaID').last().reset_index()
        elif pri_vice_vysledcich == 'po_MRTIME_nejblizsi':
            # Similar to LEStrategy implementation for time-based filtering
            # Convert BDATU and BZEIT to datetime and find closest match
            def convert_to_datetime(row):
                try:
                    if pd.notna(row['bdatu']) and pd.notna(row['bzeit']):
                        bdatu = str(row['bdatu'])
                        bzeit = str(row['bzeit'])
                        
                        # Format: YYYYMMDD and HHMMSS
                        year = int(bdatu[:4])
                        month = int(bdatu[4:6])
                        day = int(bdatu[6:8])
                        
                        hour = int(bzeit[:2])
                        minute = int(bzeit[2:4])
                        second = int(bzeit[4:6]) if len(bzeit) >= 6 else 0
                        
                        return datetime(year, month, day, hour, minute, second)
                except:
                    return None
                return None
            
            merged_df['sap_datetime'] = merged_df.apply(convert_to_datetime, axis=1)
            
            # Calculate time difference
            merged_df['time_diff'] = merged_df.apply(
                lambda row: abs((row['MRtime'] - row['sap_datetime']).total_seconds()) 
                if pd.notna(row['sap_datetime']) else float('inf'), 
                axis=1
            )
            
            # Get the record with minimal time difference for each zasilkaID
            merged_df = merged_df.sort_values('time_diff').groupby('zasilkaID').first().reset_index()
        
        return merged_df
    

class MultibaleniStrategy(SAPStrategy):
    """Strategy for Multibaleni format that maps to TANUM+TAPOS through WATRAmb table."""
    
    def process_data(self, watra_df, sap_df, pri_vice_vysledcich, months_back=6):
        """Process data for Multibaleni format by looking up in WATRAmb table."""
        try:
            # Instead of querying WATRA database directly, we'll use the local SQLite copy
            from config import DATABASE_FILE
            import sqlite3
            from datetime import datetime, timedelta
            import pandas as pd
            
            threshold_date = (datetime.now() - timedelta(days=30 * months_back)).strftime('%Y-%m-%d')
            
            # Connect to SQLite
            conn = sqlite3.connect(DATABASE_FILE)
            
            # Query to get all recent multibaleni entries with their latest zasilkaID
            query = """
            WITH LatestEntries AS (
                SELECT 
                    mb,
                    zasilkaID,
                    ROW_NUMBER() OVER (PARTITION BY mb ORDER BY mbTime DESC) as row_num
                FROM watra_mb
                WHERE mbTime >= ?
            )
            SELECT mb, zasilkaID
            FROM LatestEntries
            WHERE row_num = 1
            """
            
            mb_df = pd.read_sql_query(query, conn, params=(threshold_date,))
            
            conn.close()
            
            if mb_df.empty:
                return watra_df  # Return original data if no mapping found
            
            # Merge the mb mapping with original watra data
            merged_df = pd.merge(
                watra_df,
                mb_df,
                left_on='zasilkaID',
                right_on='mb',
                how='left',
                suffixes=('', '_mb')
            )
            
            # Now proceed with the TANUM+TAPOS processing
            # Extract TANUM (first 9 digits) and TAPOS (next 4 digits)
            merged_df['extracted_tanum'] = merged_df['zasilkaID_mb'].str[0:10]
            merged_df['extracted_tapos'] = merged_df['zasilkaID_mb'].str[10:14]
            
            # Process only rows where mapping was found
            valid_df = merged_df.dropna(subset=['zasilkaID_mb'])
            
            if valid_df.empty:
                return watra_df  # Return original data if no valid mappings
            
            # Merge with SAP data on TANUM and TAPOS
            sap_merged_df = pd.merge(
                valid_df,
                sap_df,
                left_on=['extracted_tanum', 'extracted_tapos'],
                right_on=['tanum', 'tapos'],
                how='left'
            )
            
            # Apply filtering based on pri_vice_vysledcich
            if pri_vice_vysledcich == 'první':
                # Take the first match for each zasilkaID
                sap_merged_df = sap_merged_df.sort_values('zasilkaID').groupby('zasilkaID').first().reset_index()
            elif pri_vice_vysledcich == 'poslední':
                # Take the last match for each zasilkaID
                sap_merged_df = sap_merged_df.sort_values('zasilkaID').groupby('zasilkaID').last().reset_index()
            
            return sap_merged_df
            
        except Exception as e:
            print(f"Error in MultibaleniStrategy: {e}")
            import traceback
            traceback.print_exc()
            return watra_df  # Return original data in case of error


class StrategyFactory:
    """Factory for creating SAP data processing strategies based on POHday_pravidla_sloupce."""
    
    @staticmethod
    def get_strategy(strategy_name):
        """
        Get the appropriate strategy based on POHday_pravidla_sloupce value.
        
        Args:
            strategy_name (str): The value from POHday_pravidla_sloupce column
            
        Returns:
            SAPStrategy: The strategy implementation
        """
        strategies = {
            'TANUM+TAPOS (normalizovaný)': TANUMTPOSNormalizedStrategy(),
            'TANUM/TAPOS': TANUMTPOSSlashStrategy(),
            'LE': LEStrategy(),
            'Multibaleni': MultibaleniStrategy()
            # Add more strategies as needed
        }
        
        # Default to MATNRStrategy if strategy name not found
        return strategies.get(strategy_name, MATNRStrategy())


class SAPDataProcessor:
    """Main class for processing SAP data with different strategies."""
    
    def __init__(self, sqlite_string, months_back=6):
        """
        Initialize the SAP data processor.
        
        Args:
            sqlite_string (str): SQLite connection string (e.g., sqlite:///path/to/database.db)
            months_back (int): Number of months to look back in data
        """
        self.sqlite_string = sqlite_string
        self.months_back = months_back
        self.sap_data = pd.DataFrame()
        
    def fetch_sap_data(self):
        """
        Fetch SAP data from SQLite database.
        
        Returns:
            pd.DataFrame: DataFrame with SAP data
        """
        try:
            print(f"Fetching SAP data for the last {self.months_back} months from SQLite...")
            import time
            start_time = time.time()
            
            # Get data from SQLite via the SAPData model
            self.sap_data = SAPData.get_data(self.months_back)
            
            print(f"Fetched {len(self.sap_data)} rows in {time.time() - start_time:.2f} seconds")
            return self.sap_data
            
        except Exception as e:
            print(f"Error fetching SAP data from SQLite: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def process_watra_data(self, watra_df, strategy_name, pri_vice_vysledcich='první'):
        """
        Process WATRA data using the specified strategy.
        
        Args:
            watra_df (pd.DataFrame): DataFrame with WATRA data
            strategy_name (str): Name of the strategy from POHday_pravidla_sloupce
            pri_vice_vysledcich (str): Rule for handling multiple results
            
        Returns:
            pd.DataFrame: Processed and merged data
        """

        print(f"fetchuju sap data")
        # Fetch SAP data if not already loaded
        if self.sap_data.empty:
            self.sap_data = self.fetch_sap_data()
            
        if self.sap_data.empty:
            # If SAP data couldn't be fetched, return WATRA data as is
            return watra_df
        
        print(f"zpracovávám SAP strategii: {strategy_name}")
        # Get the strategy based on strategy_name
        strategy = StrategyFactory.get_strategy(strategy_name)
        
        # Process data using the selected strategy
        merged_data = strategy.process_data(watra_df, self.sap_data, pri_vice_vysledcich, self.months_back)

        
        return merged_data
    

