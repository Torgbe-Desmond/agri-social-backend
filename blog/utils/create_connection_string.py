
def get_connection_string(auth_type, server_name, database_name, username=None, password=None, driver="ODBC Driver 17 for SQL Server"):
    """
    Returns a formatted connection string based on the authentication type.

    :param auth_type: 'local' for Windows Authentication, 'password' for SQL Server Authentication
    :param server_name: SQL Server name (e.g., 'localhost')
    :param database_name: Database name (e.g., 'FarmAppDB')
    :param username: SQL Server username (required if auth_type is 'password')
    :param password: SQL Server password (required if auth_type is 'password')
    :param driver: ODBC Driver (default: 'ODBC Driver 17 for SQL Server')
    :return: Connection string
    """
    
    if auth_type == 'local':  # Windows Authentication
        connection_string = f"mssql+pyodbc://{server_name}/{database_name}?driver={driver.replace(' ', '+')}&trusted_connection=yes"
    elif auth_type == 'password' and username and password:  # SQL Server Authentication
        connection_string = f"mssql+pyodbc://{username}:{password}@{server_name}/{database_name}?driver={driver.replace(' ', '+')}"
    else:
        raise ValueError("For 'password' auth_type, both username and password must be provided.")

    return connection_string

