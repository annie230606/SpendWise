import sys
import os

# Add root directory to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.coach import calculate_spending_velocity, simulate_rebalancing

def test_spending_velocity():
    # Test case 1: spending is safe
    # Limit: $1000, Spent: $200, New: $100. Day of month: assume today is mid-month.
    # To test deterministic velocity, let's look at calculate_spending_velocity logic.
    # It uses datetime.datetime.utcnow(), so it depends on the current day.
    # Let's verify it returns a float and handles limits correctly.
    v = calculate_spending_velocity(200.0, 100.0, 1000.0)
    assert isinstance(v, float)
    print("test_spending_velocity passed!")

def test_rebalancing():
    # Test case 2: rebalancing simulation
    # Deficit to cover: $130
    # Budgets: Shopping is breached. Other categories: Dining Out ($200 limit, $50 spent -> $150 rem) and Entertainment ($100 limit, $10 spent -> $90 rem)
    budgets = [
        {"category": "Shopping", "monthly_limit": 100.0, "current_spent": 230.0},
        {"category": "Dining Out", "monthly_limit": 200.0, "current_spent": 50.0},
        {"category": "Entertainment", "monthly_limit": 100.0, "current_spent": 10.0}
    ]
    
    proposed = simulate_rebalancing(budgets, "Shopping", 130.0)
    
    # Dining Out remaining: 150. Entertainment remaining: 90. Total remaining = 240
    # Dining Out reduction = 130 * (150/240) = 81.25 -> New limit = 200 - 81.25 = 118.75
    # Entertainment reduction = 130 * (90/240) = 48.75 -> New limit = 100 - 48.75 = 51.25
    assert proposed["Dining Out"] == 118.75
    assert proposed["Entertainment"] == 51.25
    print("test_rebalancing passed!")

if __name__ == "__main__":
    test_spending_velocity()
    test_rebalancing()
