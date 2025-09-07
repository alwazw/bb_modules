import unittest
from unittest.mock import patch, MagicMock

# Add project root to path to allow importing 'logic'
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Now we can import the logic module
from fulfillment_service.src import logic

class TestLogic(unittest.TestCase):

    def test_find_order_by_id_success(self):
        """
        Test that find_order_by_id returns the correct order when it exists.
        """
        orders = [
            {"order_id": "123", "customer": "A"},
            {"order_id": "456", "customer": "B"},
        ]
        result = logic.find_order_by_id(orders, "456")
        self.assertIsNotNone(result)
        self.assertEqual(result['customer'], "B")

    def test_find_order_by_id_not_found(self):
        """
        Test that find_order_by_id returns None when the order does not exist.
        """
        orders = [
            {"order_id": "123", "customer": "A"},
            {"order_id": "456", "customer": "B"},
        ]
        result = logic.find_order_by_id(orders, "999")
        self.assertIsNone(result)

    # We will need to mock the data loading to properly test get_work_order_details
    @patch('fulfillment_service.src.logic.load_json_file')
    def test_get_work_order_details_success(self, mock_load_json):
        """
        Test the successful retrieval of work order details.
        """
        # Arrange: Set up the mock return values for load_json_file
        mock_orders = [{"order_id": "TEST-1", "order_lines": [{"offer_sku": "SKU-A"}]}]
        mock_products = [{
            "variants": [{
                "sku": "SKU-A",
                "barcodes": {"ram": "RAM-123"}
            }]
        }]
        # The mock should return different values on subsequent calls
        mock_load_json.side_effect = [mock_orders, mock_products]

        # Act
        work_order, error = logic.get_work_order_details("TEST-1")

        # Assert
        self.assertIsNone(error)
        self.assertIsNotNone(work_order)
        self.assertEqual(work_order['order']['order_id'], "TEST-1")
        self.assertIn("RAM-123", work_order['required_components'])
        self.assertEqual(work_order['required_components']['RAM-123'], 'ram')


if __name__ == '__main__':
    unittest.main()
