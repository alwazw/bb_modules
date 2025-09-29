import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import json

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# Modules to be tested
from shipping.canpar.canpar_scripts import canpar_api_client, canpar_db_utils, canpar_bb_orders_labels_automation_api
from order_management.awaiting_shipment.orders_awaiting_shipment import retrieve_pending_shipping

class TestCanparWorkflow(unittest.TestCase):

    def setUp(self):
        """Set up mock data that can be used across multiple tests."""
        # This represents what comes from the Best Buy API
        self.mock_api_order = {
            'order_id': 'BBY-12345',
            'customer': {
                'firstname': 'John',
                'lastname': 'Doe',
                'email': 'john.doe@example.com',
                'shipping_address': {
                    'firstname': 'John',
                    'lastname': 'Doe',
                    'street_1': '123 Test St',
                    'city': 'Testville',
                    'state': 'ON',
                    'zip_code': 'K1A0B1',
                    'phone': '555-555-5555'
                }
            },
            'order_lines': [{'quantity': 1, 'offer_sku': 'SKU123'}],
            'total_price': 100.00
        }
        # This represents what's fetched from our database (the raw_order_data contains the api order)
        self.mock_db_order = {
            'order_id': 'BBY-12345',
            'raw_order_data': self.mock_api_order
        }

    @patch('shipping.canpar.canpar_scripts.canpar_api_client.get_business_service_client')
    def test_create_shipment_api_client_success(self, mock_get_client):
        """Test the Canpar API client's create_shipment function on success."""
        mock_client = MagicMock()
        mock_factory = MagicMock()
        mock_client.type_factory.return_value = mock_factory
        mock_get_client.return_value = mock_client

        mock_api_response = {
            'return': {
                'error': None,
                'shipment': {
                    'packages': [{'barcode': 'D123456789', 'label': 'encoded-pdf-data'}]
                }
            }
        }
        mock_client.service.processShipment.return_value = mock_api_response

        order_details_for_api = {
            'order_id': 'BBY-12345', 'delivery_name': 'John Doe', 'delivery_attention': '1x SKU123',
            'delivery_address_1': '123 Test St', 'delivery_city': 'Testville', 'delivery_province': 'ON',
            'delivery_postal_code': 'K1A0B1', 'delivery_phone': '555-555-5555',
            'delivery_email': 'john.doe@example.com', 'weight': 2, 'declared_value': 100.00
        }

        result = canpar_api_client.create_shipment(order_details_for_api)

        self.assertTrue(result['success'])
        self.assertEqual(result['shipping_id'], 'D123456789')
        self.assertEqual(result['pdf_label'], 'encoded-pdf-data')
        self.assertTrue(mock_factory.Address.called)
        self.assertTrue(mock_factory.Package.called)
        self.assertTrue(mock_factory.Shipment.called)

    @patch('shipping.canpar.canpar_scripts.canpar_db_utils.get_db_connection')
    def test_get_orders_ready_for_shipping(self, mock_get_db_connection):
        """Test fetching orders that are ready for shipping from the database."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_connection.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [self.mock_db_order]

        orders = canpar_db_utils.get_orders_ready_for_shipping()

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]['order_id'], 'BBY-12345')
        mock_cursor.execute.assert_called_once()

    @patch('shipping.canpar.canpar_scripts.canpar_bb_orders_labels_automation_api.canpar_api_client.create_shipment')
    @patch('shipping.canpar.canpar_scripts.canpar_bb_orders_labels_automation_api.canpar_db_utils.create_canpar_shipment')
    @patch('shipping.canpar.canpar_scripts.canpar_bb_orders_labels_automation_api.add_order_status_history')
    @patch('shipping.canpar.canpar_scripts.canpar_bb_orders_labels_automation_api.update_best_buy_order_status')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_process_single_order_success(self, mock_makedirs, mock_file, mock_update_bb, mock_add_status, mock_create_shipment_db, mock_create_shipment_api):
        """Test the end-to-end processing of a single order."""
        mock_create_shipment_api.return_value = {'success': True, 'shipping_id': 'D12345', 'pdf_label': 'cGRmZGF0YQ=='}
        mock_create_shipment_db.return_value = 99
        mock_update_bb.return_value = True

        mock_conn = MagicMock()

        result = canpar_bb_orders_labels_automation_api.process_single_order(self.mock_db_order, mock_conn)

        self.assertTrue(result)
        mock_create_shipment_api.assert_called_once()
        mock_file.assert_called_once()
        mock_create_shipment_db.assert_called_once()
        self.assertEqual(mock_add_status.call_count, 2)
        mock_update_bb.assert_called_once()

    @patch('order_management.awaiting_shipment.orders_awaiting_shipment.retrieve_pending_shipping.get_db_connection')
    def test_save_new_orders_to_db(self, mock_get_db_connection):
        """Test saving new orders to the database."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_connection.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.rowcount = 1

        retrieve_pending_shipping.save_new_orders_to_db([self.mock_api_order])

        self.assertEqual(mock_cursor.execute.call_count, 2)
        mock_conn.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()