# Master Scheduler & Workflow Execution

The application's backend processes are designed to be run periodically to check for new orders and move existing orders through the fulfillment lifecycle. This can be achieved in two ways: via the master scheduler or by running the workflows directly.

## 1. Manual Workflow Execution (`run_core_workflows.sh`)

For manual execution or integration with external schedulers (like a cron job), the `run_core_workflows.sh` script is the recommended method.

This script executes the entire data processing pipeline a single time, running each workflow in the correct sequence:
1.  **Run `main_acceptance.py`:** Fetches and accepts new orders.
2.  **Run `main_shipping.py`:** Creates shipping labels for accepted orders.
3.  **Run `main_tracking.py`:** Updates Best Buy with tracking numbers.

### How to Run
```bash
# From the project root
./run_core_workflows.sh
```

## 2. Continuous Operation (`main_scheduler.py`)

The `main_scheduler.py` script provides a way to run the application continuously. It runs an infinite loop that executes the main workflow scripts every 15 minutes (this interval is configurable in the script).

### How it Works (v2)

The scheduler has been refactored for robustness. Instead of importing functions from other scripts, it uses Python's `subprocess` module to launch each main workflow (`main_acceptance.py`, etc.) as a completely separate process.

-   **Isolation:** This ensures that an unhandled error in one workflow will not crash the main scheduler. The scheduler will log the error and continue its loop.
-   **Extensibility:** The sequence of scripts to run is defined in a simple list (`WORKFLOW_SCRIPTS`) at the top of the file, making it easy to add, remove, or reorder steps.

### How to Run
```bash
# From the project root
python3 main_scheduler.py
```
The scheduler will print detailed logs to the console as it progresses through each cycle. To stop the scheduler, press `Ctrl+C`.
