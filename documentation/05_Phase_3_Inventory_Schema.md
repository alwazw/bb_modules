# Phase 3: Inventory Management Schema Design

This document outlines the database schema designed to support the sophisticated inventory management capabilities envisioned for Phase 3. The goal is to create a flexible and powerful data model that can accurately represent the project's complex product structure.

## 1. Core Concepts

The inventory system is designed around a few core concepts:

-   **Base Products:** A "base product" is a core laptop model, stripped of its configurable parts (e.g., "Dell Inspiron 15").
-   **Components:** "Components" are the individual parts that can be used to build a final product. This includes configurable hardware like RAM and SSDs, as well as bundled accessories like backpacks or mice.
-   **Product Variants:** A "product variant" is the canonical, internal representation of a *specific configuration* of a base product (e.g., "Dell Inspiron 15 with 32GB RAM and a 1TB SSD"). This is the "unique ID" that serves as the true identifier for a sellable product.
-   **Shop SKUs:** A "shop SKU" is a public-facing SKU used on the Best Buy marketplace. Multiple shop SKUs can map to a single internal product variant, allowing for marketing strategies like A/B price testing without corrupting the internal inventory data.

## 2. Database Schema

The following tables were added to `database/schema.sql` to model this system.

### `components` Table
-   **Purpose:** Stores a master list of all individual, trackable components.
-   **Columns:**
    -   `component_id` (PK): A unique ID for the component.
    -   `name`: A human-readable name (e.g., "16GB DDR4 3200MHz RAM Stick").
    -   `type`: A category for the component (e.g., `'RAM'`, `'SSD'`, `'Accessory'`).
    -   `specs` (JSONB): A flexible field to store detailed specifications (e.g., `{"capacity_gb": 16, "speed": "3200MHz"}`).

### `base_products` Table
-   **Purpose:** Stores the core laptop models.
-   **Columns:**
    -   `product_id` (PK): A unique ID for the base model.
    -   `model_name`: The name of the model (e.g., "HP Spectre x360 14").
    -   `brand`: The brand of the product (e.g., "HP").

### `product_variants` Table
-   **Purpose:** The heart of the inventory system. Defines a specific, unique configuration of a product.
-   **Columns:**
    -   `variant_id` (PK): The unique internal ID for this configuration.
    -   `base_product_id` (FK): Links to the base product this variant is derived from.
    -   `internal_sku`: A unique, human-readable internal SKU that can be used to identify this exact configuration (e.g., `INSPIRON-15-32-1000`).
    -   `description`: A text description of the variant.

### `variant_components` Table
-   **Purpose:** A many-to-many join table that defines the "Bill of Materials" for each product variant.
-   **Columns:**
    -   `variant_id` (FK): Links to the `product_variants` table.
    -   `component_id` (FK): Links to the `components` table.
    -   `quantity`: The number of a specific component required for the variant (e.g., 2x 8GB RAM sticks).

### `shop_sku_map` Table
-   **Purpose:** Maps the public-facing Best Buy SKUs to our internal product variants. This is the key to decoupling marketing listings from internal inventory.
-   **Columns:**
    -   `shop_sku` (PK): The SKU used on the Best Buy marketplace.
    -   `variant_id` (FK): The internal product variant this SKU represents.
    -   `listing_title`: The public title of the listing on Best Buy.
    -   `is_active`: A boolean to easily enable or disable mappings.

## 3. Example Workflow

1.  A new order arrives with `shop_sku = 'DELL-PROMO-A'`.
2.  The system queries the `shop_sku_map` table to find that `'DELL-PROMO-A'` maps to `variant_id = 5`.
3.  The system then queries the `variant_components` table for `variant_id = 5` to get the list of all components needed to fulfill the order (e.g., 1x Base Product "Inspiron 15", 2x Component "16GB RAM", 1x Component "1TB SSD").
4.  This information can then be used to decrement inventory counts and will eventually feed into the "Work Order" module for fulfillment.
