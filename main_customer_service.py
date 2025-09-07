import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from customer_service.message_aggregation.fetch_messages import fetch_and_save_messages

def main():
    """
    Main function to run the customer service message aggregation phase.
    """
    print("--- Starting Phase 5: Customer Service - Message Aggregation ---")

    try:
        fetch_and_save_messages()
        print("--- Phase 5: Customer Service - Message Aggregation Complete ---")
    except Exception as e:
        print(f"An error occurred during the customer service phase: {e}")
        # In a real application, you might want to add more robust error handling
        # and notifications (e.g., sending an alert to an admin).
        sys.exit(1)

if __name__ == "__main__":
    main()
