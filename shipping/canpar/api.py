import os
import zeep
from zeep.helpers import serialize_object
from datetime import datetime

# --- Configuration ---
# Use a local WSDL file for reliability and to avoid network requests for the definition.
WSDL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'CanshipBusinessService.wsdl')

# It's recommended to use the sandbox for development and testing.
# The endpoint can be overridden when creating the client.
CANPAR_SOAP_ENDPOINT = "https://sandbox.canpar.com/canshipws/services/CanshipBusinessService"

# --- Credentials ---
# IMPORTANT: These should not be hardcoded. Use environment variables, a config file,
# or a secure secret management system.
CANPAR_USER_ID = "wafic.alwazzan@visionvation.com"
CANPAR_PASSWORD = "Ground291!"
CANPAR_SHIPPER_NUM = "46000041"


def get_canpar_client():
    """
    Initializes and returns a zeep SOAP client for the Canpar API.
    """
    # For production, you might want to use a different endpoint.
    # The WSDL defines several, including HTTPS endpoints.
    # Example: "https://canship.canpar.com/canshipws/services/CanshipBusinessService.CanshipBusinessServiceHttpsSoap12Endpoint/"
    client = zeep.Client(WSDL_PATH, service_name='CanshipBusinessService')
    return client


def create_shipment(client, order_details, num_packages=1):
    """
    Creates a shipment with Canpar using the provided order details.

    Args:
        client: The zeep SOAP client.
        order_details: A dictionary containing the order information.
        num_packages: The number of packages (labels) to create for this shipment.

    Returns:
        A dictionary containing the result of the shipment creation process.
    """
    raw_order = order_details['raw_order_data']
    shipping_address = raw_order['customer']['shipping_address']

    # Create a list of package payloads
    packages_payload = []
    for i in range(num_packages):
        packages_payload.append({
            'reported_weight': 1.8,  # Example weight, can be parameterized later
            'length': 35,
            'width': 25,
            'height': 5,
            'reference': f"{raw_order['order_id']}-P{i+1}", # Add a package identifier to the reference
        })

    shipment_payload = {
        'password': CANPAR_PASSWORD,
        'user_id': CANPAR_USER_ID,
        'shipment': {
            'shipper_num': CANPAR_SHIPPER_NUM,
            'shipping_date': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            'service_type': '1',  # '1' for Ground
            'description': f"Order {raw_order['order_id']}",
            'instruction': 'Deliver to front door.',
            'delivery_address': {
                'name': f"{shipping_address['firstname']} {shipping_address['lastname']}",
                'address_line_1': shipping_address['street_1'],
                'city': shipping_address['city'],
                'province': shipping_address['state'],
                'postal_code': shipping_address['zip_code'].replace(" ", ""),
                'country': 'CA',
                'phone': shipping_address.get('phone', '1112223333'),
            },
            'pickup_address': {
                'name': 'VISIONVATION INC.',
                'address_line_1': '133 Rock Fern Way',
                'city': 'North York',
                'province': 'ON',
                'postal_code': 'M2J4N3',
                'country': 'CA',
                'phone': '6474440848',
            },
            'packages': packages_payload,
            'reported_weight_unit': 'K',
            'dimention_unit': 'C',
        }
    }

    try:
        # The service name is 'CanshipBusinessService' and the port is 'CanshipBusinessServiceHttpsSoap12Endpoint' in the WSDL
        # Zeep is smart enough to find the correct service and port if they are not ambiguous.
        # We can call the 'processShipment' operation directly.
        response = client.service.processShipment(request=shipment_payload)

        # Zeep converts the SOAP response into Python objects.
        # We can use serialize_object to convert it to a dictionary for easier handling.
        response_dict = serialize_object(response)

        if response_dict and response_dict.get('processShipmentResult'):
            result = response_dict['processShipmentResult']
            if result.get('shipment') and result['shipment'].get('packages'):
                packages_info = []
                # The response may return a single package as a dict or multiple as a list
                packages = result['shipment']['packages']
                if not isinstance(packages, list):
                    packages = [packages]

                for pkg in packages:
                    packages_info.append({
                        'tracking_number': pkg.get('barcode'),
                        'package_reference': pkg.get('reference'),
                    })
                return {
                    'success': True,
                    'shipment_id': result['shipment']['id'],
                    'packages': packages_info,
                    'raw_response': response_dict,
                }

        # Handle errors returned by the API
        error_message = response_dict.get('error') or response_dict.get('processShipmentResult', {}).get('errors')
        if isinstance(error_message, list):
            error_message = ', '.join(error_message)
        elif not error_message:
            error_message = 'Unknown error during shipment processing.'
        return {'success': False, 'error': error_message, 'raw_response': response_dict}

    except zeep.exceptions.Fault as e:
        print(f"SOAP Fault: {e}")
        return {'success': False, 'error': str(e)}
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {'success': False, 'error': str(e)}


def get_shipping_label(client, shipment_id, thermal=False):
    """
    Retrieves a shipping label from Canpar for a given shipment ID.
    The WSDL indicates a `getLabels` and `getLabelsAdvancedV2` operation.
    `getLabels` seems to return a base64 encoded string.
    """
    label_request = {
        'password': CANPAR_PASSWORD,
        'user_id': CANPAR_USER_ID,
        'id': shipment_id,
        'thermal': thermal,
    }
    try:
        response = client.service.getLabels(request=label_request)
        response_dict = serialize_object(response)
        if response_dict and response_dict.get('labels'):
            return {'success': True, 'labels': response_dict['labels']}
        error_message = response_dict.get('error', 'Failed to retrieve labels.')
        return {'success': False, 'error': error_message}
    except zeep.exceptions.Fault as e:
        print(f"SOAP Fault while getting label: {e}")
        return {'success': False, 'error': str(e)}


def track_shipment(client, tracking_number):
    """
    Tracks a shipment with Canpar.
    Note: The provided WSDL `CanshipBusinessService` seems focused on shipment creation
    and management, not public tracking. A different service/API (like `TrackingService`)
    is usually used for this. This function is a placeholder.
    """
    # This will likely require a different WSDL or API endpoint for tracking.
    # For now, we will search for a shipment by its barcode (tracking number).
    tracking_request = {
        'password': CANPAR_PASSWORD,
        'user_id': CANPAR_USER_ID,
        'shipper_num': CANPAR_SHIPPER_NUM,
        'barcode': tracking_number,
    }
    try:
        # Using 'searchShipmentsByBarcode' as a proxy for tracking
        response = client.service.searchShipmentsByBarcode(request=tracking_request)
        response_dict = serialize_object(response)
        if response_dict and response_dict.get('shipment'):
            return {'success': True, 'shipments': response_dict['shipment']}
        error_message = response_dict.get('error', 'Failed to track shipment.')
        return {'success': False, 'error': error_message}
    except zeep.exceptions.Fault as e:
        print(f"SOAP Fault while tracking: {e}")
        return {'success': False, 'error': str(e)}