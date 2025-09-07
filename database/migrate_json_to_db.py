import os
import json
import psycopg2
from psycopg2 import extras
from db_utils import get_db_connection

# --- Configuration ---
# Construct the absolute path to the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs', 'best_buy')
PENDING_ACCEPTANCE_FILE = os.path.join(LOGS_DIR, 'pending_acceptance.json')
ACCEPTED_LOG_FILE = os.path.join(LOGS_DIR, 'accepted_orders_log.json')
# This file is in a different log directory, based on the original file structure
CP_LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs', 'canada_post')
SHIPPED_LOG_FILE = os.path.join(CP_LOGS_DIR, 'cp_shipping_labels_data.json')


def load_json_data(filepath):
    """Safely loads data from a JSON file."""
    if not os.path.exists(filepath):
        print(f"INFO: File not found: {filepath}. Skipping.")
        return []
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"ERROR: Could not read or parse {filepath}. Reason: {e}. Skipping.")
        return []

def migrate_data():
    """Migrates data from old JSON files to the new PostgreSQL database."""
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            print("ERROR: Could not establish database connection. Aborting migration.")
            return

        with conn.cursor() as cur:
            print("\n--- Starting Migration from JSON to PostgreSQL ---")

            # 1. Process orders from pending_acceptance.json
            print(f"\nProcessing {PENDING_ACCEPTANCE_FILE}...")
            pending_orders = load_json_data(PENDING_ACCEPTANCE_FILE)
            for order_data in pending_orders:
                order_id = order_data.get('order_id')
                if not order_id:
                    continue

                # Insert into orders table
                cur.execute(
                    """
                    INSERT INTO orders (order_id, status, raw_order_data)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (order_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        raw_order_data = EXCLUDED.raw_order_data,
                        updated_at = NOW();
                    """,
                    (order_id, 'pending_acceptance', json.dumps(order_data))
                )

                # Insert into order_lines table
                for line_data in order_data.get('order_lines', []):
                    line_id = line_data.get('order_line_id')
                    if not line_id:
                        continue
                    cur.execute(
                        """
                        INSERT INTO order_lines (order_line_id, order_id, sku, quantity, raw_line_data)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (order_line_id) DO NOTHING;
                        """,
                        (line_id, order_id, line_data.get('offer_sku'), line_data.get('quantity'), json.dumps(line_data))
                    )
            print(f"Processed {len(pending_orders)} orders from pending acceptance file.")

            # 2. Update status for orders from accepted_orders_log.json
            print(f"\nProcessing {ACCEPTED_LOG_FILE}...")
            accepted_orders = load_json_data(ACCEPTED_LOG_FILE)
            for acceptance_log in accepted_orders:
                order_id = acceptance_log.get('order_id')
                if not order_id:
                    continue
                # This will update the status if the order already exists, otherwise does nothing
                cur.execute(
                    """
                    UPDATE orders SET status = 'accepted'
                    WHERE order_id = %s AND status = 'pending_acceptance';
                    """,
                    (order_id,)
                )
            print(f"Processed {len(accepted_orders)} acceptance logs.")

            # 3. Update status for shipped orders
            print(f"\nProcessing {SHIPPED_LOG_FILE}...")
            shipped_orders = load_json_data(SHIPPED_LOG_FILE)
            for ship_log in shipped_orders:
                # The order ID is nested in this file's structure
                order_id = ship_log.get('order_details', {}).get('order_id')
                if not order_id:
                    continue
                cur.execute(
                    "UPDATE orders SET status = 'shipped' WHERE order_id = %s;",
                    (order_id,)
                )
            print(f"Processed {len(shipped_orders)} shipping logs.")

            conn.commit()
            print("\nSUCCESS: Migration completed successfully!")

    except (Exception, psycopg2.DatabaseError) as e:
        print(f"\nERROR: An error occurred during migration: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    confirm = input("Are you sure you want to run the migration script? This may overwrite existing data. (yes/no): ")
    if confirm.lower() == 'yes':
        migrate_data()
    else:
        print("Migration cancelled.")
