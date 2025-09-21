# -*- coding: utf-8 -*-
"""
================================================================================
Main Entry Point for the Customer Service Auto-Reply Module
================================================================================
Purpose:
----------------
This script serves as the primary executable for the customer service auto-reply
feature. Its main job is to trigger the business logic that scans for new
customer messages and sends automated replies based on a set of predefined rules.

This entry point script keeps the execution logic simple and separate from the
core implementation, making the system easier to manage and test.
----------------
"""

# =====================================================================================
# --- Imports and Setup ---
# =====================================================================================
import sys
import os

# --- Python Path Configuration ---
# This ensures that the script can find and import modules from other parts of
# the project, particularly the `customer_service` module. It adds the project's
# root directory to the list of paths Python searches for modules.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the main logic function from the auto_reply module.
from customer_service.src.auto_reply import run_auto_reply_logic


# =====================================================================================
# --- Main Execution ---
# =====================================================================================

def main():
    """
    Main function to run the customer service auto-reply module.
    It wraps the core logic in a try...except block to catch any unexpected
    errors and provide a clean exit status.
    """
    print("--- Starting Customer Service - Auto-Reply Module ---")
    try:
        # Call the function that contains the actual business logic.
        run_auto_reply_logic()
        print("--- Customer Service - Auto-Reply Module Complete ---")
    except Exception as e:
        # If any unhandled exception occurs, print an error message and exit
        # with a non-zero status code to indicate failure.
        print(f"An error occurred during the auto-reply process: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # This standard Python construct ensures that the `main()` function is called
    # only when the script is executed directly.
    main()
