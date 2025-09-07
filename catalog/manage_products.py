import json
import argparse
import os

# Define the path to the products database file
PRODUCTS_FILE = os.path.join(os.path.dirname(__file__), 'products.json')

def read_products():
    """Reads the product catalog from the JSON file."""
    try:
        with open(PRODUCTS_FILE, 'r') as f:
            content = f.read()
            if not content:
                return []
            return json.loads(content)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        print("Error: Could not decode JSON from products.json. The file might be corrupt.")
        return []

def write_products(products):
    """Writes the product catalog back to the JSON file."""
    with open(PRODUCTS_FILE, 'w') as f:
        json.dump(products, f, indent=2)

def view_products(args):
    """Displays all products in the catalog."""
    products = read_products()
    if not products:
        print("The product catalog is empty.")
        return
    print(json.dumps(products, indent=2))

def add_product(args):
    """Adds a new product or a new variant to an existing product."""
    products = read_products()

    product_id = args.product_id
    sku = args.sku

    # Find if the base product already exists
    product_to_update = next((p for p in products if p.get('base_product', {}).get('product_id') == product_id), None)

    if product_to_update:
        # Product exists, add a new variant
        print(f"Base product '{product_id}' found. Checking for SKU '{sku}'...")
        # Check if SKU already exists in this product's variants
        if any(v.get('sku') == sku for v in product_to_update.get('variants', [])):
            print(f"Error: SKU '{sku}' already exists for product '{product_id}'. SKUs must be unique.")
            return

        variant_attributes = {k: v for k, v in vars(args).items() if k in ['ram', 'storage', 'color', 'processor'] and v is not None}
        new_variant = {
            "sku": sku,
            "attributes": variant_attributes,
            "upc": args.upc
        }
        product_to_update['variants'].append(new_variant)
        print(f"Successfully added new variant '{sku}' to product '{product_id}'.")

    else:
        # Product does not exist, create a new one
        print(f"Base product '{product_id}' not found. Creating a new product entry.")
        if not args.brand or not args.model:
            print("Error: When creating a new product, --brand and --model are required.")
            return

        variant_attributes = {k: v for k, v in vars(args).items() if k in ['ram', 'storage', 'color', 'processor'] and v is not None}
        new_product = {
            "base_product": {
                "product_id": product_id,
                "brand": args.brand,
                "model": args.model,
                "series": args.series,
                "description": args.description
            },
            "variants": [
                {
                    "sku": sku,
                    "attributes": variant_attributes,
                    "upc": args.upc
                }
            ]
        }
        products.append(new_product)
        print(f"Successfully created new product '{product_id}' with variant '{sku}'.")

    write_products(products)

def update_product(args):
    """Updates an existing product in the catalog."""
    # This implementation can be complex. For now, we'll focus on updating a variant's attributes.
    products = read_products()
    sku_to_update = args.sku

    variant_found = False
    for product in products:
        for variant in product.get('variants', []):
            if variant.get('sku') == sku_to_update:
                print(f"Found SKU '{sku_to_update}'. Updating attributes.")
                for key, value in vars(args).items():
                    if key in variant['attributes'] and value is not None:
                        variant['attributes'][key] = value
                variant_found = True
                break
        if variant_found:
            break

    if variant_found:
        write_products(products)
        print(f"Successfully updated attributes for SKU '{sku_to_update}'.")
    else:
        print(f"Error: SKU '{sku_to_update}' not found in the catalog.")

def main():
    """Main function to parse arguments and call the appropriate function."""
    parser = argparse.ArgumentParser(description="Manage the product catalog.")
    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

    # 'view' command
    parser_view = subparsers.add_parser('view', help='View all products in the catalog.')
    parser_view.set_defaults(func=view_products)

    # 'add' command
    parser_add = subparsers.add_parser('add', help='Add a new product or variant.')
    parser_add.add_argument('--product-id', type=str, required=True, help='The unique ID for the base product.')
    parser_add.add_argument('--brand', type=str, help='Brand of the product (required for new products).')
    parser_add.add_argument('--model', type=str, help='Model of the product (required for new products).')
    parser_add.add_argument('--series', type=str, help='Series of the product.')
    parser_add.add_argument('--description', type=str, help='Description of the product.')
    parser_add.add_argument('--sku', type=str, required=True, help='The unique SKU for the variant.')
    parser_add.add_argument('--upc', type=str, help='The UPC for the variant.')
    parser_add.add_argument('--ram', type=str, help='RAM attribute of the variant.')
    parser_add.add_argument('--storage', type=str, help='Storage attribute of the variant.')
    parser_add.add_argument('--color', type=str, help='Color attribute of the variant.')
    parser_add.add_argument('--processor', type=str, help='Processor attribute of the variant.')
    parser_add.set_defaults(func=add_product)

    # 'update' command
    parser_update = subparsers.add_parser('update', help='Update an existing variant\'s attributes.')
    parser_update.add_argument('--sku', type=str, required=True, help='The SKU of the variant to update.')
    parser_update.add_argument('--ram', type=str, help='New RAM value.')
    parser_update.add_argument('--storage', type=str, help='New Storage value.')
    parser_update.add_argument('--color', type=str, help='New Color value.')
    parser_update.add_argument('--processor', type=str, help='New Processor value.')
    parser_update.set_defaults(func=update_product)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
