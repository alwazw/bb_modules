# Mirakl API Developer Manual
## Project: bb_modules (Best Buy Marketplace Automation)

### 1. Introduction
This manual provides the technical mapping between the `bb_modules` Python suite and the Mirakl Marketplace API. The project automates order fulfillment, inventory synchronization, and customer communication for Best Buy Marketplace.

### 2. General API Specifications
- **Base URL**: To be replaced by the specific Mirakl environment URL (e.g., Best Buy's Mirakl instance).
- **Authentication**: Include your API key in the `Authorization` header.
  - `Authorization: YOUR_API_KEY`
- **Format**: JSON is the preferred format.
- **Protocol**: HTTPS only.
- **Rate Limits**: Handled via HTTP 429 status codes. Use the `Retry-After` header.

### 3. Core Module Mapping

#### A. Order Management (`order_management`)
Handles order acceptance and retrieval.
- **Endpoints**:
  - `GET /api/orders`: Retrieve list of orders.
  - `PUT /api/orders/{order_id}/accept`: Accept a specific order.

#### B. Inventory & Offers (`inventory`, `offers`)
Manages product offers and component data.
- **Endpoints**:
  - `GET /api/offers`: Retrieve existing offers.
  - `POST /api/offers/imports`: Bulk import/update offers.
  - `GET /api/offers/{offer}`: Get details for a specific offer.

#### C. Shipping & Tracking (`shipping`, `tracking`)
Updates tracking information and confirms shipment.
- **Endpoints**:
  - `PUT /api/orders/{order_id}/tracking`: Update tracking info for an order.
  - `POST /api/shipments/tracking`: Update tracking for specific shipments.
  - `PUT /api/shipments/ship`: Confirm that an order has been shipped.

#### D. Customer Service (`customer_service`)
Manages threads and messages.
- **Endpoints**:
  - `GET /api/inbox/threads`: Retrieve message threads.
  - `POST /api/inbox/threads/{thread_id}/message`: Send a message to a customer.

#### E. Invoicing & Accounting (`accounting`)
Fetches transaction logs for financial analysis.
- **Endpoints**:
  - `GET /api/invoices`: List accounting documents.
  - `GET /api/sellerpayment/transactions_logs`: Retrieve detailed transaction history.

### 4. Implementation Notes for `bb_modules`
- **Database**: PostgreSQL is used as the central repository.
- **Docker**: Modules run as containerized services.
- **Workflows**: Scripts like `main_acceptance.py` and `main_tracking.py` should be scheduled to call the respective APIs periodically.

--- 
Source URLs:
- Mirakl API Docs: https://developer.mirakl.com/content/product/mmp/rest/seller/openapi3
- GitHub Repo: https://github.com/alwazw/bb_modules
