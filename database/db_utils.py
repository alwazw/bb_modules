import os
import json
import psycopg2
from psycopg2 import extras

def get_db_connection():
    """
    Establishes and returns a connection to the PostgreSQL database.

    This function reads database connection parameters (DB name, user, password, host, port)
    from environment variables. If any variable is not set, it falls back to a
    default value suitable for the local Docker environment defined in docker-compose.yml.

    This approach allows for flexibility in deployment; the same code can be run
    locally or in a production environment with different database credentials
    by simply setting the appropriate environment variables.

    Returns:
        psycopg2.connection or None: A connection object if successful, otherwise None.
    """
    try:
        # Attempt to connect to the database using credentials from environment variables
        # or fall back to defaults.
        conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB", "order_management"),
            user=os.getenv("POSTGRES_USER", "user"),
            password=os.getenv("POSTGRES_PASSWORD", "password"),
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432")
        )
        return conn
    except psycopg2.OperationalError as e:
        # This exception is typically raised for connection-related issues,
        # such as the database server not running or incorrect credentials.
        print(f"""Error: Could not connect to the database. Please ensure it is running.
Details: {e}""")
        return None

def initialize_database():
    """
    Initializes the database by executing the DDL statements in 'schema.sql'.

    This function is designed to be idempotent. It reads the entire 'schema.sql' file,
    which should contain 'DROP TABLE IF EXISTS' statements to ensure that running
    this function on an existing database will reset it to a clean state defined
    by the schema. It's a destructive operation intended for setting up a new
    environment or for development resets.
    """
    conn = None
    try:
        # Construct the absolute path to schema.sql relative to this script's location.
        # This ensures that the script can be run from any directory.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.join(script_dir, 'schema.sql')

        print(f"INFO: Reading database schema from {schema_path}...")
        with open(schema_path, 'r') as f:
            # Read the entire content of the schema file.
            schema_sql = f.read()

        # Establish a new database connection.
        conn = get_db_connection()
        if conn is None:
            # If connection fails, get_db_connection will print the error, so we just exit.
            return

        # Use a 'with' statement for the cursor to ensure it's properly closed.
        with conn.cursor() as cur:
            print("INFO: Executing schema.sql to initialize database...")
            # Execute the entire SQL script. psycopg2 can handle multi-statement strings.
            cur.execute(schema_sql)
            # Commit the transaction to make the changes persistent.
            conn.commit()
            print("SUCCESS: Database initialized successfully.")

    except FileNotFoundError:
        # This error occurs if schema.sql is missing.
        print(f"ERROR: schema.sql not found at {schema_path}")
    except Exception as e:
        # Catch any other exceptions during the process (e.g., SQL syntax errors).
        print(f"ERROR: An error occurred during database initialization: {e}")
        if conn:
            # If an error occurs, roll back any partial changes from the transaction.
            conn.rollback()
    finally:
        # Ensure the database connection is always closed, whether success or failure.
        if conn:
            conn.close()

def log_api_call(conn, service, endpoint, related_id, request_payload, response_body, status_code, is_success):
    """
    Logs the details of a third-party API call to the generic 'api_calls' table.

    Args:
        conn: An active psycopg2 database connection object.
        service (str): The name of the service being called (e.g., 'BestBuy', 'CanadaPost').
        endpoint (str): The specific endpoint or action being performed.
        related_id (str): An ID to associate the call with (e.g., order_id).
        request_payload (dict or str): The payload sent. Will be stored as JSONB.
        response_body (str): The raw response body (can be JSON or XML text).
        status_code (int): The HTTP status code of the response.
        is_success (bool): Whether the call was considered successful.
    """
    try:
        with conn.cursor() as cur:
            # Convert dict payloads to json strings, leave others as is.
            if isinstance(request_payload, dict):
                request_payload = json.dumps(request_payload)

            cur.execute(
                """
                INSERT INTO api_calls (service, endpoint, related_id, request_payload, response_body, status_code, is_success)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (service, endpoint, related_id, request_payload, response_body, status_code, is_success)
            )
        conn.commit()
    except Exception as e:
        print(f"ERROR: Could not log API call. Reason: {e}")
        conn.rollback()


# This block allows the script to be run directly from the command line.
if __name__ == '__main__':
    print("--- Database Initializer ---")
    print("WARNING: This script is destructive and will drop all existing tables.")
    # A confirmation step to prevent accidental execution.
    confirm = input("Are you sure you want to drop all existing tables and re-initialize the database? (yes/no): ")
    if confirm.lower() == 'yes':
        initialize_database()
    else:
        print("INFO: Database initialization cancelled.")
    print("--- Finished ---")