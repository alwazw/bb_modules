#!/usr/bin/env python3

"""
Main entry point for the Order Acceptance Workflow.

This script serves as the primary executable for the order acceptance phase.
Its sole responsibility is to import and trigger the main workflow function
from the `order_management.workflow` module.

This clean separation of concerns (entry point vs. logic) makes the system
more modular and easier to test and maintain.
"""

import sys
import os

# --- Python Path Configuration ---
# This section ensures that the script can be run from anywhere and still find
# its necessary modules (like 'order_management' and 'database').
#
# It gets the directory of the current script (e.g., /path/to/project/) and
# adds it to the list of paths that Python searches for modules.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Import the main function from the workflow module, giving it a clear, specific name.
from order_management.workflow import main as order_acceptance_main

# The `if __name__ == '__main__':` block is a standard Python construct.
# It ensures that the code inside it only runs when the script is executed
# directly (e.g., `python3 main_acceptance.py`), and not when it's imported
# by another script.
if __name__ == '__main__':
    # Execute the main function from the refactored workflow.
    # All the complex logic resides in that function.
    order_acceptance_main()
