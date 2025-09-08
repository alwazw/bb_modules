#!/usr/bin/env python3

"""
Main entry point for the Tracking Update Workflow.

This script initializes and runs the primary workflow for updating Best Buy
with tracking numbers for orders that have had shipping labels created.
It marks the orders as shipped, completing the fulfillment cycle.

The core logic is located in the `tracking.workflow` module.
"""

import sys
import os

# Ensure the project root is in the Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Import the main function from the refactored workflow
from tracking.workflow import main as tracking_workflow_main

if __name__ == '__main__':
    # Execute the main tracking workflow
    tracking_workflow_main()
