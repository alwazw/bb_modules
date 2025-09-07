import unittest
import json
import os
from unittest.mock import patch, mock_open

# Add project root to path to allow importing 'shipping'
import sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT)

from shipping.canada_post.cp_shipping import cp_pdf_labels

class TestShipping(unittest.TestCase):

    def setUp(self):
        """Set up test data."""
        self.mock_order_data = {"order_id": "ORDER-1"}
        self.mock_xml_content = "<shipment></shipment>"

    @patch('builtins.open', new_callable=mock_open)
    def test_log_shipping_data(self, mock_file):
        cp_pdf_labels.log_shipping_data("ORDER-1", "TRACK-123", "http://example.com/label.pdf", "<response/>")
        mock_file().write.assert_called()

    @patch('builtins.open', new_callable=mock_open)
    def test_log_cp_history(self, mock_file):
        cp_pdf_labels.log_cp_history("<shipment_details/>")
        mock_file().write.assert_called()

    @patch('requests.post')
    def test_create_shipment_and_get_label_success(self, mock_post):
        # Mock the API response
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <shipment-info xmlns="http://www.canadapost.ca/ws/shipment-v8">
            <tracking-pin>TRACK-123</tracking-pin>
            <links>
                <link rel="label" href="http://example.com/label.pdf"/>
                <link rel="details" href="http://example.com/details"/>
            </links>
        </shipment-info>
        """
        mock_post.return_value = mock_response

        label_url, details_url, tracking_pin = cp_pdf_labels.create_shipment_and_get_label("user", "pass", "123", self.mock_xml_content, self.mock_order_data)
        self.assertEqual(label_url, "http://example.com/label.pdf")
        self.assertEqual(details_url, "http://example.com/details")
        self.assertEqual(tracking_pin, "TRACK-123")

    @patch('requests.get')
    def test_download_label_success(self, mock_get):
        # Mock the API response
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.content = b"PDF content"
        mock_get.return_value = mock_response

        with patch('builtins.open', mock_open()) as mock_file:
            result = cp_pdf_labels.download_label("http://example.com/label.pdf", "user", "pass", "label.pdf")
            self.assertTrue(result)
            mock_file().write.assert_called_with(b"PDF content")

if __name__ == '__main__':
    unittest.main()
