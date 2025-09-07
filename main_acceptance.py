import time
from Orders.pending_acceptance.orders_pending_acceptance.retieve_pending_acceptance import main as retrieve_main
from Orders.pending_acceptance.accept_orders_pending_confirmation.accept_orders import main as accept_main
from Orders.pending_acceptance.accept_pending_orders_validation.order_acceptance_validation import validate_acceptance

def main_orchestrator(): """ Orchestrates the entire order acceptance process flow. """ 
print("=============================================") 
print("=== PHASE 1: Best Buy Order Acceptance ===") 
print("=============================================")

max_retries = 3
retry_count = 0

while retry_count < max_retries:
    print(f"\n>>> Main Loop Attempt: {retry_count + 1}/{max_retries} <<<")
    
    print("\n>>> STEP 1.1: Retrieving all orders pending acceptance...")
    retrieve_main()
    
    print("\n>>> STEP 1.2: Sending requests to accept new orders...")
    accept_main()
    
    print("\nINFO: Waiting for 5 seconds for API to process acceptances...")
    time.sleep(5)
    
    print("\n>>> STEP 1.3: Validating that orders were accepted...")
    validation_status = validate_acceptance()
    
    print(f"\n>>> FINAL VALIDATION STATUS FOR PHASE 1: {validation_status} <<<")
    
    if validation_status == 'SUCCESS':
        print("\n✅ Graceful termination of Phase 1: All orders processed successfully.")
        break
        
    elif validation_status == 'VALIDATION_FAILED':
        print("\n❌ Error in Phase 1: Some orders failed to be accepted. Check 'failed_order_acceptances.json'.")
        break
        
    elif validation_status == 'NEW_ORDERS_FOUND':
        retry_count += 1
        print(f"\n🔄 New orders found. Looping back to the start.")
        if retry_count >= max_retries:
            print("\n❌ Error: Reached max retries for Phase 1. Exiting to avoid infinite loop.")
            break
        print("---------------------------------------------")
        time.sleep(2)
        
    else:
        print("\n- Phase 1 finished, but some pending orders may remain. Please check the logs.")
        break

print("\n=============================================")
print("===      Phase 1 Process Has Concluded      ===")
print("=============================================")

if __name__ == '__main__':
    main_orchestrator()
