# Master Scheduler & Workflow Execution

The application's backend processes are designed to be run periodically to check for new orders and move existing orders through the fulfillment lifecycle. This document explains the two primary ways to execute these workflows.

## 1. Manual, Single-Cycle Execution (`run_core_workflows.sh`)

For manual execution or for integration with external, industry-standard schedulers (like a Linux `cron` job), the `run_core_workflows.sh` script is the recommended method.

This script executes the entire data processing pipeline **a single time**. It runs each core workflow in the correct, logical sequence to ensure data integrity.

### The Workflow Sequence:
1.  **Run `main_acceptance.py`**: Fetches and accepts new orders from the marketplace.
2.  **Run `main_shipping.py`**: Creates shipping labels for any orders that were just accepted.
3.  **Run `main_tracking.py`**: Updates Best Buy with tracking numbers for any labels that were just created.
4.  **Run `main_customer_service.py`**: Fetches the latest customer messages.

### How to Run:
```bash
# From the project root directory
./run_core_workflows.sh
```
This is the ideal way to run the process in a production environment, as it relies on a proven and simple execution script that can be easily integrated into standard server management tools.

---

## 2. Continuous Operation via Python Scheduler (`main_scheduler.py`)

The `main_scheduler.py` script provides a simple, self-contained way to run the application continuously without relying on external tools like `cron`. It runs an infinite loop that executes the main workflow scripts every 15 minutes (this interval is configurable in the script).

### How it Works (v2)

The scheduler has been refactored for improved robustness and process isolation. Instead of importing and calling Python functions from other scripts (which would cause a crash in one to crash them all), it now uses Python's `subprocess` module to launch each main workflow (`main_acceptance.py`, etc.) as a **completely separate process**.

-   **Process Isolation**: This is a key feature. It ensures that an unhandled error in one workflow (e.g., in `main_shipping.py`) will not crash the main scheduler. The scheduler will log the error from the failed subprocess and simply continue its loop, attempting to run the next script in the sequence.
-   **Extensibility**: The sequence of scripts to run is defined in a simple list (`WORKFLOW_SCRIPTS`) at the top of the file. This makes it incredibly easy for a developer to add, remove, or reorder steps in the future without touching the core scheduler logic.
-   **Clear Logging**: The scheduler captures the standard output and standard error of each subprocess, printing it to the console for clear, real-time logging of what each workflow is doing.

### How to Run:
```bash
# From the project root, using Python
python3 main_scheduler.py
```
The scheduler will print detailed logs to the console as it progresses through each cycle. To stop the scheduler, press `Ctrl+C`. This method is best suited for local development and testing.
