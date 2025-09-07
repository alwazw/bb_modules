# Master Scheduler

The `main_scheduler.py` script is the main entry point for running the application in a continuous, automated fashion.

## How it Works

The scheduler runs an infinite loop that executes the entire order processing workflow every 15 minutes (this interval is configurable in the script).

In each cycle, it performs the following actions in sequence:

1.  **Run `main_acceptance.py`:** Checks for and accepts any new orders.
2.  **Run `main_shipping.py`:** Checks for any orders that are ready for shipment, creates labels for them (if not already created), and validates the new shipments with Canada Post.
3.  **Run `main_tracking.py`:** Updates Best Buy with the tracking numbers for the newly created shipments and marks them as shipped.
4.  **Run `main_customer_service.py`:** Fetches new customer messages from the Best Buy API and saves them for processing.

## How to Run

To start the scheduler, simply run the following command from the root of the project:

```bash
python3 main_scheduler.py
```

The scheduler will print detailed logs to the console as it progresses through each phase of the workflow. To stop the scheduler, press `Ctrl+C`.
