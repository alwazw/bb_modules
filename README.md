# Best Buy Marketplace - Python Order Automation

This project provides a command-line based Python application to automate the acceptance of orders and creation of shipping labels from the Best Buy Marketplace.

## Project Status
This project is under active development. The core order automation features are functional, and the shipping module has been enhanced for better robustness and logging.

## Project Phases

This project is broken down into five distinct phases, each with its own main orchestrator script:

1.  **Phase 1: Order Acceptance (`main_acceptance.py`)** - Fetches and accepts new orders from Best Buy.
2.  **Phase 2: Retrieve for Shipping (`retrieve_pending_shipping.py`)** - Gets orders that are ready for shipment. This is not a standalone phase, but part of the shipping workflow.
3.  **Phase 3: Create Shipping Labels (`main_shipping.py`)** - Generates XML payloads and creates Canada Post shipping labels.
4.  **Phase 4: Update Tracking Numbers (`main_tracking.py`)** - Updates Best Buy with the new tracking numbers.
5.  **Phase 5: Customer Service (`main_customer_service.py`)** - Fetches and aggregates customer messages from Best Buy.

## Fulfillment Service

In addition to the core automation scripts, this project now includes a **Fulfillment Service**, a standalone Flask application designed to guide technicians through the physical assembly and labeling process. This service helps prevent assembly errors and shipping mix-ups.

For detailed information on the service, its API, and how to run it, please see the dedicated documentation:
[**Fulfillment Service README**](./fulfillment_service/README.md)

## Shipping Module

The shipping module has been enhanced for better error handling and logging. For detailed information on the shipping module, its components, and how to troubleshoot common issues, please see the dedicated documentation:
[**Shipping Module README**](./shipping/README.md)

## 🚀 Getting Started

### 1. Prerequisites

*   Python 3.6+
*   `requests` library

### 2. Installation

1.  **Clone the repository** and navigate into the directory.

2.  **Create and activate a virtual environment:**
    *   `python3 -m venv venv`
    *   On macOS/Linux: `source venv/bin/activate`
    *   On Windows: `.\venv\Scripts\activate`

3.  **Install dependencies:**
    *   `pip install requests`

4.  **Add your API Keys:**
    *   Open `secrets.txt` and add your Best Buy and Canada Post credentials.
    *   **IMPORTANT:** In `shipping/canada_post/cp_shipping/cp_pdf_labels.py`, you must replace `"YOUR_CUSTOMER_NUMBER"` with your actual Canada Post customer number.

### 3. Running the Application

Run each phase in order using the main orchestrator scripts:

```bash
# Phase 1: Accept new orders
python3 main_acceptance.py

# Phase 3: Create shipping labels
python3 main_shipping.py

# Phase 4: Update tracking info on Best Buy
python3 main_tracking.py

# Phase 5: Fetch customer messages
python3 main_customer_service.py
```
