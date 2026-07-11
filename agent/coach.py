import os
import calendar
import datetime
import json
from dotenv import load_dotenv
from llama_cpp import Llama
from database.client import update_budget_with_history, get_budget_by_category, supabase_admin, update_budget, get_budgets

load_dotenv()

_llm_instance = None

def get_llm():
    global _llm_instance
    if _llm_instance is None:
        model_path = os.getenv("LOCAL_LLM_FILE_PATH", "models/Phi-3-mini-4k-instruct-q4.gguf")
        try:
            _llm_instance = Llama(model_path=model_path, n_threads=2, n_ctx=2048, verbose=False)
        except Exception as ex:
            print(f"⚠️ Failed to load model: {ex}")
    return _llm_instance

def evaluate_sustainability(remaining_budget: float) -> bool:
    now = datetime.datetime.utcnow()
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    remaining_days = max(1, days_in_month - now.day + 1)
    projected_daily = remaining_budget / remaining_days
    return projected_daily >= 6.0 

def simulate_rebalancing(budgets: list, breached_category: str, deficit: float) -> dict:
    other_categories = [b for b in budgets if b["category"] != breached_category]
    total_remaining = sum(max(0.0, float(b["monthly_limit"]) - float(b["current_spent"])) for b in other_categories)
    proposed_limits = {}
    if total_remaining >= deficit and total_remaining > 0:
        for b in other_categories:
            cat = b["category"]
            rem = max(0.0, float(b["monthly_limit"]) - float(b["current_spent"]))
            # Proportional reduction
            reduction = deficit * (rem / total_remaining)
            proposed_limits[cat] = round(float(b["monthly_limit"]) - reduction, 2)
    return proposed_limits

def apply_confirmed_budget(phone_number: str, proposed_limits: dict, target_category: str):
    """
    Applies rebalancing. New limit = current_spent + remaining_buffer + reclaimed_amount.
    """
    total_reclaimed = 0.0
    for category, new_limit in proposed_limits.items():
        if category == target_category: continue
        old_record = get_budget_by_category(phone_number, category)
        if not old_record: continue
        old_limit = float(old_record["monthly_limit"])
        reduction = old_limit - new_limit
        total_reclaimed += reduction
        update_budget_with_history(phone_number, category, new_limit, reason="AI_REBALANCE_REDUCTION")
    
    target_record = get_budget_by_category(phone_number, target_category)
    if target_record:
        current_spent = float(target_record["current_spent"])
        original_limit = float(target_record["monthly_limit"])
        remaining_buffer = max(0.0, original_limit - current_spent)
        
        # Applying your logic: New Limit = current_spent + remaining + reclaimed
        new_target_limit = current_spent + remaining_buffer + total_reclaimed
        
        update_budget_with_history(phone_number, target_category, new_target_limit, reason="AI_REBALANCE_TOPUP")
    
    supabase_admin.table("users").update({"pending_budget_json": None}).eq("phone_number", phone_number).execute()

def generate_coaching_message(merchant: str, amount: float, breached_category: str, deficit: float, proposed_limits: dict, budgets: list) -> str:
    llm = get_llm()
    limits_text = "\n".join([f"• {c}: New limit ₹{round(l)}" for c, l in proposed_limits.items()])
    prompt = (
        "<|system|>\nYou are a friendly, concise AI financial coach on WhatsApp. "
        "The user just spent ₹{amount} at {merchant} in '{breached_category}', which is pushing their budget. "
        "Write a short, encouraging text. "
        "RULES:\n"
        "1. NO formal greetings (no 'Hello', no 'Dear', no 'I hope...').\n"
        "2. NO professional signatures (no 'Best regards', no 'Financial Coach', no '[Your Name]').\n"
        "3. Use emojis to be friendly.\n"
        "4. Suggest these limits:\n{limits_text}\n"
        "5. End with exactly: 'Type Confirm to apply.'\n"
        "<|user|>\nGenerate the WhatsApp alert.\n<|assistant|>\n"
    )
    try:
        response = llm(prompt.format(amount=amount, merchant=merchant, breached_category=breached_category, limits_text=limits_text), max_tokens=300, temperature=0.7)
        return response["choices"][0]["text"].strip()
    except:
        return f"⚠️ Sustainability Alert: Limits updated. Reply 'Confirm' to apply."

def process_automated_transaction(phone_number: str, amount: float, category: str, merchant: str) -> dict:
    budgets = get_budgets(phone_number)
    cat_budget = next((b for b in budgets if b["category"] == category), None)
    current_spent = float(cat_budget["current_spent"]) if cat_budget else 0.0
    limit = float(cat_budget["monthly_limit"]) if cat_budget else 100.0
    new_spent = current_spent + amount
    update_budget(phone_number, category, current_spent=new_spent)
    
    rem_budget = limit - new_spent
    if not evaluate_sustainability(rem_budget):
        deficit = max(0.0, new_spent - limit)
        if deficit == 0: deficit = (limit * 0.4) 
        proposed_limits = simulate_rebalancing(budgets, category, deficit)
        pending_data = {"proposed_limits": proposed_limits, "breached_category": category}
        supabase_admin.table("users").update({"pending_budget_json": json.dumps(pending_data)}).eq("phone_number", phone_number).execute()
        coaching_msg = generate_coaching_message(merchant, amount, category, deficit, proposed_limits, budgets)
        return {"alert": True, "coaching_message": coaching_msg}
    return {"alert": False}