#!/usr/bin/env python3

"""
Main entry point for the Order Acceptance Workflow.

This script initializes and runs the primary workflow for processing new orders.
The core logic, including fetching orders from the database, calling APIs,
handling retries, and logging, is located in the `order_management.workflow` module.
"""

import sys
import os

# Ensure the project root is in the Python path
# This allows for direct execution of this script from the command line
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from order_management.workflow import main as order_acceptance_main

if __name__ == '__main__':
    # Execute the main function from the refactored workflow
    order_acceptance_main()
