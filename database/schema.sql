-- Drop tables in reverse order of creation to respect foreign key constraints.
DROP TABLE IF EXISTS shop_sku_map;
DROP TABLE IF EXISTS variant_components;
DROP TABLE IF EXISTS product_variants;
DROP TABLE IF EXISTS base_products;
DROP TABLE IF EXISTS components;
DROP TABLE IF EXISTS process_failures;
DROP TABLE IF EXISTS api_calls;
DROP TABLE IF EXISTS shipments;
DROP TABLE IF EXISTS order_status_history;
DROP TABLE IF EXISTS order_lines;
DROP TABLE IF EXISTS orders;

-- =====================================================================================
-- Core Order Processing Schema
-- =====================================================================================

-- Main table for storing order information. This table contains data that is
-- unlikely to change, like the customer info and the items ordered.
CREATE TABLE orders (
    order_id VARCHAR(255) PRIMARY KEY,
    -- The raw JSON data for the order. Storing this allows us to re-process an
    -- order or audit the original data without needing to call the API again.
    raw_order_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for storing individual order lines.
CREATE TABLE order_lines (
    order_line_id VARCHAR(255) PRIMARY KEY,
    order_id VARCHAR(255) NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    sku VARCHAR(255),
    quantity INTEGER,
    raw_line_data JSONB
);

-- This table provides a complete, timestamped history of an order's state.
-- Instead of a single 'status' column, we append a new row here every time the
-- order moves to a new step in the process. This is the source of truth for an
-- order's current status and provides a powerful audit trail.
CREATE TABLE order_status_history (
    history_id SERIAL PRIMARY KEY,
    order_id VARCHAR(255) NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL, -- e.g., 'pending_acceptance', 'accepted', 'label_created', 'shipped'
    notes TEXT, -- Optional context for the status change
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table to store shipment information, created when the shipping process begins.
CREATE TABLE shipments (
    shipment_id SERIAL PRIMARY KEY,
    -- UNIQUE constraint ensures one shipment record per order, preventing duplicate labels.
    order_id VARCHAR(255) NOT NULL UNIQUE REFERENCES orders(order_id) ON DELETE CASCADE,
    tracking_pin VARCHAR(255) UNIQUE,
    label_pdf_path VARCHAR(1024),
    cp_api_label_url VARCHAR(1024),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================================
-- Auditing and Error Logging Schema
-- =====================================================================================

-- A generic table to log all third-party API calls for auditing and debugging.
CREATE TABLE api_calls (
    call_id SERIAL PRIMARY KEY,
    service VARCHAR(50) NOT NULL, -- e.g., 'BestBuy', 'CanadaPost'
    endpoint VARCHAR(255) NOT NULL, -- e.g., 'CreateShipment', 'UpdateTracking'
    related_id VARCHAR(255), -- e.g., an order_id
    request_payload JSONB,
    response_body TEXT, -- Using TEXT to accommodate both JSON and XML responses
    status_code INTEGER,
    is_success BOOLEAN NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- A generic table to log critical, unrecoverable failures that require manual intervention.
CREATE TABLE process_failures (
    failure_id SERIAL PRIMARY KEY,
    related_id VARCHAR(255) NOT NULL, -- e.g., an order_id
    process_name VARCHAR(100) NOT NULL, -- e.g., 'OrderAcceptance', 'ShippingLabelCreation'
    details TEXT, -- A human-readable description of the error
    payload JSONB, -- The data object that was being processed when the failure occurred
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================================
-- Inventory Management Schema (Phase 3)
-- =====================================================================================

-- Stores individual, sellable/trackable components (RAM, SSDs, accessories, etc.).
CREATE TABLE components (
    component_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL, -- e.g., 'RAM', 'SSD', 'Accessory'
    specs JSONB -- e.g., {"capacity_gb": 16, "speed": "DDR4-3200"}
);

-- Stores the base laptop models, stripped of their configurable components.
CREATE TABLE base_products (
    product_id SERIAL PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    brand VARCHAR(100)
);

-- This is the canonical representation of a specific product configuration.
-- This is the "unique ID" that groups together multiple shop SKUs.
CREATE TABLE product_variants (
    variant_id SERIAL PRIMARY KEY,
    base_product_id INTEGER NOT NULL REFERENCES base_products(product_id),
    -- An internal, human-readable SKU for this specific variant configuration.
    internal_sku VARCHAR(255) UNIQUE NOT NULL,
    description TEXT
);

-- A join table defining the Bill of Materials for each product variant.
-- It links a variant to the specific components and quantities that make it up.
CREATE TABLE variant_components (
    variant_id INTEGER NOT NULL REFERENCES product_variants(variant_id) ON DELETE CASCADE,
    component_id INTEGER NOT NULL REFERENCES components(component_id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (variant_id, component_id)
);

-- This table maps a marketplace-facing "shop SKU" back to our internal, canonical product variant.
-- This allows for multiple listings (e.g., for A/B testing) to resolve to a single internal product.
CREATE TABLE shop_sku_map (
    shop_sku VARCHAR(255) PRIMARY KEY,
    variant_id INTEGER NOT NULL REFERENCES product_variants(variant_id),
    listing_title TEXT,
    is_active BOOLEAN DEFAULT true
);

-- =====================================================================================
-- Indexes and Triggers
-- =====================================================================================

-- Indexes for common query patterns and foreign keys.
CREATE INDEX idx_order_status_history_order_id ON order_status_history(order_id);
CREATE INDEX idx_shipments_order_id ON shipments(order_id);
CREATE INDEX idx_api_calls_related_id ON api_calls(related_id);
CREATE INDEX idx_process_failures_related_id ON process_failures(related_id);
CREATE INDEX idx_shop_sku_map_variant_id ON shop_sku_map(variant_id);

-- A trigger to automatically update the 'updated_at' timestamp on the orders table.
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_timestamp
BEFORE UPDATE ON orders
FOR EACH ROW
EXECUTE PROCEDURE trigger_set_timestamp();