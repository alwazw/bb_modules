import os
import sys
import unittest
import requests
from unittest.mock import patch, MagicMock, mock_open, call

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from shipping import workflow
from tracking import workflow as tracking_workflow

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
            'get_db_connection': patch('tracking.workflow.get_db_connection', return_value=self.mock_conn),
            'get_best_buy_api_key': patch('tracking.workflow.get_best_buy_api_key', return_value='fake_bb_key'),
            'update_bb_tracking_number': patch('tracking.workflow.update_bb_tracking_number'),
            'mark_bb_order_as_shipped': patch('tracking.workflow.mark_bb_order_as_shipped'),
            'add_order_status_history': patch('tracking.workflow.add_order_status_history'),
            'log_process_failure': patch('tracking.workflow.log_process_failure'),
            'get_shipments_to_update_on_bb': patch('tracking.workflow.get_shipments_to_update_on_bb')
        }
        self.mocks = {name: patcher.start() for name, patcher in self.patchers.items()}
        self.addCleanup(self.stop_all_patchers)

    def stop_all_patchers(self):
        for patcher in self.patchers.values():
            patcher.stop()

    def test_happy_path_tracking_update(self):
        """Tests the ideal scenario: tracking is updated successfully."""
        self.mocks['get_shipments_to_update_on_bb'].return_value = [MOCK_SHIPMENT]
        self.mocks['update_bb_tracking_number'].return_value = (True, "Success", 204, {})
        self.mocks['mark_bb_order_as_shipped'].return_value = (True, "Success", 204)
        tracking_workflow.main()
        self.mocks['update_bb_tracking_number'].assert_called_once()
        self.mocks['mark_bb_order_as_shipped'].assert_called_once()
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_SHIPMENT['order_id'], 'shipped', notes='Successfully marked as shipped on Best Buy.'
        )
        self.mocks['log_process_failure'].assert_not_called()

    def test_update_bb_tracking_number_fails(self):
        """Tests the case where updating the tracking number on Best Buy fails."""
        self.mocks['get_shipments_to_update_on_bb'].return_value = [MOCK_SHIPMENT]
        self.mocks['update_bb_tracking_number'].return_value = (False, "Server Error", 500, {})
        tracking_workflow.main()
        self.mocks['log_process_failure'].assert_called_once()
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_SHIPMENT['order_id'], 'tracking_failed', notes=unittest.mock.ANY
        )

    def test_mark_as_shipped_fails(self):
        """Tests the case where marking the order as shipped on Best Buy fails."""
        self.mocks['get_shipments_to_update_on_bb'].return_value = [MOCK_SHIPMENT]
        self.mocks['update_bb_tracking_number'].return_value = (True, "Success", 204, {})
        self.mocks['mark_bb_order_as_shipped'].return_value = (False, "Server Error", 500)
        tracking_workflow.main()
        self.mocks['log_process_failure'].assert_called_once()
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_SHIPMENT['order_id'], 'tracking_failed', notes=unittest.mock.ANY
        )

if __name__ == '__main__':
    unittest.main()

class TestGetShippableOrders(unittest.TestCase):

    def setUp(self):
        self.conn = workflow.get_db_connection()
        # Clean up any existing test data
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM shipments WHERE order_id = 'test-order-123'")
            cur.execute("DELETE FROM order_status_history WHERE order_id = 'test-order-123'")
            cur.execute("DELETE FROM order_lines WHERE order_id = 'test-order-123'")
            cur.execute("DELETE FROM orders WHERE order_id = 'test-order-123'")
            cur.execute("DELETE FROM customers WHERE mirakl_customer_id = 'test-customer-123'")
        self.conn.commit()

    def tearDown(self):
        # Clean up the test data
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM shipments WHERE order_id = 'test-order-123'")
            cur.execute("DELETE FROM order_status_history WHERE order_id = 'test-order-123'")
            cur.execute("DELETE FROM order_lines WHERE order_id = 'test-order-123'")
            cur.execute("DELETE FROM orders WHERE order_id = 'test-order-123'")
            cur.execute("DELETE FROM customers WHERE mirakl_customer_id = 'test-customer-123'")
        self.conn.commit()
        self.conn.close()

    def test_get_shippable_orders_excludes_orders_with_shipments(self):
        """
        Tests that get_shippable_orders_from_db excludes orders that already have a shipment record.
        """
        # 1. Create a customer, order, and order line
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO customers (mirakl_customer_id, firstname, lastname) VALUES (%s, %s, %s) RETURNING id", ('test-customer-123', 'Test', 'User'))
            customer_id = cur.fetchone()[0]
            cur.execute("INSERT INTO orders (order_id, raw_order_data) VALUES (%s, %s)", ('test-order-123', '{}'))
            cur.execute("INSERT INTO order_lines (order_line_id, order_id, sku, quantity) VALUES (%s, %s, %s, %s)", ('test-order-line-123', 'test-order-123', 'test-sku-123', 1))
            # 2. Set the order status to 'accepted'
            cur.execute("INSERT INTO order_status_history (order_id, status) VALUES (%s, %s)", ('test-order-123', 'accepted'))
        self.conn.commit()

        # 3. Call get_shippable_orders_from_db and assert that the order is returned
        shippable_orders = workflow.get_shippable_orders_from_db(self.conn)
        self.assertEqual(len(shippable_orders), 1)
        self.assertEqual(shippable_orders[0]['order_id'], 'test-order-123')

        # 4. Create a shipment for the order
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO shipments (order_id) VALUES (%s)", ('test-order-123',))
        self.conn.commit()

        # 5. Call get_shippable_orders_from_db again and assert that the order is NOT returned
        shippable_orders = workflow.get_shippable_orders_from_db(self.conn)
        self.assertEqual(len(shippable_orders), 0)
