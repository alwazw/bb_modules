# Setup and Deployment Guide

This guide provides step-by-step instructions for setting up the environment and deploying the Best Buy Order Automation application.

## 1. Prerequisites

- Docker
- Docker Compose

## 2. Installation & Setup

The entire application stack is managed by Docker Compose, simplifying the setup process significantly.

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Run the Setup Script:**
    The `setup.sh` script automates the entire setup process, including building Docker images and initializing the database.
    ```bash
    chmod +x setup.sh
    ./setup.sh
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

## 4. Running the Application

The application is divided into two main parts: the backend workflows and the web interfaces.

-   **To run the web interfaces:**
    The `run_web_interface.sh` script will start the web applications using Docker Compose.
    ```bash
    chmod +x run_web_interface.sh
    ./run_web_interface.sh
    ```
    You can then access the interfaces at:
    -   **Fulfillment Service:** `http://localhost:5001`
    -   **Customer Service:** `http://localhost:5002/conversations`

-   **To run the backend workflows:**
    The `run_core_workflows.sh` script will run the backend workflows inside a Docker container.
    ```bash
    chmod +x run_core_workflows.sh
    ./run_core_workflows.sh
    ```
    This script can be run manually or scheduled to run periodically using a tool like `cron`.
