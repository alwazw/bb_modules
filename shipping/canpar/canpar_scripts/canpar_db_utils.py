import os
import sys
import psycopg2
from psycopg2 import extras

# Add project root to Python path to allow importing from other modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)

from database.db_utils import get_db_connection, log_api_call, log_process_failure

def get_orders_ready_for_shipping():
    """
    Fetches orders that have been accepted but do not yet have a shipment record.
    This identifies orders that are ready for label creation.

    :return: A list of dictionaries, where each dictionary represents an order.
    """
    orders = []
    conn = get_db_connection()
    if not conn:
        return orders

    try:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            # This query finds the latest status for each order and filters for those
            # that are 'accepted' and not yet present in the shipments table.
            query = """
                WITH latest_status AS (
                    SELECT
                        order_id,
                        status,
                        ROW_NUMBER() OVER(PARTITION BY order_id ORDER BY timestamp DESC) as rn
                    FROM order_status_history
                )
                SELECT o.order_id, o.raw_order_data
                FROM orders o
                JOIN latest_status ls ON o.order_id = ls.order_id
                LEFT JOIN shipments s ON o.order_id = s.order_id
                WHERE ls.rn = 1 AND ls.status = 'accepted' AND s.shipment_id IS NULL;
            """
            cur.execute(query)
            rows = cur.fetchall()
            for row in rows:
                orders.append(dict(row))
            print(f"INFO: Found {len(orders)} orders ready for shipping.")
    except Exception as e:
        print(f"ERROR: Could not fetch orders ready for shipping. Reason: {e}")
    finally:
        if conn:
            conn.close()
    return orders

def create_canpar_shipment(order_id, tracking_pin, label_pdf_path):
    """
    Creates a new shipment record in the database for a Canpar shipment.

    :param order_id: The ID of the order.
    :param tracking_pin: The Canpar tracking number.
    :param label_pdf_path: The file path where the PDF label is saved.
    :return: The ID of the newly created shipment, or None if it fails.
    """
    shipment_id = None
    conn = get_db_connection()
    if not conn:
        return None

    try:
        with conn.cursor() as cur:
            # The 'cp_api_label_url' is specific to Canada Post, so we leave it null.
            query = """
                INSERT INTO shipments (order_id, tracking_pin, label_pdf_path)
                VALUES (%s, %s, %s)
                RETURNING shipment_id;
            """
            cur.execute(query, (order_id, tracking_pin, label_pdf_path))
            shipment_id = cur.fetchone()[0]
            conn.commit()
            print(f"SUCCESS: Created shipment record for order {order_id} with tracking pin {tracking_pin}.")
    except Exception as e:
        print(f"ERROR: Could not create shipment record for order {order_id}. Reason: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()
    return shipment_id

if __name__ == '__main__':
    # Example usage for testing purposes
    print("--- Testing Canpar DB Utils ---")

    # Note: This will only work if the database is running and has data.
    # orders_to_ship = get_orders_ready_for_shipping()
    # if orders_to_ship:
    #     print(f"\nFound {len(orders_to_ship)} orders to ship.")
    #     test_order = orders_to_ship[0]
    #     print(f"Test order: {test_order['order_id']}")
    #     # create_canpar_shipment(test_order['order_id'], 'TEST_TRACKING_123', '/tmp/test_label.pdf')
    # else:
    #     print("\nNo orders found that are ready for shipping.")

    print("\n--- Finished Testing ---")