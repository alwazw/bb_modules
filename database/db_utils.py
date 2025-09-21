# -*- coding: utf-8 -*-
"""
================================================================================
Database Utility Functions
================================================================================
Purpose:
----------------
This script provides a centralized set of utility functions for interacting with
the PostgreSQL database. It handles common tasks such as establishing a database
connection, initializing the schema, and logging various events like status
changes, API calls, and critical process failures.

By centralizing these functions, we ensure that all parts of the application
interact with the database in a consistent and reliable manner.

Key Functions:
- `get_db_connection()`: Establishes a connection using environment variables,
  making the application portable between development and production environments.
- `initialize_database()`: A destructive but essential function to set up the
  database schema from the `schema.sql` file. It's used for initial setup and
  for resetting the database during testing.
- `add_order_status_history()`: Adds a new entry to the order status audit trail.
- `log_process_failure()`: Logs errors that require manual intervention.
- `log_api_call()`: Logs every interaction with external APIs for debugging
  and auditing.

This script can also be run directly from the command line to initialize the
database, with or without a confirmation prompt.
----------------
"""

# =====================================================================================
# --- Imports ---
# =====================================================================================
import os
import json
import psycopg2
import argparse
from psycopg2 import extras


# =====================================================================================
# --- Core Database Functions ---
# =====================================================================================

def get_db_connection():
    """
    Establishes and returns a connection to the PostgreSQL database.

    It reads connection parameters (host, port, user, password, dbname) from
    environment variables. This is a best practice for security and portability,
    as it avoids hardcoding credentials in the source code. Default values are
    provided to facilitate local development.

    Returns:
        psycopg2.connection or None: An active database connection object if
                                     successful, otherwise None.
    """
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB", "order_management"),
            user=os.getenv("POSTGRES_USER", "user"),
            password=os.getenv("POSTGRES_PASSWORD", "password"),
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432")
        )
        return conn
    except psycopg2.OperationalError as e:
        # This error typically occurs if the database server is not running or
        # is not accessible from where the script is being run.
        print(f"""Error: Could not connect to the database. Please ensure it is running.
Details: {e}""")
        return None

def initialize_database():
    """
    Initializes the database by executing the DDL statements in `schema.sql`.

    This is a **DESTRUCTIVE** operation. It will drop all existing tables defined
    in the schema file before recreating them. This is useful for setting up a
    clean database from scratch or for resetting the database during testing.
    """
    conn = None
    try:
        # Construct the full path to the schema.sql file, assuming it's in the
        # same directory as this script.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.join(script_dir, 'schema.sql')
        print(f"INFO: Reading database schema from {schema_path}...")

        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        conn = get_db_connection()
        if conn is None:
            # Abort if we couldn't even get a connection.
            return

        with conn.cursor() as cur:
            print("INFO: Executing schema.sql to initialize database...")
            # Execute the entire content of the .sql file.
            cur.execute(schema_sql)
            conn.commit()
            print("SUCCESS: Database initialized successfully.")
    except FileNotFoundError:
        print(f"ERROR: schema.sql not found at {schema_path}")
    except Exception as e:
        print(f"ERROR: An error occurred during database initialization: {e}")
        if conn:
            conn.rollback() # Roll back any partial changes on error.
    finally:
        if conn:
            conn.close()


# =====================================================================================
# --- Logging and Auditing Functions ---
# =====================================================================================

def add_order_status_history(conn, order_id, new_status, notes=None):
    """
    Inserts a new record into the 'order_status_history' table.

    This function is the single source of truth for changing an order's status.
    Instead of updating a status field on an order, we append a new row to its
    history, creating a powerful audit trail.

    Args:
        conn: An active psycopg2 database connection object.
        order_id (str): The ID of the order being updated.
        new_status (str): The new status for the order (e.g., 'accepted', 'shipped').
        notes (str, optional): Any additional context for the status change.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO order_status_history (order_id, status, notes) VALUES (%s, %s, %s);",
                (order_id, new_status, notes)
            )
        conn.commit()
        print(f"INFO: Order {order_id} status updated to '{new_status}'.")
    except Exception as e:
        print(f"ERROR: Could not update order status for {order_id}. Reason: {e}")
        conn.rollback()

def log_process_failure(conn, related_id, process_name, details, payload=None):
    """
    Logs a critical, unrecoverable error to the 'process_failures' table.

    This table is for errors that require manual intervention, such as a persistent
    API failure or a validation mismatch.

    Args:
        conn: An active psycopg2 database connection object.
        related_id (str): The ID of the item being processed (e.g., an order_id).
        process_name (str): The name of the workflow where the failure occurred.
        details (str): A human-readable description of the error.
        payload (dict, optional): The data object that was being processed.
    """
    try:
        with conn.cursor() as cur:
            # Convert dict payload to JSON string for storage.
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            cur.execute(
                "INSERT INTO process_failures (related_id, process_name, details, payload) VALUES (%s, %s, %s, %s);",
                (related_id, process_name, details, payload)
            )
        conn.commit()
        print(f"CRITICAL: Logged process failure for '{related_id}' in process '{process_name}'.")
    except Exception as e:
        print(f"ERROR: Could not log process failure. Reason: {e}")
        conn.rollback()

def log_api_call(conn, service, endpoint, related_id, request_payload, response_body, status_code, is_success):
    """
    Logs the details of every third-party API call to the 'api_calls' table.

    This provides a complete audit trail of all interactions with external
    services like Best Buy and Canada Post, which is invaluable for debugging.

    Args:
        conn: An active psycopg2 database connection object.
        service (str): The name of the service being called (e.g., 'BestBuy').
        endpoint (str): The specific API endpoint being called.
        related_id (str): The ID of the item related to the call (e.g., order_id).
        request_payload (dict or str): The payload sent in the request.
        response_body (str): The raw text of the API response.
        status_code (int): The HTTP status code of the response.
        is_success (bool): Whether the call was considered successful.
    """
    try:
        with conn.cursor() as cur:
            # Convert dict payload to JSON string for storage.
            if isinstance(request_payload, dict):
                request_payload = json.dumps(request_payload)
            cur.execute(
                "INSERT INTO api_calls (service, endpoint, related_id, request_payload, response_body, status_code, is_success) VALUES (%s, %s, %s, %s, %s, %s, %s);",
                (service, endpoint, related_id, request_payload, response_body, status_code, is_success)
            )
        conn.commit()
    except Exception as e:
        print(f"ERROR: Could not log API call. Reason: {e}")
        conn.rollback()


# =====================================================================================
# --- Script Execution (for direct command-line use) ---
# =====================================================================================
if __name__ == '__main__':
    # This block allows the script to be run directly to initialize the database.
    parser = argparse.ArgumentParser(description="Database utility script.")
    parser.add_argument(
        '--init',
        action='store_true',
        help='Initialize the database schema without prompting for confirmation.'
    )
    args = parser.parse_args()

    if args.init:
        # The '--init' flag is used by the automated setup.sh script.
        print("--- Database Initializer (non-interactive) ---")
        initialize_database()
    else:
        # Running the script manually will provide a confirmation prompt.
        print("--- Database Initializer ---")
        print("WARNING: This script is destructive and will drop all existing tables.")
        confirm = input("Are you sure you want to drop all existing tables and re-initialize the database? (yes/no): ")
        if confirm.lower() == 'yes':
            initialize_database()
        else:
            print("INFO: Database initialization cancelled.")
    print("--- Finished ---")
