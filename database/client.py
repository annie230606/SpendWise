import os
import time
import jwt
from dotenv import load_dotenv
from supabase import create_client, Client, ClientOptions

# Load environment variables
load_dotenv("c:/Annie/finance/.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

if not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_JWT_SECRET:
    raise ValueError("Missing SUPABASE_URL, SUPABASE_KEY, or SUPABASE_JWT_SECRET in environment variables.")

try:
    PROJECT_REF = SUPABASE_URL.split("//")[1].split(".")[0]
except Exception:
    PROJECT_REF = "xtlnzfugqfbywgdofmvv"

def get_service_client() -> Client:
    now_ts = int(time.time())
    payload = {
        "iss": "supabase",
        "ref": PROJECT_REF,
        "role": "service_role",
        "iat": now_ts,
        "exp": now_ts + 3600
    }
    token = jwt.encode(payload, SUPABASE_JWT_SECRET, algorithm="HS256")
    options = ClientOptions(headers={"Authorization": f"Bearer {token}"})
    return create_client(SUPABASE_URL, SUPABASE_KEY, options=options)

supabase_admin = get_service_client()

# --- DATABASE HELPER FUNCTIONS ---

def get_user(phone_number: str):
    res = supabase_admin.table("users").select("*").eq("phone_number", phone_number).execute()
    return res.data[0] if res.data else None

def create_user(phone_number: str, savings_goal_amount: float, savings_goal_deadline: str, onboarding_status: str = "ONBOARDED"):
    res = supabase_admin.table("users").insert({
        "phone_number": phone_number,
        "savings_goal_amount": savings_goal_amount,
        "savings_goal_deadline": savings_goal_deadline,
        "onboarding_status": onboarding_status
    }).execute()
    return res.data[0] if res.data else None

def update_user_status(phone_number: str, onboarding_status: str):
    res = supabase_admin.table("users").update({"onboarding_status": onboarding_status}).eq("phone_number", phone_number).execute()
    return res.data[0] if res.data else None

def update_user_savings_goal(phone_number: str, amount: float, deadline: str):
    res = supabase_admin.table("users").update({"savings_goal_amount": amount, "savings_goal_deadline": deadline}).eq("phone_number", phone_number).execute()
    return res.data[0] if res.data else None

def set_mfa_code(phone_number: str, mfa_code: str, expires_at: float):
    res = supabase_admin.table("users").update({
        "mfa_code": mfa_code,
        "mfa_expires_at": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(expires_at))
    }).eq("phone_number", phone_number).execute()
    return res.data[0] if res.data else None

def delete_user_data(phone_number: str):
    supabase_admin.table("transactions").delete().eq("user_phone", phone_number).execute()
    supabase_admin.table("budgets").delete().eq("user_phone", phone_number).execute()
    supabase_admin.table("users").delete().eq("phone_number", phone_number).execute()

# --- BUDGET AUDIT & TRACKING ---

def update_budget_with_history(phone_number: str, category: str, new_limit: float, reason: str = "AI_REBALANCE"):
    current = supabase_admin.table("budgets").select("monthly_limit").eq("user_phone", phone_number).eq("category", category).single().execute().data
    old_limit = float(current.get("monthly_limit", 0))
    
    supabase_admin.table("budget_history").insert({
        "user_phone": phone_number,
        "category": category,
        "old_limit": old_limit,
        "new_limit": new_limit,
        "change_reason": reason
    }).execute()
    
    supabase_admin.table("budgets").update({"monthly_limit": new_limit}).eq("user_phone", phone_number).eq("category", category).execute()

def get_budgets(phone_number: str):
    res = supabase_admin.table("budgets").select("*").eq("user_phone", phone_number).execute()
    return res.data

def get_budget_by_category(phone_number: str, category: str):
    res = supabase_admin.table("budgets").select("*").eq("user_phone", phone_number).eq("category", category).execute()
    return res.data[0] if res.data else None

def create_budget(phone_number: str, category: str, monthly_limit: float, current_spent: float = 0.0):
    res = supabase_admin.table("budgets").insert({
        "user_phone": phone_number,
        "category": category,
        "monthly_limit": monthly_limit,
        "current_spent": current_spent
    }).execute()
    return res.data[0] if res.data else None

def update_budget(phone_number: str, category: str, current_spent: float = None, monthly_limit: float = None):
    updates = {}
    if current_spent is not None: updates["current_spent"] = current_spent
    if monthly_limit is not None: updates["monthly_limit"] = monthly_limit
    res = supabase_admin.table("budgets").update(updates).eq("user_phone", phone_number).eq("category", category).execute()
    return res.data[0] if res.data else None

# --- TRANSACTION FUNCTIONS ---

def create_transaction(phone_number: str, amount: float, category: str, merchant: str):
    res = supabase_admin.table("transactions").insert({
        "user_phone": phone_number,
        "amount": amount,
        "category": category,
        "merchant": merchant
    }).execute()
    return res.data[0] if res.data else None

def get_transactions(phone_number: str, limit: int = 50):
    res = supabase_admin.table("transactions").select("*").eq("user_phone", phone_number).order("timestamp", desc=True).limit(limit).execute()
    return res.data