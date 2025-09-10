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

MOCK_SHIPMENT = {
    'shipment_id': 1,
    'order_id': 'BBY-SHIP-123',
    'tracking_pin': '123123123'
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
        self.mock_cp_creds = {
            'api_user': 'user',
            'api_password': 'pass',
            'customer_number': 'cust_num',
            'paid_by_customer': 'paid_by',
            'contract_id': 'contract'
        }

        self.patchers = {
            'get_db_connection': patch('shipping.workflow.get_db_connection', return_value=self.mock_conn),
            'get_canada_post_credentials': patch('shipping.workflow.get_canada_post_credentials', return_value=self.mock_cp_creds),
            'get_best_buy_api_key': patch('shipping.workflow.get_best_buy_api_key', return_value='fake_bb_key'),
            'requests.post': patch('requests.post'),
            'requests.put': patch('requests.put'),
            'download_label_pdf': patch('shipping.workflow.download_label_pdf', return_value=True),
            'os.path.exists': patch('os.path.exists', return_value=True),
            'validate_xml_content': patch('shipping.workflow.validate_xml_content', return_value=True),
            'validate_pdf_content': patch('shipping.workflow.validate_pdf_content', return_value=True),
            'add_order_status_history': patch('shipping.workflow.add_order_status_history'),
            'log_process_failure': patch('shipping.workflow.log_process_failure'),
            'create_shipment_record': patch('shipping.workflow.create_shipment_record', return_value=1)
        }
        self.mocks = {name: patcher.start() for name, patcher in self.patchers.items()}
        self.addCleanup(self.stop_all_patchers)

    def stop_all_patchers(self):
        for patcher in self.patchers.values():
            patcher.stop()

    def test_happy_path_label_creation_and_validation(self):
        """Tests the ideal scenario: a label is created, downloaded, and validated successfully."""
        self.mocks['requests.post'].return_value = MagicMock(status_code=200, text=MOCK_CP_SUCCESS_RESPONSE)
        workflow.process_single_order_shipping(self.mock_conn, self.mock_cp_creds, MOCK_ORDER)
        self.mocks['validate_xml_content'].assert_called_once()
        self.mocks['validate_pdf_content'].assert_called_once()
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_ORDER['order_id'], 'label_created', notes='Tracking PIN: 123123123'
        )
        self.mocks['log_process_failure'].assert_not_called()

    def test_api_fails_with_retries_then_logs_failure(self):
        """Tests that a persistent API failure is retried and then logged as a critical failure."""
        self.mocks['requests.post'].side_effect = requests.exceptions.RequestException(
            response=MagicMock(status_code=500, text="Server Error")
        )
        workflow.process_single_order_shipping(self.mock_conn, self.mock_cp_creds, MOCK_ORDER)
        self.assertEqual(self.mocks['requests.post'].call_count, workflow.MAX_LABEL_CREATION_ATTEMPTS)
        self.mocks['log_process_failure'].assert_called_once()
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_ORDER['order_id'], 'shipping_failed', notes=unittest.mock.ANY
        )

    def test_content_validation_fails(self):
        """Tests that a failure in the content validation stops the process and logs an error."""
        self.mocks['requests.post'].return_value = MagicMock(status_code=200, text=MOCK_CP_SUCCESS_RESPONSE)
        self.mocks['validate_xml_content'].return_value = False
        workflow.process_single_order_shipping(self.mock_conn, self.mock_cp_creds, MOCK_ORDER)
        self.mocks['validate_xml_content'].assert_called_once()
        self.mocks['log_process_failure'].assert_called_once()
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_ORDER['order_id'], 'shipping_failed', notes=unittest.mock.ANY
        )
        for call_args in self.mocks['add_order_status_history'].call_args_list:
            self.assertNotEqual(call_args[0][1], 'label_created')

class TestTrackingUpdateWorkflow(unittest.TestCase):

    def setUp(self):
        """Set up mock objects for each test."""
        self.mock_conn = MagicMock()
        self.patchers = {
            'get_db_connection': patch('shipping.workflow.get_db_connection', return_value=self.mock_conn),
            'get_best_buy_api_key': patch('shipping.workflow.get_best_buy_api_key', return_value='fake_bb_key'),
            'requests.put': patch('requests.put'),
            'add_order_status_history': patch('shipping.workflow.add_order_status_history'),
            'log_process_failure': patch('shipping.workflow.log_process_failure'),
            'get_shipments_to_update_on_bb': patch('shipping.workflow.get_shipments_to_update_on_bb')
        }
        self.mocks = {name: patcher.start() for name, patcher in self.patchers.items()}
        self.addCleanup(self.stop_all_patchers)

    def stop_all_patchers(self):
        for patcher in self.patchers.values():
            patcher.stop()

    def test_happy_path_tracking_update(self):
        """Tests the ideal scenario: tracking is updated successfully."""
        self.mocks['get_shipments_to_update_on_bb'].return_value = [MOCK_SHIPMENT]
        self.mocks['requests.put'].return_value = MagicMock(status_code=204)
        workflow.update_tracking_workflow(self.mock_conn, 'fake_bb_key')
        self.assertEqual(self.mocks['requests.put'].call_count, 2)
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_SHIPMENT['order_id'], 'shipped', notes='Successfully marked as shipped on Best Buy.'
        )
        self.mocks['log_process_failure'].assert_not_called()

    def test_update_bb_tracking_number_fails(self):
        """Tests the case where updating the tracking number on Best Buy fails."""
        self.mocks['get_shipments_to_update_on_bb'].return_value = [MOCK_SHIPMENT]
        self.mocks['requests.put'].side_effect = [
            requests.exceptions.RequestException(response=MagicMock(status_code=500, text="Server Error")),
            MagicMock(status_code=204)
        ]
        workflow.update_tracking_workflow(self.mock_conn, 'fake_bb_key')
        self.mocks['log_process_failure'].assert_called_once()
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_SHIPMENT['order_id'], 'tracking_failed', notes=unittest.mock.ANY
        )

    def test_mark_as_shipped_fails(self):
        """Tests the case where marking the order as shipped on Best Buy fails."""
        self.mocks['get_shipments_to_update_on_bb'].return_value = [MOCK_SHIPMENT]
        self.mocks['requests.put'].side_effect = [
            MagicMock(status_code=204),
            requests.exceptions.RequestException(response=MagicMock(status_code=500, text="Server Error"))
        ]
        workflow.update_tracking_workflow(self.mock_conn, 'fake_bb_key')
        self.mocks['log_process_failure'].assert_called_once()
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_SHIPMENT['order_id'], 'tracking_failed', notes=unittest.mock.ANY
        )

if __name__ == '__main__':
    unittest.main()
