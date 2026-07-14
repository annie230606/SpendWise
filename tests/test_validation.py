import sys
import os

# Set stdout to UTF-8 to handle emojis and rupee symbols
sys.stdout.reconfigure(encoding='utf-8')

# Add root directory to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.client import delete_user_data, create_user, create_budget, get_budgets
from agent.coach import process_automated_transaction

def run_validation_test():
    test_phone = "+15550009999"
    print("=" * 60)
    print("Ollama Agent Validation Unit Test")
    print("=" * 60)
    
    # 1. Clean up user data
    print("\n[Setup] Cleaning up test user...")
    delete_user_data(test_phone)
    
    # 2. Setup user and budgets
    print("[Setup] Creating test user and category limits...")
    create_user(test_phone, savings_goal_amount=500.0, savings_goal_deadline="2026-07-31")
    # Category Groceries (limit 300, spent 0)
    create_budget(test_phone, "Groceries", monthly_limit=300.0, current_spent=0.0)
    # Category Dining Out (limit 200, spent 50)
    create_budget(test_phone, "Dining Out", monthly_limit=200.0, current_spent=50.0)
    
    # Verify setup
    budgets = get_budgets(test_phone)
    print("Initial Budgets:")
    for b in budgets:
        print(f" - {b['category']}: Spent Rs. {b['current_spent']} of Rs. {b['monthly_limit']}")
        
    # 3. Spend 290 on Groceries
    print("\n[Test] Simulating purchase: ₹290.00 at Costco (Groceries)...")
    # This leaves exactly ₹10.00 in Groceries budget. It should flag as high-risk impulse buy.
    result = process_automated_transaction(
        phone_number=test_phone,
        amount=290.0,
        category="Groceries",
        merchant="Costco"
    )
    
    # 4. Assert and print results
    print("\n[Result] Response returned from process_automated_transaction:")
    print(f"Is Flagged: {result.get('is_flagged')}")
    print(f"Risk Level: {result.get('risk_level')}")
    print(f"Reason: {result.get('reason')}")
    print(f"WhatsApp Suggestion:\n{result.get('whatsapp_suggestion')}")
    
    assert result.get("is_flagged") is True, "Test FAILED: Transaction should be flagged as high risk."
    assert result.get("risk_level") == "High", "Test FAILED: Risk level should be High."
    assert "🚨" in result.get("whatsapp_suggestion"), "Test FAILED: WhatsApp suggestion should contain 🚨 emoji."
    assert "📉" in result.get("whatsapp_suggestion"), "Test FAILED: WhatsApp suggestion should contain 📉 emoji."
    assert "🔄" in result.get("whatsapp_suggestion"), "Test FAILED: WhatsApp suggestion should contain 🔄 emoji."
    
    print("\nPASSED ✅")
    
    # Cleanup
    print("\n[Cleanup] Removing test user data...")
    delete_user_data(test_phone)
    print("Cleaned up.")
    print("=" * 60)

if __name__ == "__main__":
    run_validation_test()
