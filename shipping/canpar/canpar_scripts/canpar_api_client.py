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

def create_shipment(order_details):
    """
    Creates a shipment in Canpar and returns the shipping label.
    :param order_details: A dictionary containing the necessary information for the shipment.
    :return: A dictionary with the shipping_id and the PDF label data, or an error dictionary.
    """
    client = get_business_service_client()

    # Get the factory for creating complex types
    factory = client.type_factory('ns0')

    # Create the Address object for the delivery address
    delivery_address = factory.Address(
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

    # Create the Address object for the pickup address (using hardcoded values for now)
    pickup_address = factory.Address(
        name="VISIONVATION INC.",
        address_line_1="133 ROCK FERN WAY",
        city="NORTH YORK",
        province="ON",
        postal_code="M2J4N3",
        country="CA",
        phone="6474440848"
    )

    # Create the Package object(s)
    packages = [
        factory.Package(
            reported_weight=order_details.get('weight', 2),
            length=order_details.get('length', 14),
            width=order_details.get('width', 10),
            height=order_details.get('height', 2),
            declared_value=order_details.get('declared_value', 0)
        )
    ]

    # Create the main Shipment object
    shipment = factory.Shipment(
        shipper_num=CANPAR_SHIPPER_NUM,
        shipping_date=datetime.now(),
        service_type="1",  # Ground service
        delivery_address=delivery_address,
        pickup_address=pickup_address,
        packages=packages,
        reference=order_details.get('order_id'),
        dimention_unit='I', # Inches
        reported_weight_unit='L', # Pounds
        nsr=True, # No signature required
        send_email_to_delivery=True
    )

    try:
        # The actual API call to Canpar.
        # This will be mocked during tests.
        response = client.service.processShipment(user_id=CANPAR_API_USER, password=CANPAR_API_PASSWORD, shipment=shipment)

        if response['return']['error']:
            return {'success': False, 'error': response['return']['error']}

        result_shipment = response['return']['shipment']
        # The barcode is the tracking number for Canpar.
        shipping_id = result_shipment['packages'][0]['barcode']
        # The label is returned as base64 encoded data.
        pdf_label = result_shipment['packages'][0]['label']

        return {'success': True, 'shipping_id': shipping_id, 'pdf_label': pdf_label}

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