import sys
import os

# Add project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from Orders.shipped_orders.update_tracking_info.update_tracking_numbers import main as update_tracking_main
from Orders.shipped_orders.update_tracking_info.validate_shipped_status import main as validate_status_main

def main_orchestrator():
    """
    Orchestrates the entire tracking number update process.
    """
    print("=============================================")
    print("=== PHASE 4: Update Tracking Numbers      ===")
    print("=============================================")

    print("\n>>> STEP 4.1: Updating Best Buy with tracking numbers...")
    update_tracking_main()

    import time
    print("\nINFO: Waiting for 15 seconds for API to process tracking update...")
    time.sleep(15)

    print("\n>>> STEP 4.2: Validating that order statuses are updated...")
    validate_status_main()

    print("\n=============================================")
    print("===      Phase 4 Process Has Concluded      ===")
    print("=============================================")

if __name__ == '__main__':
    main_orchestrator()
