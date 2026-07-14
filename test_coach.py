import json
import sys
from types import ModuleType

# 1. Setup Mock Database BEFORE importing coach
mock_db = ModuleType('database')
mock_db.client = ModuleType('client')

def mock_get_budgets(phone):
    print("📋 [Mock DB] Fetching budgets for user...")
    return [
        {"category": "Food", "monthly_limit": 2000.0, "current_spent": 1900.0},
        {"category": "Entertainment", "monthly_limit": 1500.0, "current_spent": 200.0}
    ]

def mock_update_budget(phone, cat, current_spent):
    print(f"💾 [Mock DB] Successfully updated {cat} budget to total spent: ₹{current_spent}")

mock_db.client.get_budgets = mock_get_budgets
mock_db.client.update_budget = mock_update_budget
mock_db.client.create_budget = lambda p, c, l, s: {"category": c, "monthly_limit": l, "current_spent": s}

sys.modules['database'] = mock_db
sys.modules['database.client'] = mock_db.client

# 2. Now import the process function safely
try:
    from agent.coach import process_automated_transaction
except Exception as e:
    print(f"❌ Failed to import from agent.coach: {e}")
    sys.exit(1)

if __name__ == "__main__":
    print("\n🚀 [Test] Simulating a ₹200 transaction at Zomato...")
    
    try:
        output = process_automated_transaction(
            phone_number="+919999999999",
            amount=200.0,
            category="Food",
            merchant="Zomato"
        )
        
        print("\n📊 [Test Result Summary]:")
        print(json.dumps(output, indent=2))
        
    except Exception as err:
        print(f"❌ Run crashed with error: {err}")
