import os
import json
import psycopg2
import argparse
from psycopg2 import extras

def get_db_connection():
    """
    Establishes and returns a connection to the PostgreSQL database.
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
        print(f"""Error: Could not connect to the database. Please ensure it is running.
Details: {e}""")
        return None

def initialize_database():
    """
    Initializes the database by executing the DDL statements in 'schema.sql'.
    """
    conn = None
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.join(script_dir, 'schema.sql')
        print(f"INFO: Reading database schema from {schema_path}...")
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        conn = get_db_connection()
        if conn is None:
            return
        with conn.cursor() as cur:
            print("INFO: Executing schema.sql to initialize database...")
            cur.execute(schema_sql)
            conn.commit()
            print("SUCCESS: Database initialized successfully.")
    except FileNotFoundError:
        print(f"ERROR: schema.sql not found at {schema_path}")
    except Exception as e:
        print(f"ERROR: An error occurred during database initialization: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def add_order_status_history(conn, order_id, new_status, notes=None):
    """
    Inserts a new record into the 'order_status_history' table.
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
    """
    try:
        with conn.cursor() as cur:
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
    Logs the details of a third-party API call to the generic 'api_calls' table.
    """
    try:
        with conn.cursor() as cur:
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

def get_shipment_details_from_db(conn, shipment_id):
    """
    Fetches shipment details from the database by shipment_id.
    """
    details = None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM shipments WHERE shipment_id = %s;", (shipment_id,))
            details = dict(cur.fetchone()) if cur.rowcount > 0 else None
    except Exception as e:
        print(f"ERROR: Could not fetch shipment details for shipment_id {shipment_id}. Reason: {e}")
    return details

def update_shipment_status_in_db(conn, shipment_id, status, notes=""):
    """
    Updates the status and notes of a shipment in the database.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE shipments
                SET status = %s, notes = %s
                WHERE shipment_id = %s;
                """,
                (status, notes, shipment_id)
            )
        conn.commit()
        print(f"INFO: Updated shipment {shipment_id} status to '{status}'.")
    except Exception as e:
        print(f"ERROR: Could not update status for shipment {shipment_id}. Reason: {e}")
        conn.rollback()

def get_shipments_details_by_order_id(conn, order_id):
    """
    Fetches all shipment details for a given order_id.
    """
    details = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM shipments WHERE order_id = %s;", (order_id,))
            details = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"ERROR: Could not fetch shipments for order_id {order_id}. Reason: {e}")
    return details

def get_shipment_details_by_tracking_pin(conn, tracking_pin):
    """
    Fetches shipment details from the database by tracking_pin.
    """
    details = None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM shipments WHERE tracking_pin = %s;", (tracking_pin,))
            details = dict(cur.fetchone()) if cur.rowcount > 0 else None
    except Exception as e:
        print(f"ERROR: Could not fetch shipment for tracking_pin {tracking_pin}. Reason: {e}")
    return details

def get_orders_by_date_range(conn, days=30):
    """
    Fetches all orders from the database within a given date range that have a shipment record.
    """
    orders = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # This query joins orders with shipments and filters by the order date.
            cur.execute("""
                SELECT o.*, s.shipment_id, s.tracking_pin, s.status as shipment_status, s.cp_api_label_url
                FROM orders o
                JOIN shipments s ON o.order_id = s.order_id
                WHERE o.created_at >= NOW() - INTERVAL '%s days';
            """, (days,))
            orders = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"ERROR: Could not fetch orders from the last {days} days. Reason: {e}")
    return orders

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Database utility script.")
    parser.add_argument('--init', action='store_true', help='Initialize the database schema without prompting for confirmation.')
    args = parser.parse_args()

    if args.init:
        print("--- Database Initializer (non-interactive) ---")
        initialize_database()
    else:
        print("--- Database Initializer ---")
        print("WARNING: This script is destructive and will drop all existing tables.")
        confirm = input("Are you sure you want to drop all existing tables and re-initialize the database? (yes/no): ")
        if confirm.lower() == 'yes':
            initialize_database()
        else:
            print("INFO: Database initialization cancelled.")
    print("--- Finished ---")
