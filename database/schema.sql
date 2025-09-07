-- Drop tables if they exist to ensure a clean slate on re-initialization
DROP TABLE IF EXISTS order_acceptance_debug_logs;
DROP TABLE IF EXISTS order_acceptance_attempts;
DROP TABLE IF EXISTS order_lines;
DROP TABLE IF EXISTS orders;

-- Main table for storing order information
CREATE TABLE orders (
    order_id VARCHAR(255) PRIMARY KEY,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    raw_order_data JSONB
);

-- Table for storing individual order lines
CREATE TABLE order_lines (
    order_line_id VARCHAR(255) PRIMARY KEY,
    order_id VARCHAR(255) NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    sku VARCHAR(255),
    quantity INTEGER,
    raw_line_data JSONB
);

-- Table to log each attempt to accept an order
CREATE TABLE order_acceptance_attempts (
    attempt_id SERIAL PRIMARY KEY,
    order_id VARCHAR(255) NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) NOT NULL, -- e.g., 'success', 'failure'
    api_response JSONB
);

-- Table for detailed logging of problematic orders that fail repeatedly
CREATE TABLE order_acceptance_debug_logs (
    log_id SERIAL PRIMARY KEY,
    order_id VARCHAR(255) NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    details TEXT,
    raw_request_payload JSONB
);

-- Create an index on order_id in the attempts table for faster lookups
CREATE INDEX idx_order_acceptance_attempts_order_id ON order_acceptance_attempts(order_id);


-- =====================================================================================
-- Schema for Shipping & Tracking Module
-- =====================================================================================

-- Table to store shipment information, linked to an order
CREATE TABLE shipments (
    shipment_id SERIAL PRIMARY KEY,
    order_id VARCHAR(255) NOT NULL UNIQUE REFERENCES orders(order_id) ON DELETE CASCADE,
    tracking_pin VARCHAR(255) UNIQUE,
    status VARCHAR(50) NOT NULL, -- e.g., 'label_created', 'tracking_updated'
    label_pdf_path VARCHAR(1024),
    cp_api_label_url VARCHAR(1024),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table to log all API calls related to a specific shipment
-- A generic table to log all third-party API calls for auditing and debugging
CREATE TABLE api_calls (
    call_id SERIAL PRIMARY KEY,
    service VARCHAR(50) NOT NULL, -- e.g., 'BestBuy', 'CanadaPost'
    endpoint VARCHAR(255) NOT NULL, -- e.g., 'CreateShipment', 'UpdateTracking'
    related_id VARCHAR(255), -- e.g., an order_id or shipment_id
    request_payload JSONB,
    response_body TEXT, -- Using TEXT to accommodate both JSON and XML responses
    status_code INTEGER,
    is_success BOOLEAN NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for faster lookups on foreign keys and common query fields
CREATE INDEX idx_shipments_order_id ON shipments(order_id);
CREATE INDEX idx_api_calls_related_id ON api_calls(related_id);
CREATE INDEX idx_api_calls_service ON api_calls(service);


-- Create a function to automatically update the updated_at timestamp
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create a trigger to call the function before any update on the orders table
CREATE TRIGGER set_timestamp
BEFORE UPDATE ON orders
FOR EACH ROW
EXECUTE PROCEDURE trigger_set_timestamp();
