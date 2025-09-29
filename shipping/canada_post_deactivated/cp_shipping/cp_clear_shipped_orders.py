
import os 
import json

--- Configuration ---
ORDERS_FILE = os.path.join(os.path.dirname(file), '..', '..', '..', 'Orders', 'awaiting_shipment', 'orders_awaiting_shipment', 'orders_pending_shipping.json') CP_SHIPPING_DATA_FILE = os.path.join(os.path.dirname(file), 'cp_shipping_labels_data.json')

def main(): """ Validates label creation and cleans up the pending shipping list. """ print("\n--- Starting Clear Shipped Orders Script ---")

if not os.path.exists(CP_SHIPPING_DATA_FILE):
    print("ERROR: cp_shipping_labels_data.json not found. Cannot perform cleanup.")
    return
    
with open(CP_SHIPPING_DATA_FILE, 'r') as f:
    try:
        shipped_data = json.load(f)
    except json.JSONDecodeError:
        print("ERROR: cp_shipping_labels_data.json is corrupted.")
        return
        
if not os.path.exists(ORDERS_FILE):
    print("ERROR: orders_pending_shipping.json not found.")
    return
    
with open(ORDERS_FILE, 'r') as f:
    try:
        pending_orders = json.load(f)
    except json.JSONDecodeError:
        print("ERROR: orders_pending_shipping.json is corrupted.")
        return

shipped_order_ids = {entry['order_id'] for entry in shipped_data if entry.get('tracking_pin')}

print(f"INFO: Found {len(shipped_order_ids)} successfully created shipments.")

remaining_pending_orders = [order for order in pending_orders if order['order_id'] not in shipped_order_ids]

if len(remaining_pending_orders) < len(pending_orders):
    print(f"INFO: Removing {len(pending_orders) - len(remaining_pending_orders)} shipped orders from the pending list.")
    with open(ORDERS_FILE, 'w') as f:
        json.dump(remaining_pending_orders, f, indent=4)
    print("SUCCESS: orders_pending_shipping.json has been updated.")
else:
    print("INFO: No orders to remove from the pending list.")
    
print("--- Clear Shipped Orders Script Finished ---\n")
if name == 'main': main() 
