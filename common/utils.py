import os

SECRETS_FILE = os.path.join(os.path.dirname(__file__), '..', 'secrets.txt')

def get_secret(key_name):
    """ Reads a specific key from the secrets.txt file. """
    try:
        with open(SECRETS_FILE, 'r') as f:
            for line in f:
                if line.startswith(key_name + '='):
                    secret_value = line.strip().split('=', 1)[1]
                    return secret_value
        print(f"ERROR: Key '{key_name}' not found in {SECRETS_FILE}")
        return None
    except FileNotFoundError:
        print(f"ERROR: {SECRETS_FILE} not found.")
        return None

def get_best_buy_api_key():
    """ Helper function to get the Best Buy API key. """
    return get_secret('BEST_BUY_API_KEY')

def get_canada_post_credentials():
    """ Helper function to get all Canada Post credentials. """
    user = get_secret('CANADA_POST_API_USER')
    password = get_secret('CANADA_POST_API_PASSWORD')
    customer_number = get_secret('CANADA_POST_CUSTOMER_NUMBER')
    paid_by = get_secret('CANADA_POST_PAID_BY_CUSTOMER')
    contract_id = get_secret('CANADA_POST_CONTRACT_ID')

    if all([user, password, customer_number, paid_by, contract_id]):
        print("SUCCESS: All Canada Post credentials loaded.")
        return user, password, customer_number, paid_by, contract_id
    else:
        print("ERROR: Could not find all required Canada Post credentials in secrets.txt")
        return None, None, None, None, None
