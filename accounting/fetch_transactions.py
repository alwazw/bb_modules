import json
import os
import requests
from datetime import datetime, timedelta

API_BASE_URL = "https://marketplace.bestbuy.ca/api"

def load_api_key(secret_file="secrets.txt"):
    """Loads the Best Buy API key from the secrets file."""
    try:
        with open(secret_file, "r") as f:
            for line in f:
                if line.startswith("BEST_BUY_API_KEY="):
                    return line.strip().split("=")[1]
    except FileNotFoundError:
        print(f"Error: {secret_file} not found.")
        return None
    return None

import argparse

def get_transactions(api_key, date_from=None):
    """
    Fetches accounting transactions from the Mirakl API.
    """
    print("Connecting to Mirakl API to fetch accounting transactions...")

    headers = {"Authorization": api_key}

    if not date_from:
        # Fetch transactions from the last 30 days by default.
        date_from = (datetime.utcnow() - timedelta(days=30)).isoformat() + "Z"

    params = {
        "date_created_from": date_from,
    }

    all_transactions = []
    next_page_token = None

    while True:
        if next_page_token:
            params["page_token"] = next_page_token

        response = requests.get(f"{API_BASE_URL}/sellerpayment/transactions_logs", headers=headers, params=params)

        if response.status_code != 200:
            print(f"Error fetching transactions: {response.status_code} - {response.text}")
            response.raise_for_status()

        data = response.json()
        all_transactions.extend(data.get("data", []))

        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break

    print(f"Found {len(all_transactions)} transactions.")
    return all_transactions

def save_transactions_to_json(transactions, file_path="accounting/transactions.json"):
    """
    Saves a list of transactions to a JSON file.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w") as f:
        json.dump(transactions, f, indent=4)

    print(f"Successfully saved {len(transactions)} transactions to {file_path}.")

def fetch_and_save_transactions(date_from=None):
    """
    Main orchestration function for the transaction fetching phase.
    """
    api_key = load_api_key()
    if not api_key:
        print("Could not load API key. Aborting.")
        return

    transactions = get_transactions(api_key, date_from)

    if transactions:
        save_transactions_to_json(transactions)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch accounting transactions from the Mirakl API.")
    parser.add_argument("--date-from", help="The start date for fetching transactions in ISO 8601 format (e.g., YYYY-MM-DDTHH:MM:SSZ).")
    args = parser.parse_args()

    fetch_and_save_transactions(args.date_from)
