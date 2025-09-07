import time
import sys
import os

# Add project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from main_acceptance import main_orchestrator as accept_orders_main
from main_shipping import process_shippable_orders
from main_tracking import main_orchestrator as tracking_update_main
from main_customer_service import main as customer_service_main

SCHEDULER_INTERVAL_SECONDS = 900 # 15 minutes

def main():
    """
    Master scheduler to run the entire order processing workflow in a loop.
    """
    print("=============================================")
    print("===      STARTING MASTER SCHEDULER        ===")
    print("=============================================")

    while True:
        print(f"\n\n\n{'='*20} RUNNING WORKFLOW CYCLE AT {time.ctime()} {'='*20}")

        # --- PHASE 1: ACCEPT NEW ORDERS ---
        print("\n>>> Checking for new orders to accept...")
        accept_orders_main()

        # --- PHASE 2: PROCESS SHIPPABLE ORDERS ---
        print("\n>>> Checking for shippable orders...")
        process_shippable_orders()

        # --- PHASE 3: UPDATE TRACKING FOR SHIPPED ORDERS ---
        print("\n>>> Checking for shipped orders to update...")
        tracking_update_main()

        # --- PHASE 5: AGGREGATE CUSTOMER MESSAGES ---
        print("\n>>> Checking for new customer messages...")
        customer_service_main()

        print(f"\n{'='*20} WORKFLOW CYCLE COMPLETE {'='*20}")
        print(f"--- Scheduler sleeping for {SCHEDULER_INTERVAL_SECONDS / 60} minutes... ---")
        time.sleep(SCHEDULER_INTERVAL_SECONDS)


if __name__ == '__main__':
    main()
