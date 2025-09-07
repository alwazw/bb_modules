#!/usr/bin/env python3

"""
Main entry point for the Shipping Label Creation Workflow.

This script initializes and runs the primary workflow for creating shipping
labels for orders that have been accepted and are ready for fulfillment.

The core logic, including fetching shippable orders from the database,
generating the Canada Post XML payload, calling the API, and downloading
the PDF label, is located in the `shipping.workflow` module.
"""

import sys
import os

# Ensure the project root is in the Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Import the main function from the refactored workflow
from shipping.workflow import main as shipping_workflow_main

if __name__ == '__main__':
    # Execute the main shipping workflow
    shipping_workflow_main()
