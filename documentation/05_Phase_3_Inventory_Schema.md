# Phase 3: Inventory Management Schema Design

This document outlines the database schema designed to support the sophisticated inventory management capabilities envisioned for Phase 3. The goal is to create a flexible and powerful data model that can accurately represent the project's complex product structure, where a single base product can be sold in multiple configurations and under various marketing SKUs.

## 1. Core Concepts

The inventory system is designed around a few core concepts that work together to create a "Bill of Materials" (BOM) for any sellable product.

-   **Base Products**: A "base product" is a core laptop model, stripped of its configurable parts (e.g., "Dell Inspiron 15"). It serves as the chassis or foundation for different configurations.

-   **Components**: "Components" are the individual parts that can be used to build a final product. This includes configurable hardware like RAM and SSDs, as well as bundled accessories like backpacks or mice. Each component is a distinct, trackable item.

-   **Product Variants**: A "product variant" is the canonical, internal representation of a *specific configuration* of a base product (e.g., "Dell Inspiron 15 with 32GB RAM and a 1TB SSD"). This is the "unique ID" that serves as the true identifier for a sellable product. It is the central point that links a base product to its components.

-   **Shop SKUs**: A "shop SKU" is a public-facing SKU used on the Best Buy marketplace. Multiple shop SKUs can map to a single internal product variant. This is a powerful feature that allows for marketing strategies like A/B price testing, promotional bundles, or different product titles for the same physical item, all without corrupting the internal inventory data.

## 2. Database Schema

The following tables were added to `database/schema.sql` to model this system.

### `components` Table
-   **Purpose**: Stores a master list of all individual, trackable components.
-   **Columns**:
    -   `component_id` (PK): A unique ID for the component.
    -   `name` (VARCHAR): A human-readable name (e.g., "16GB DDR4 3200MHz RAM Stick").
    -   `type` (VARCHAR): A category for the component (e.g., `'RAM'`, `'SSD'`, `'Accessory'`).
    -   `specs` (JSONB): A flexible field to store detailed specifications (e.g., `{"capacity_gb": 16, "speed": "3200MHz"}`).

### `base_products` Table
-   **Purpose**: Stores the core laptop models.
-   **Columns**:
    -   `product_id` (PK): A unique ID for the base model.
    -   `model_name` (VARCHAR): The name of the model (e.g., "HP Spectre x360 14").
    -   `brand` (VARCHAR): The brand of the product (e.g., "HP").

### `product_variants` Table
-   **Purpose**: The heart of the inventory system. Defines a specific, unique configuration of a product.
-   **Columns**:
    -   `variant_id` (PK): The unique internal ID for this configuration.
    -   `base_product_id` (FK): Links to the `base_products` table.
    -   `internal_sku` (VARCHAR): A unique, human-readable internal SKU that can be used to identify this exact configuration (e.g., `INSPIRON-15-32-1000`).
    -   `description` (TEXT): A text description of the variant.

### `variant_components` Table
-   **Purpose**: A many-to-many join table that defines the "Bill of Materials" for each product variant. It links a variant to the specific components and quantities that make it up.
-   **Columns**:
    -   `variant_id` (FK): Links to the `product_variants` table.
    -   `component_id` (FK): Links to the `components` table.
    -   `quantity` (INTEGER): The number of a specific component required for the variant (e.g., 2 for two 8GB RAM sticks).

### `shop_sku_map` Table
-   **Purpose**: Maps the public-facing Best Buy SKUs to our internal product variants. This is the key to decoupling marketing listings from internal inventory management.
-   **Columns**:
    -   `shop_sku` (PK): The SKU used on the Best Buy marketplace.
    -   `variant_id` (FK): The internal product variant this SKU represents.
    -   `listing_title` (TEXT): The public title of the listing on Best Buy.
    -   `is_active` (BOOLEAN): A flag to easily enable or disable mappings.

## 3. Example Workflow

Here's how the system would use this schema to determine the components needed for an order:

1.  A new order arrives from Best Buy with `shop_sku = 'DELL-PROMO-A'`.
2.  The system queries the `shop_sku_map` table to find that `'DELL-PROMO-A'` maps to `variant_id = 5`.
3.  The system then queries the `variant_components` table for all records where `variant_id = 5`. This returns the "Bill of Materials" for the order.
4.  The result might be:
    -   Component ID 1 (Inspiron 15 Base Unit), Quantity 1
    -   Component ID 15 (16GB RAM Stick), Quantity 2
    -   Component ID 27 (1TB NVMe SSD), Quantity 1
5.  This list of required components can then be used to decrement inventory counts and will eventually feed into the "Work Order" module for the fulfillment team to assemble the physical product.
