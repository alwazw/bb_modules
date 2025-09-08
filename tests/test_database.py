import os
import sys
import unittest
import psycopg2
from unittest.mock import patch, MagicMock, mock_open

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from database.db_utils import get_db_connection, initialize_database

class TestDatabaseUtils(unittest.TestCase):

    @patch('database.db_utils.psycopg2.connect')
    def test_get_db_connection_success(self, mock_connect):
        """
        Tests that get_db_connection returns a connection object on success.
        """
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        conn = get_db_connection()

        self.assertIsNotNone(conn)
        self.assertEqual(conn, mock_conn)
        mock_connect.assert_called_once()

    @patch('database.db_utils.psycopg2.connect')
    def test_get_db_connection_failure(self, mock_connect):
        """
        Tests that get_db_connection returns None when a connection cannot be established.
        """
        # The code specifically catches OperationalError, so we should test that case.
        mock_connect.side_effect = psycopg2.OperationalError("Connection failed")

        conn = get_db_connection()

        self.assertIsNone(conn)

    @patch('database.db_utils.get_db_connection')
    @patch('builtins.open', new_callable=mock_open, read_data="CREATE TABLE test;DROP TABLE test;")
    def test_initialize_database_success(self, mock_file, mock_get_conn):
        """
        Tests that initialize_database reads the schema and executes it.
        """
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        initialize_database()

        # Check that a connection was requested and a cursor was created
        mock_get_conn.assert_called_once()
        mock_conn.cursor.assert_called_once()

        # Check that the SQL from the mock file was executed
        mock_cursor.execute.assert_called_once_with("CREATE TABLE test;DROP TABLE test;")

        # Check that the transaction was committed and the connection was closed
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('database.db_utils.get_db_connection')
    def test_initialize_database_no_connection(self, mock_get_conn):
        """
        Tests that initialize_database handles the case where no DB connection is available.
        """
        mock_get_conn.return_value = None

        with patch('builtins.open', mock_open(read_data="")):
            initialize_database()

        mock_get_conn.assert_called_once()

    @patch('database.db_utils.psycopg2.connect')
    def test_add_order_status_history(self, mock_connect):
        """Tests that a new status history record is inserted correctly."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        from database.db_utils import add_order_status_history
        add_order_status_history(mock_conn, 'ORDER123', 'shipped', 'Notes here')

        mock_cursor.execute.assert_called_once_with(
            unittest.mock.ANY,
            ('ORDER123', 'shipped', 'Notes here')
        )
        mock_conn.commit.assert_called_once()

    @patch('database.db_utils.psycopg2.connect')
    def test_log_process_failure(self, mock_connect):
        """Tests that a new process failure is logged correctly."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        from database.db_utils import log_process_failure
        payload = {'data': 'test'}
        log_process_failure(mock_conn, 'ORDER123', 'TestProcess', 'It failed', payload)

        mock_cursor.execute.assert_called_once_with(
            unittest.mock.ANY,
            ('ORDER123', 'TestProcess', 'It failed', unittest.mock.ANY)
        )
        mock_conn.commit.assert_called_once()

if __name__ == '__main__':
    with patch('builtins.input', return_value='yes'):
        unittest.main()
