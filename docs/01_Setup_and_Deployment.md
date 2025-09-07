# Setup and Deployment Guide

This guide provides step-by-step instructions for setting up the environment and deploying the Best Buy Order Automation application.

## 1. Prerequisites

- Python 3.6+
- `pip` for installing packages

## 2. Installation

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create and Activate a Virtual Environment:**
    It is highly recommended to use a virtual environment to manage dependencies.
    -   **On macOS/Linux:**
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    -   **On Windows:**
        ```bash
        python -m venv venv
        .\venv\Scripts\activate
        ```

3.  **Install Dependencies:**
    The only external dependency is the `requests` library.
    ```bash
    pip install requests
    ```

## 3. Configuration

All sensitive information, such as API keys and customer numbers, is stored in the `secrets.txt` file in the root directory. You must populate this file with your credentials before running the application.

1.  **Create `secrets.txt`:**
    If it doesn't exist, create a file named `secrets.txt` in the root of the project.

2.  **Add Credentials:**
    Open `secrets.txt` and add the following keys, replacing the placeholder values with your actual credentials.

    ```ini
    # Best Buy Marketplace API Key
    BEST_BUY_API_KEY=your_best_buy_api_key_here

    # Canada Post Production API Credentials
    CANADA_POST_API_USER=your_production_api_user_here
    CANADA_POST_API_PASSWORD=your_production_api_password_here
    CANADA_POST_CUSTOMER_NUMBER=your_10_digit_customer_number_here
    CANADA_POST_PAID_BY_CUSTOMER=your_10_digit_paid_by_customer_number_here
    CANADA_POST_CONTRACT_ID=your_10_digit_contract_id_here
    ```

    **Note:** All Canada Post numbers should be padded with leading zeros to be 10 digits if necessary.

## 4. Running the Application

The application is designed to run continuously via a master scheduler.

-   **To start the master scheduler:**
    ```bash
    python3 main_scheduler.py
    ```

This will start the main loop, which runs every 15 minutes to check for new orders and process them through the entire workflow.

-   **To run individual phases manually:**
    You can also run the main orchestrator for each phase individually for testing or manual processing.
    -   **Accept Orders:**
        ```bash
        python3 main_acceptance.py
        ```
    -   **Process Shippable Orders:**
        ```bash
        python3 main_shipping.py
        ```
    -   **Update Tracking:**
        ```bash
        python3 main_tracking.py
        ```
