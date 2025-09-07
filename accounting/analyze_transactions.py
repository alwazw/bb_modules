import json
import os

import csv

def load_transactions(file_path="accounting/transactions.csv"):
    """Loads transactions from a CSV file."""
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return None
    with open(file_path, "r") as f:
        reader = csv.DictReader(f)
        return list(reader)

def analyze_and_remodel_transactions(transactions):
    """
    Analyzes and remodels a list of transactions.
    """
    orders = {}
    for transaction in transactions:
        order_id = transaction.get("Order ID")
        if not order_id or order_id == "-":
            continue

        if order_id not in orders:
            orders[order_id] = {
                "order_id": order_id,
                "transactions": [],
                "analysis": {
                    "selling_price": 0.0,
                    "taxes": 0.0,
                    "commission": 0.0,
                    "commission_tax": 0.0,
                    "refunded_amount": 0.0,
                    "refunded_tax": 0.0,
                    "net_revenue": 0.0
                }
            }

        orders[order_id]["transactions"].append(transaction)

        transaction_type = transaction.get("Type")
        amount_str = transaction.get("Amount", "0.0").replace("$", "").replace(",", "")
        try:
            amount = float(amount_str)
        except ValueError:
            continue

        if transaction_type == "Order amount":
            orders[order_id]["analysis"]["selling_price"] += amount
        elif transaction_type == "Order amount tax":
            orders[order_id]["analysis"]["taxes"] += amount
        elif transaction_type == "Commission":
            orders[order_id]["analysis"]["commission"] += abs(amount)
        elif transaction_type == "Commission tax":
            orders[order_id]["analysis"]["commission_tax"] += abs(amount)
        elif transaction_type == "Order amount refund":
            orders[order_id]["analysis"]["refunded_amount"] += abs(amount)
        elif transaction_type == "Order amount tax refund":
            orders[order_id]["analysis"]["refunded_tax"] += abs(amount)
        elif transaction_type == "Commission refund":
            orders[order_id]["analysis"]["commission"] -= abs(amount)
        elif transaction_type == "Commission tax refund":
            orders[order_id]["analysis"]["commission_tax"] -= abs(amount)

    # Calculate net revenue
    for order_id, data in orders.items():
        analysis = data["analysis"]
        net_revenue = (analysis["selling_price"] + analysis["taxes"]) - (analysis["commission"] + analysis["commission_tax"] + analysis["refunded_amount"] + analysis["refunded_tax"])
        analysis["net_revenue"] = round(net_revenue, 2)

    return list(orders.values())

def save_analyzed_transactions(data, file_path="accounting/analyzed_transactions.json"):
    """Saves analyzed transactions to a JSON file."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)
    print(f"Successfully saved analyzed transactions to {file_path}.")

def main():
    """Main orchestration function."""
    transactions = load_transactions()
    if transactions:
        analyzed_data = analyze_and_remodel_transactions(transactions)
        save_analyzed_transactions(analyzed_data)

if __name__ == "__main__":
    main()
