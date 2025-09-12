# Accounting Module

This module provides tools for fetching and analyzing financial transactions from the Best Buy Marketplace API. It helps in understanding the revenue, costs, and taxes associated with each order.

## Key Components

*   **`fetch_transactions.py`**: A script to connect to the Mirakl API and download all transaction logs for a specified period. By default, it fetches transactions from the last 30 days.
*   **`analyze_transactions.py`**: A script that takes the raw transaction data (in CSV format), remodels it, and performs an analysis. It groups transactions by order ID and calculates key metrics like selling price, taxes, commissions, and net revenue.
*   **`transactions.csv`**: The raw, unprocessed transaction data downloaded from the marketplace.
*   **`analyzed_transactions.json`**: The output of the analysis script. This file contains a structured breakdown of the financials for each order.
*   **`tax_summary.csv`**: A summary file that can be used for tax reporting purposes.

## Workflow

1.  **Fetch Data**: Run `fetch_transactions.py` to download the latest transaction data from the Best Buy Marketplace. This will save the data in `transactions.json`.
    ```bash
    python3 accounting/fetch_transactions.py
    ```
    You can also specify a start date for the transaction export:
    ```bash
    python3 accounting/fetch_transactions.py --date-from YYYY-MM-DDTHH:MM:SSZ
    ```

2.  **Convert to CSV**: The `analyze_transactions.py` script currently reads from a `transactions.csv` file. You will need to convert the `transactions.json` file to CSV format. This can be done using various tools or scripts.

3.  **Analyze Data**: Run `analyze_transactions.py` to process the `transactions.csv` file and generate the `analyzed_transactions.json` and `tax_summary.csv` files.
    ```bash
    python3 accounting/analyze_transactions.py
    ```

This module provides the financial insights necessary for bookkeeping and business analysis.
