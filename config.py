import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# SQL Server configuration
SQL_SERVER = os.environ.get("SQL_SERVER")
SQL_USERNAME = os.environ.get("SQL_USERNAME")
SQL_PASSWORD = os.environ.get("SQL_PASSWORD")
ICO_DATABASE = os.environ.get("ICO_DATABASE")
WATRA_DATABASE = os.environ.get("WATRA_DATABASE")

# Oracle configuration
ORACLE_CONFIG = {
    'user': os.environ.get("ORACLE_USER"),
    'password': os.environ.get("ORACLE_PASSWORD"),
    'dsn': os.environ.get("ORACLE_DSN")
}

# Build SQL Server connection strings
def get_sql_connection_string(database):
    encoded_password = quote_plus(SQL_PASSWORD)
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={database};"
        f"UID={SQL_USERNAME};"
        f"PWD={encoded_password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=yes;"
    )
    return f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}"

# Create the connection strings
ICO_DB_CONNECTION_STRING = get_sql_connection_string(ICO_DATABASE)
WATRA_DB_CONNECTION_STRING = get_sql_connection_string(WATRA_DATABASE)

# Oracle connection string for SQLAlchemy
ORACLE_SQLALCHEMY_CONNECTION_STRING = (
    f"oracle+cx_oracle://{ORACLE_CONFIG['user']}:{ORACLE_CONFIG['password']}@{ORACLE_CONFIG['dsn']}"
)

# Alternative Windows authentication connection (commented out)
# def get_windows_auth_connection_string(database):
#     conn_str = (
#         f"DRIVER={{SQL Server}};"
#         f"SERVER={SQL_SERVER};"
#         f"DATABASE={database};"
#         f"Trusted_Connection=yes;"
#         f"TrustServerCertificate=yes"
#     )
#     return f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}"


# Update database file path
DATABASE_FILE = 'data/SchedLine.db'