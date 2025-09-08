import os
import sys
import unittest
import requests
from unittest.mock import patch, MagicMock, mock_open, call

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from shipping import workflow

# --- Test Data ---
MOCK_ORDER = {
    'order_id': 'BBY-SHIP-123',
    'raw_order_data': {
        'order_id': 'BBY-SHIP-123',
        'customer': {
            'shipping_address': {
                'firstname': 'John', 'lastname': 'Doe', 'street_1': '123 Test St',
                'city': 'Testville', 'state': 'ON', 'zip_code': 'A1B 2C3'
            }
        },
        'order_lines': [{'offer_sku': 'SKU-B', 'quantity': 1}]
    }
}

MOCK_CP_SUCCESS_RESPONSE = """
<shipment-info xmlns="http://www.canadapost.ca/ws/shipment-v8">
  <shipment-id>123456789</shipment-id>
  <tracking-pin>123123123</tracking-pin>
  <destination>
    <name>John Doe</name>
    <address-details>
        <postal-zip-code>A1B2C3</postal-zip-code>
    </address-details>
  </destination>
  <links>
    <link href="https://example.com/label" rel="label" media-type="application/pdf"/>
  </links>
</shipment-info>
"""

class TestShippingWorkflowV2(unittest.TestCase):

    def setUp(self):
        """Set up mock objects for each test."""
        self.mock_conn = MagicMock()
        self.mock_creds = ('user', 'pass', 'cust_num', 'paid_by', 'contract')

        self.patchers = {
            'get_db_connection': patch('shipping.workflow.get_db_connection', return_value=self.mock_conn),
            'get_canada_post_credentials': patch('shipping.workflow.get_canada_post_credentials', return_value=self.mock_creds),
            'requests.post': patch('requests.post'),
            'download_label_pdf': patch('shipping.workflow.download_label_pdf', return_value=True),
            'os.path.exists': patch('os.path.exists', return_value=True),
            'validate_xml_content': patch('shipping.workflow.validate_xml_content', return_value=True),
            'validate_pdf_content': patch('shipping.workflow.validate_pdf_content', return_value=True),
            'add_order_status_history': patch('shipping.workflow.add_order_status_history'),
            'log_process_failure': patch('shipping.workflow.log_process_failure'),
            'get_shippable_orders': patch('shipping.workflow.get_shippable_orders_from_db')
        }
        self.mocks = {name: patcher.start() for name, patcher in self.patchers.items()}
        self.addCleanup(self.stop_all_patchers)

    def stop_all_patchers(self):
        for patcher in self.patchers.values():
            patcher.stop()

    def test_happy_path_label_creation_and_validation(self):
        """Tests the ideal scenario: a label is created, downloaded, and validated successfully."""
        # --- Arrange ---
        self.mocks['get_shippable_orders'].return_value = [MOCK_ORDER]
        # Mock successful API call
        self.mocks['requests.post'].return_value = MagicMock(status_code=200, text=MOCK_CP_SUCCESS_RESPONSE)

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # 1. Check that the content validation functions were called.
        self.mocks['validate_xml_content'].assert_called_once()
        self.mocks['validate_pdf_content'].assert_called_once()

        # 2. Check that the final status was updated to 'label_created'.
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_ORDER['order_id'], 'label_created', notes='Tracking PIN: 123123123'
        )
        # 3. Ensure no failure was logged.
        self.mocks['log_process_failure'].assert_not_called()

    def test_api_fails_with_retries_then_logs_failure(self):
        """Tests that a persistent API failure is retried and then logged as a critical failure."""
        # --- Arrange ---
        self.mocks['get_shippable_orders'].return_value = [MOCK_ORDER]
        # Mock the API to always fail
        self.mocks['requests.post'].side_effect = requests.exceptions.RequestException(
            response=MagicMock(status_code=500, text="Server Error")
        )

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # 1. Check that the API was called the maximum number of times.
        self.assertEqual(self.mocks['requests.post'].call_count, workflow.MAX_LABEL_CREATION_ATTEMPTS)

        # 2. Check that a process failure was logged.
        self.mocks['log_process_failure'].assert_called_once()

        # 3. Check that the final status was updated to 'shipping_failed'.
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_ORDER['order_id'], 'shipping_failed', notes=unittest.mock.ANY
        )

    def test_content_validation_fails(self):
        """Tests that a failure in the content validation stops the process and logs an error."""
        # --- Arrange ---
        self.mocks['get_shippable_orders'].return_value = [MOCK_ORDER]
        self.mocks['requests.post'].return_value = MagicMock(status_code=200, text=MOCK_CP_SUCCESS_RESPONSE)
        # Mock the XML validation to return False
        self.mocks['validate_xml_content'].return_value = False

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # 1. Check that the validation was attempted.
        self.mocks['validate_xml_content'].assert_called_once()

        # 2. Check that a process failure was logged.
        self.mocks['log_process_failure'].assert_called_once()

        # 3. Check that the final status was updated to 'shipping_failed'.
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_ORDER['order_id'], 'shipping_failed', notes=unittest.mock.ANY
        )

        # 4. Check that the successful 'label_created' status was NOT set.
        for call_args in self.mocks['add_order_status_history'].call_args_list:
            self.assertNotEqual(call_args[0][1], 'label_created')

if __name__ == '__main__':
    unittest.main()
