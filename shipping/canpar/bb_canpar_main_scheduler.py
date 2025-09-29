import time
import schedule
import sys
import os

# Add project root to Python path to allow importing from other modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from order_management.awaiting_shipment.orders_awaiting_shipment import retrieve_pending_shipping
from shipping.canpar.canpar_scripts import canpar_bb_orders_labels_automation_api

def job():
    """
    This function defines the scheduled job. It runs the two main processes in sequence:
    1. Retrieve new orders from Best Buy and save them to the database.
    2. Process the orders that are ready for shipping to create Canpar labels.
    """
    print("======================================================")
    print(f"Starting scheduled run at {time.ctime()}")
    print("======================================================")

    # Step 1: Retrieve new orders from Best Buy
    try:
        print("\n>>> Running: Retrieve Pending Shipment Script")
        retrieve_pending_shipping.main()
        print(">>> Finished: Retrieve Pending Shipment Script\n")
    except Exception as e:
        print(f"CRITICAL ERROR in retrieve_pending_shipping script: {e}")

    # Add a small delay between tasks
    time.sleep(5)

    # Step 2: Process orders and create Canpar labels
    try:
        print("\n>>> Running: Canpar Label Automation Script")
        canpar_bb_orders_labels_automation_api.main()
        print(">>> Finished: Canpar Label Automation Script\n")
    except Exception as e:
        print(f"CRITICAL ERROR in canpar_bb_orders_labels_automation_api script: {e}")

    print("======================================================")
    print("Scheduled run finished.")
    print("======================================================")


def main():
    """
    Main function to set up and run the scheduler.
    For this implementation, it runs the job once immediately.
    In a production environment, you would use the schedule library to run it periodically.
    """
    print("--- Canpar Main Scheduler ---")

    # In a real production environment, you would use a loop like this:
    # schedule.every(30).minutes.do(job)
    # print("Scheduler started. Will run every 30 minutes.")
    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)

    # For the purpose of this project, we will just run the job once.
    job()

    print("--- Scheduler has completed its run. ---")


if __name__ == "__main__":
    main()