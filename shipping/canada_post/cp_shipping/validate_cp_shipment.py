import os
import sys
import requests
import base64

# Add project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, '..', '..', '..'))
from common.utils import get_canada_post_credentials


def get_tracking_summary(api_user, api_password, tracking_pin):
    """ Calls the Get Tracking Summary API to validate the tracking PIN. """
    if not tracking_pin:
        print("ERROR: No tracking PIN provided for validation.")
        return False

    # Use the production URL for tracking
    tracking_url = f"https://soa-gw.canadapost.ca/vis/track/pin/{tracking_pin}/summary"

    auth_string = f"{api_user}:{api_password}"
    auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')

    headers = {
        'Accept': 'application/vnd.cpc.track-v2+xml', # Note: different Accept header for tracking
        'Authorization': f'Basic {auth_b64}'
    }

    print(f"INFO: Validating tracking PIN {tracking_pin} with URL: {tracking_url}...")
    try:
        response = requests.get(tracking_url, headers=headers)
        response.raise_for_status()
        print(f"SUCCESS: Tracking PIN {tracking_pin} is valid and recognized by Canada Post.")
        print("Tracking Summary:", response.text)
        return True
    except requests.exceptions.RequestException as e:
        print(f"CRITICAL: Tracking PIN {tracking_pin} could not be validated.")
        print(f"ERROR: Tracking validation API request failed: {e}")
        if e.response is not None:
            print("Response Body:", e.response.text)
        return False

def get_shipment_details(api_user, api_password, shipment_details_url):
    """ Calls the Get Shipment Details API to validate the shipment and returns the response. """
    if not shipment_details_url:
        print("ERROR: No shipment details URL provided for validation.")
        return None

    auth_string = f"{api_user}:{api_password}"
    auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')

    headers = {
        'Accept': 'application/vnd.cpc.shipment-v8+xml',
        'Authorization': f'Basic {auth_b64}'
    }

    print(f"INFO: Getting shipment details with URL: {shipment_details_url}...")
    try:
        response = requests.get(shipment_details_url, headers=headers)
        response.raise_for_status()
        print("SUCCESS: Get Shipment Details API call was successful.")
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Get Shipment Details API request failed: {e}")
        if e.response is not None:
            print("Response Body:", e.response.text)
        return None

def main():
    """ Main function to be called by orchestrator. """
    print("INFO: validate_cp_shipment.py executed as a standalone script.")
    pass

if __name__ == '__main__':
    main()
