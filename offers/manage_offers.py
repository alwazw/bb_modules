import json
import argparse
import os

# Define paths to the data files
OFFERS_FILE = os.path.join(os.path.dirname(__file__), 'offers.json')
PRODUCTS_FILE = os.path.join(os.path.dirname(__file__), '..', 'catalogue', 'products.json')

def read_json_file(filepath):
    """Reads a JSON file and returns its content."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def write_json_file(filepath, data):
    """Writes data to a JSON file."""
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def find_sku_in_catalogue(sku):
    """Checks if a SKU exists in the product catalogue."""
    products_data = read_json_file(PRODUCTS_FILE)
    for product in products_data:
        for variant in product.get('variants', []):
            if variant.get('sku') == sku:
                return True
    return False

def create_offer(args):
    """Creates or updates an offer for a given SKU."""
    sku = args.sku
    price = args.price
    stock = args.stock

    if not find_sku_in_catalogue(sku):
        print(f"Error: SKU '{sku}' not found in the product catalogue. Please add the product first.")
        return

    offers = read_json_file(OFFERS_FILE)

    # Check if an offer for this SKU already exists
    offer_found = False
    for offer in offers:
        if offer.get('sku') == sku:
            offer['price'] = price
            offer['stock'] = stock
            offer_found = True
            break

    if not offer_found:
        offers.append({
            "sku": sku,
            "price": price,
            "stock": stock
        })

    write_json_file(OFFERS_FILE, offers)
    print(f"Successfully created/updated offer for SKU: {sku}, Price: ${price}, Stock: {stock}")

def view_offers(args):
    """Displays all current offers."""
    offers = read_json_file(OFFERS_FILE)
    if not offers:
        print("There are no current offers.")
        return
    print(json.dumps(offers, indent=2))

def main():
    """Main function to parse arguments and call the appropriate function."""
    parser = argparse.ArgumentParser(description="Manage sales offers.")
    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

    # 'create' command
    parser_create = subparsers.add_parser('create', help='Create or update a sales offer.')
    parser_create.add_argument('--sku', type=str, required=True, help='The SKU of the product variant.')
    parser_create.add_argument('--price', type=float, required=True, help='The price of the offer.')
    parser_create.add_argument('--stock', type=int, required=True, help='The available stock for the offer.')
    parser_create.set_defaults(func=create_offer)

    # 'view' command
    parser_view = subparsers.add_parser('view', help='View all current offers.')
    parser_view.set_defaults(func=view_offers)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
