# -*- coding: utf-8 -*-
"""
================================================================================
Main Entry Point for the Customer Service Message Aggregation
================================================================================
Purpose:
----------------
This script serves as the primary executable for the initial phase of the
customer service module. Its function is to fetch all recent customer-related
messages from the Best Buy Marketplace API and save them to a local JSON file.

This aggregation step is a precursor to the more complex processing and
database migration tasks. It acts as a simple, file-based staging area for
raw message data.

NOTE: This is part of an older, file-based workflow. Newer modules in this
project are moving towards direct database interaction.
----------------
"""

# =====================================================================================
# --- Imports and Setup ---
# =====================================================================================
import sys
import os

# --- Python Path Configuration ---
# Ensures the script can find modules from other project directories.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the main logic function from the fetch_messages script.
from customer_service.message_aggregation.fetch_messages import fetch_and_save_messages


# =====================================================================================
# --- Main Execution ---
# =====================================================================================

def main():
    """
    Main function to run the customer service message aggregation phase.
    Wraps the core logic in a try...except block for basic error handling.
    """
    print("--- Starting Phase 5: Customer Service - Message Aggregation ---")

    try:
        # Call the function that handles the API calls and file saving.
        fetch_and_save_messages()
        print("--- Phase 5: Customer Service - Message Aggregation Complete ---")
    except Exception as e:
        # Catch any unexpected errors during the process.
        print(f"An error occurred during the customer service phase: {e}")
        # In a real application, you might want to add more robust error handling
        # and notifications (e.g., sending an alert to an admin).
        sys.exit(1)

if __name__ == "__main__":
    # Standard entry point for executing the script directly.
    main()
