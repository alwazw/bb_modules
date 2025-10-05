import os
import zeep
from zeep.transports import Transport

# It's a good practice to use environment variables for credentials and endpoints.
# For now, we'll use placeholders.
CANPAR_API_USER = os.getenv("CANPAR_API_USER", "test_user")
CANPAR_API_PASSWORD = os.getenv("CANPAR_API_PASSWORD", "test_password")
CANPAR_SHIPPER_NUM = os.getenv("CANPAR_SHIPPER_NUM", "your_shipper_num")

BUSINESS_SERVICE_WSDL = "https://canship.canpar.com/canshipws/services/CanshipBusinessService?wsdl"
RATING_SERVICE_WSDL = "https://canship.canpar.com/canshipws/services/CanparRatingService?wsdl"
ADDONS_SERVICE_WSDL = "https://canship.canpar.com/canshipws/services/CanparAddonsService?wsdl"

def get_business_service_client():
    """Returns a zeep client for the Canpar Business Service."""
    # In a real-world scenario, you might want to handle session management
    # and other transport configurations.
    transport = Transport(timeout=10)
    client = zeep.Client(wsdl=BUSINESS_SERVICE_WSDL, transport=transport)
    return client

from datetime import datetime

CANPAR_DTO_NAMESPACE = '{http://dto.canshipws.canpar.com/xsd}'
CANPAR_WS_DTO_NAMESPACE = '{http://ws.dto.canshipws.canpar.com/xsd}'

def create_shipment(order_details):
    """
    Creates a shipment in Canpar and returns the shipping label.
    :param order_details: A dictionary containing the necessary information for the shipment.
    :return: A dictionary with the shipping_id and the PDF label data, or an error dictionary.
    """
    client = get_business_service_client()

    # Get type constructors from the client using the explicit namespace
    Address = client.get_type(f'{CANPAR_DTO_NAMESPACE}Address')
    Package = client.get_type(f'{CANPAR_DTO_NAMESPACE}Package')
    Shipment = client.get_type(f'{CANPAR_DTO_NAMESPACE}Shipment')
    ProcessShipmentRq = client.get_type(f'{CANPAR_WS_DTO_NAMESPACE}ProcessShipmentRq')

    # Create the Address object for the delivery address
    delivery_address = Address(
        name=order_details.get('delivery_name'),
        attention=order_details.get('delivery_attention'),
        address_line_1=order_details.get('delivery_address_1'),
        city=order_details.get('delivery_city'),
        province=order_details.get('delivery_province'),
        postal_code=order_details.get('delivery_postal_code'),
        country="CA",
        phone=order_details.get('delivery_phone'),
        email=order_details.get('delivery_email')
    )

    # Create the Address object for the pickup address
    pickup_address = Address(
        name="VISIONVATION INC.", address_line_1="133 ROCK FERN WAY", city="NORTH YORK",
        province="ON", postal_code="M2J4N3", country="CA", phone="6474440848"
    )

    # Create the Package object(s)
    packages = [
        Package(
            reported_weight=order_details.get('weight', 2), length=order_details.get('length', 14),
            width=order_details.get('width', 10), height=order_details.get('height', 2),
            declared_value=order_details.get('declared_value', 0)
        )
    ]

    # Create the main Shipment object
    shipment = Shipment(
        shipper_num=CANPAR_SHIPPER_NUM, shipping_date=datetime.now(), service_type="1",
        delivery_address=delivery_address, pickup_address=pickup_address, packages=packages,
        order_id=order_details.get('order_id'), dimention_unit='I', reported_weight_unit='L',
        nsr=True, send_email_to_delivery=True
    )

    # Create the request object that wraps the shipment and credentials
    request = ProcessShipmentRq(
        user_id=CANPAR_API_USER,
        password=CANPAR_API_PASSWORD,
        shipment=shipment
    )

    try:
        # NOTE: The actual API call is commented out because we are using placeholder credentials.
        # In a real environment with valid credentials, you would uncomment this line.
        # response = client.service.processShipment(request=request)

        # This is a mock response to simulate a successful API call for development purposes.
        print(f"MOCKING API CALL for order: {order_details.get('order_id')}")
        mock_response = {
            'return': {
                'error': None,
                'shipment': {
                    'id': 12345,
                    'order_id': order_details.get('order_id'),
                    'packages': [{
                        'barcode': f"D{order_details.get('order_id')}001",
                        'label': 'TVRoaXMgaXMgYSB0ZXN0IFBERiBmaWxlLg==' # "This is a test PDF file." in base64
                    }]
                }
            }
        }

        if mock_response['return']['error']:
            return {'success': False, 'error': mock_response['return']['error']}

        result_shipment = mock_response['return']['shipment']
        shipping_id = result_shipment['packages'][0]['barcode']
        pdf_label = result_shipment['packages'][0]['label']

        return {'success': True, 'shipping_id': shipping_id, 'pdf_label': pdf_label, 'raw_response': mock_response}

    except zeep.exceptions.Fault as e:
        return {'success': False, 'error': str(e)}
    except Exception as e:
        return {'success': False, 'error': f"An unexpected error occurred: {str(e)}"}

if __name__ == '__main__':
    # Example usage:
    mock_order = {
        'order_id': '12345-ABC',
        'shipping_date': '20251001',
        'delivery_name': 'John Doe',
        'delivery_attention': 'IT Department',
        'delivery_address_1': '123 Main St',
        'delivery_city': 'Toronto',
        'delivery_province': 'ON',
        'delivery_postal_code': 'M5V 2T6',
        'delivery_phone': '4165551234',
        'weight': 5,
    }
    result = create_shipment(mock_order)
    print(result)