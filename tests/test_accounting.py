import unittest
from unittest.mock import patch, mock_open
import json
from accounting.fetch_transactions import get_transactions, save_transactions_to_json

class TestAccounting(unittest.TestCase):

    @patch('requests.get')
    def test_get_transactions_success(self, mock_get):
        # Mock the API response for a successful call
        mock_response = {
            "data": [
                {"id": "1", "amount": 100},
                {"id": "2", "amount": 200}
            ],
            "next_page_token": None
        }
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response

        transactions = get_transactions("fake_api_key")

        self.assertEqual(len(transactions), 2)
        self.assertEqual(transactions[0]['id'], '1')
        self.assertEqual(transactions[1]['amount'], 200)

    @patch('requests.get')
    def test_get_transactions_api_error(self, mock_get):
        # Mock an API error
        mock_get.return_value.status_code = 500
        mock_get.return_value.text = "Internal Server Error"

        with self.assertRaises(requests.exceptions.HTTPError):
            get_transactions("fake_api_key")

    @patch('requests.get')
    def test_get_transactions_empty_response(self, mock_get):
        # Mock an empty response from the API
        mock_response = {
            "data": [],
            "next_page_token": None
        }
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response

        transactions = get_transactions("fake_api_key")

        self.assertEqual(len(transactions), 0)

    def test_save_transactions_to_json(self):
        transactions = [
            {"id": "1", "amount": 100},
            {"id": "2", "amount": 200}
        ]

        # Use mock_open to "catch" the file write
        m = mock_open()
        with patch('builtins.open', m):
            save_transactions_to_json(transactions, "fake/path.json")

        # Check that open was called with the correct path and mode
        m.assert_called_once_with("fake/path.json", "w")

        # Check that the correct data was written to the file
        handle = m()
        written_data = "".join(call.args[0] for call in handle.write.call_args_list)
        self.assertEqual(written_data, json.dumps(transactions, indent=4))

if __name__ == '__main__':
    unittest.main()
