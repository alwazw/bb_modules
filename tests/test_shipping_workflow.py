import os
import sys
import unittest
import requests
from unittest.mock import patch, MagicMock, mock_open, call

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# The module to be tested
from shipping import workflow

# --- Test Data ---
MOCK_ORDER = {
    'order_id': 'BBY-SHIP-123',
    'status': 'accepted',
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
  <links>
    <link href="https://example.com/label" rel="label" media-type="application/pdf"/>
  </links>
</shipment-info>
"""

class TestShippingWorkflow(unittest.TestCase):

    def setUp(self):
        """Set up mock objects for each test."""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__.return_value = self.mock_cursor

        # Mock credentials
        self.mock_creds = ('user', 'pass', 'cust_num', 'paid_by', 'contract')

        self.patchers = [
            patch('shipping.workflow.get_db_connection', return_value=self.mock_conn),
            patch('shipping.workflow.get_canada_post_credentials', return_value=self.mock_creds),
            patch('requests.post'),
            patch('requests.get'),
            patch('builtins.open', new_callable=mock_open),
            patch('os.makedirs')
        ]

        for p in self.patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_happy_path_label_creation(self):
        """Tests the ideal scenario: a label is created and downloaded successfully."""
        # --- Arrange ---
        # DB returns one order to process
        self.mock_cursor.fetchall.return_value = [MOCK_ORDER]
        # The INSERT for the shipment record returns a new ID
        self.mock_cursor.fetchone.return_value = (1,)

        # Mock the Canada Post API call to succeed
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.text = MOCK_CP_SUCCESS_RESPONSE
        workflow.requests.post.return_value = mock_post_response

        # Mock the PDF download call to succeed
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.content = b'%PDF-1.4...'
        workflow.requests.get.return_value = mock_get_response

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # 1. Check that we fetched shippable orders
        self.mock_cursor.execute.assert_any_call(unittest.mock.ANY, unittest.mock.ANY) # Simplified check

        # 2. Check that an initial shipment record was created
        self.mock_cursor.execute.assert_any_call(
            "INSERT INTO shipments (order_id, status) VALUES (%s, %s) RETURNING shipment_id;",
            (MOCK_ORDER['order_id'], 'label_creation_initiated')
        )

        # 3. Check that the CP 'Create Shipment' API was called
        workflow.requests.post.assert_called_once()

        # 4. Check that the API call was logged
        self.mock_cursor.execute.assert_any_call(
            unittest.mock.ANY,
            ('CanadaPost', 'CreateShipment', MOCK_ORDER['order_id'], unittest.mock.ANY, MOCK_CP_SUCCESS_RESPONSE, 200, True)
        )

        # 5. Check that the PDF download was attempted
        workflow.requests.get.assert_called_once_with(
            'https://example.com/label', headers=unittest.mock.ANY, timeout=unittest.mock.ANY
        )

        # 6. Check that the shipment record was updated with the final info
        self.mock_cursor.execute.assert_any_call(
            unittest.mock.ANY,
            ('123123123', 'https://example.com/label', unittest.mock.ANY, 1)
        )

    def test_api_failure_path(self):
        """Tests that a failure from the CP API is handled gracefully."""
        # --- Arrange ---
        self.mock_cursor.fetchall.return_value = [MOCK_ORDER]
        self.mock_cursor.fetchone.return_value = (1,)

        # Mock the CP API to fail
        mock_post_response = MagicMock()
        mock_post_response.status_code = 400
        mock_post_response.text = "<error><message>Invalid XML</message></error>"
        # Side effect for requests.post should be a RequestException that contains our mock response
        workflow.requests.post.side_effect = requests.exceptions.RequestException(response=mock_post_response)

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # 1. Check that the API call was still logged, but as a failure
        self.mock_cursor.execute.assert_any_call(
            unittest.mock.ANY,
            ('CanadaPost', 'CreateShipment', MOCK_ORDER['order_id'], unittest.mock.ANY, mock_post_response.text, 400, False)
        )

        # 2. Check that the PDF download was NOT attempted
        workflow.requests.get.assert_not_called()

        # 3. Check that the shipment record was NOT updated with tracking info
        # This is tricky to assert directly, but we can check that the successful update call was not made.
        update_call = call(
            unittest.mock.ANY,
            (unittest.mock.ANY, unittest.mock.ANY, unittest.mock.ANY, 1)
        )
        # Ensure the specific UPDATE call with tracking info is not in the list of calls
        self.assertNotIn(update_call, self.mock_cursor.execute.call_args_list)


if __name__ == '__main__':
    unittest.main()
