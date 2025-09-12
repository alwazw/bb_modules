# Catalogue Management Module

This module is the heart of your product inventory. It provides the tools and data storage for your entire product catalogue, with a focus on handling products with multiple variants (e.g., laptops with different RAM, storage, or color configurations).

## File Structure

*   `manage_products.py`: A command-line script used to add, update, and view products in your catalogue. This is the primary tool you will use to interact with your product data.
*   `products.json`: The database file for your catalogue. It is a simple JSON file that stores a list of all your products and their variants.
*   `product_schema.json`: A file that defines the expected data structure for an entry in `products.json`. This is for reference and potential validation in the future.

## How to Use `manage_products.py`

You can manage your entire product catalogue using this script from your terminal. Below are the available commands and how to use them.

### 1. View All Products

To see the complete contents of your `products.json` file in a nicely formatted way, use the `view` command.

```bash
python3 catalogue/manage_products.py view
```

### 2. Add a New Product

To add a brand new product to your catalogue, use the `add` command. You must provide the base product information (like `product-id`, `brand`, and `model`) as well as the details for its first variant.

**Example:**
```bash
python3 catalogue/manage_products.py add \
--product-id "super-laptop-x1" \
--brand "FutureBrand" \
--model "Super Laptop X1" \
--series "Pro" \
--description "The latest and greatest professional laptop." \
--sku "FB-SLX1-16-512-GR" \
--upc "123456789012" \
--ram "16GB" \
--storage "512GB SSD" \
--color "Galactic Gray"
```
This command will create a new base product called "Super Laptop X1" and add its first variant with the SKU `FB-SLX1-16-512-GR`.

### 3. Add a New Variant to an Existing Product

If a product already exists, you can use the same `add` command to add more variants to it. Just use the same `product-id` and provide the details for the new variant.

**Example:**
Let's add a 32GB RAM version to the laptop we created above.
```bash
python3 catalogue/manage_products.py add \
--product-id "super-laptop-x1" \
--sku "FB-SLX1-32-1024-GR" \
--upc "123456789013" \
--ram "32GB" \
--storage "1TB SSD" \
--color "Galactic Gray"
```
This will find the product with the ID `super-laptop-x1` and append this new variant to its list of variants.

### 4. Update an Existing Variant

To modify the attributes of a specific variant, use the `update` command. You must identify the variant by its unique `sku`.

**Example:**
Let's say we made a mistake and the 16GB model actually has a different color.
```bash
python3 catalogue/manage_products.py update \
--sku "FB-SLX1-16-512-GR" \
--color "Cosmic Silver"
```
This will find the variant with the matching SKU and update its `color` attribute. You can update any of the variant attributes (`ram`, `storage`, `color`, `processor`) in this way.
