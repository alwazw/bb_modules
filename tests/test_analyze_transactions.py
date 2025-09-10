import unittest
import csv
from accounting.analyze_transactions import analyze_and_remodel_transactions

class TestAnalyzeTransactions(unittest.TestCase):

    def test_analyze_and_remodel_transactions(self):
        # Load the sample transactions from the new CSV file
        with open("tests/sample_transactions.csv", "r") as f:
            reader = csv.DictReader(f)
            transactions = list(reader)

        analyzed_data = analyze_and_remodel_transactions(transactions)

        # There should be one order in the sample data
        self.assertEqual(len(analyzed_data), 1)

        order_analysis = analyzed_data[0]
        self.assertEqual(order_analysis["order_id"], "260962600-A")

        # Check the analysis results
        analysis = order_analysis["analysis"]
        self.assertAlmostEqual(analysis["selling_price"], 749.99)
        self.assertAlmostEqual(analysis["taxes"], 112.31) # 74.81 + 37.50
        self.assertAlmostEqual(analysis["commission"], 60.0)
        self.assertAlmostEqual(analysis["commission_tax"], 7.80)
        self.assertAlmostEqual(analysis["net_revenue"], 794.50) # (749.99 + 112.31) - (60.0 + 7.80)

    def test_analyze_and_remodel_empty_transactions(self):
        analyzed_data = analyze_and_remodel_transactions([])
        self.assertEqual(len(analyzed_data), 0)

if __name__ == '__main__':
    unittest.main()
