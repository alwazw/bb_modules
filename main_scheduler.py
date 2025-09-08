import time
import sys
import os
import subprocess

# Add project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# --- Configuration ---
# A list of the main workflow scripts to be executed in order.
# This makes the scheduler easily extensible.
WORKFLOW_SCRIPTS = [
    "main_acceptance.py",
    "main_shipping.py",
    "main_tracking.py",
    "main_customer_service.py"
]

SCHEDULER_INTERVAL_SECONDS = 900 # 15 minutes

def run_script(script_name):
    """
    Executes a given script as a separate process using subprocess.

    Args:
        script_name (str): The filename of the Python script to run.
    """
    print(f"\n{'~'*10} Running {script_name} {'~'*10}")
    try:
        # We use subprocess.run to execute the script.
        # - sys.executable ensures we use the same Python interpreter that is running the scheduler.
        # - check=True means that if the script returns a non-zero exit code (i.e., fails),
        #   a CalledProcessError will be raised, and we can catch it.
        # - capture_output=True and text=True will capture the stdout/stderr of the script.
        result = subprocess.run(
            [sys.executable, script_name],
            check=True,
            capture_output=True,
            text=True
        )
        # Print the output of the script for logging purposes.
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("--- Script Errors ---", file=sys.stderr)
            print(result.stderr, file=sys.stderr)

    except FileNotFoundError:
        print(f"ERROR: Script not found: {script_name}", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        # This block catches errors if the script exits with a non-zero status.
        print(f"ERROR: {script_name} failed with exit code {e.returncode}", file=sys.stderr)
        print("--- STDOUT ---", file=sys.stderr)
        print(e.stdout, file=sys.stderr)
        print("--- STDERR ---", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred while running {script_name}: {e}", file=sys.stderr)


def main():
    """
    Master scheduler to run the entire order processing workflow in a loop.
    """
    print("=============================================")
    print("===      STARTING MASTER SCHEDULER v2     ===")
    print("=============================================")

    while True:
        print(f"\n\n\n{'='*20} RUNNING WORKFLOW CYCLE AT {time.ctime()} {'='*20}")

        for script in WORKFLOW_SCRIPTS:
            run_script(script)

        print(f"\n{'='*20} WORKFLOW CYCLE COMPLETE {'='*20}")
        print(f"--- Scheduler sleeping for {SCHEDULER_INTERVAL_SECONDS / 60} minutes... ---")
        time.sleep(SCHEDULER_INTERVAL_SECONDS)


if __name__ == '__main__':
    main()
