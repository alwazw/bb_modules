import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from customer_service.src.auto_reply import run_auto_reply_logic

def main():
    """
    Main function to run the customer service auto-reply module.
    """
    print("--- Starting Customer Service - Auto-Reply Module ---")
    try:
        run_auto_reply_logic()
        print("--- Customer Service - Auto-Reply Module Complete ---")
    except Exception as e:
        print(f"An error occurred during the auto-reply process: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
