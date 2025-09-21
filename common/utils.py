# -*- coding: utf-8 -*-
"""
================================================================================
Common Utility Functions
================================================================================
Purpose:
----------------
This script provides common, reusable utility functions that are shared across
multiple modules in the project. The primary purpose is to handle the reading
of sensitive information (API keys and credentials) from a `secrets.txt` file.

By centralizing the logic for accessing secrets, we can easily manage how
credentials are loaded and used throughout the application, and we avoid
duplicating this code in every script that needs it.

Key Functions:
- `get_secret(key_name)`: The core function that reads the `secrets.txt` file
  line by line and extracts the value for a given key.
- `get_best_buy_api_key()`: A specific helper function that uses `get_secret`
  to fetch the Best Buy API key.
- `get_canada_post_credentials()`: A helper function that retrieves all necessary
  credentials for the Canada Post API and returns them as a tuple.
----------------
"""

# =====================================================================================
# --- Imports and Configuration ---
# =====================================================================================
import os

# Define the path to the secrets file, which is expected to be in the project root.
# `os.path.dirname(__file__)` gets the directory of the current script (e.g., /app/common)
# `os.path.join(..., '..', 'secrets.txt')` goes up one level to the project root
# and then looks for `secrets.txt`.
SECRETS_FILE = os.path.join(os.path.dirname(__file__), '..', 'secrets.txt')


# =====================================================================================
# --- Core Functions ---
# =====================================================================================

def get_secret(key_name):
    """
    Reads a specific key from the `secrets.txt` file.

    The `secrets.txt` file is expected to be a simple key-value store, with each
    line formatted as `KEY_NAME=SECRET_VALUE`.

    Args:
        key_name (str): The name of the key to retrieve (e.g., "BEST_BUY_API_KEY").

    Returns:
        str or None: The secret value as a string if the key is found, otherwise None.
    """
    try:
        with open(SECRETS_FILE, 'r') as f:
            for line in f:
                # Check if the line starts with the key we're looking for.
                if line.startswith(key_name + '='):
                    # Split the line at the first '=' and take the second part.
                    secret_value = line.strip().split('=', 1)[1]
                    return secret_value
        # If the loop finishes without finding the key.
        print(f"ERROR: Key '{key_name}' not found in {SECRETS_FILE}")
        return None
    except FileNotFoundError:
        # If the secrets.txt file doesn't exist at all.
        print(f"ERROR: {SECRETS_FILE} not found.")
        return None

def get_best_buy_api_key():
    """
    A simple helper function to get the Best Buy API key.
    This makes the calling code cleaner (e.g., `get_best_buy_api_key()` instead of
    `get_secret('BEST_BUY_API_KEY')`).

    Returns:
        str or None: The Best Buy API key, or None if not found.
    """
    return get_secret('BEST_BUY_API_KEY')

def get_canada_post_credentials():
    """
    A helper function that retrieves all required Canada Post credentials at once.

    It fetches each required key and then checks if all of them were found before
    returning them. This ensures that the calling code gets either all the
    credentials it needs or nothing at all, preventing partial failures.

    Returns:
        tuple: A tuple containing (user, password, customer_number, paid_by, contract_id)
               if all credentials are found.
        tuple: A tuple of (None, None, None, None, None) if any credential is missing.
    """
    user = get_secret('CANADA_POST_API_USER')
    password = get_secret('CANADA_POST_API_PASSWORD')
    customer_number = get_secret('CANADA_POST_CUSTOMER_NUMBER')
    paid_by = get_secret('CANADA_POST_PAID_BY_CUSTOMER')
    contract_id = get_secret('CANADA_POST_CONTRACT_ID')

    # `all()` checks if every item in the list is "truthy" (i.e., not None or empty).
    if all([user, password, customer_number, paid_by, contract_id]):
        print("SUCCESS: All Canada Post credentials loaded.")
        return user, password, customer_number, paid_by, contract_id
    else:
        print("ERROR: Could not find all required Canada Post credentials in secrets.txt")
        return None, None, None, None, None
