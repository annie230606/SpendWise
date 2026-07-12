import json
import secrets
import time
from langgraph.graph import StateGraph, END
from agent.coach import apply_confirmed_budget
from agent.auditor import parse_and_process_message
from database.client import (
    get_user, create_user, update_user_status, set_mfa_code, delete_user_data, 
    get_budgets, update_user_savings_goal, create_budget
)

class AgentState(dict):
    phone_number: str
    message: str
    response_text: str = ""

# --- ONBOARDING NODES ---

def welcome_node(state: AgentState) -> AgentState:
    create_user(state["phone_number"], 0.0, "2026-12-31", "AWAITING_METHOD")
    return {**state, "response_text": (
        "Welcome to SpendWise! Your event-driven personal financial intelligence agent.\n\n"
        "Let's get you set up with your guardrails. Which onboarding path would you prefer?\n"
        "• Pathway A (The CSV Profiler): Upload a .csv bank statement.\n"
        "• Pathway B (Clean Slate Setup): Set up manually through a quick text-interview.\n\n"
        "Please reply with 'A' to upload your CSV, or 'B' to start the manual setup."
    )}

def onboarding_method_node(state: AgentState) -> AgentState:
    msg = state["message"].strip().upper()
    if msg == "A":
        update_user_status(state["phone_number"], "AWAITING_CSV")
        return {**state, "response_text": "Please upload your .csv file."}
    elif msg == "B":
        update_user_status(state["phone_number"], "AWAITING_GOAL")
        return {**state, "response_text": "Awesome! Let's start the interview.\n\nQuestion 1: What is your savings target this month? (e.g. 1000)"}
    return {**state, "response_text": "Please reply with 'A' or 'B'."}

def process_goal_node(state: AgentState) -> AgentState:
    try:
        update_user_savings_goal(state["phone_number"], float(state["message"]), "2026-12-31")
        update_user_status(state["phone_number"], "AWAITING_BUDGET")
        return {**state, "response_text": (
            f"Savings goal of ₹{float(state['message']):.1f} registered.\n\n"
            "Question 2: Please enter your monthly budget limits for our 4 supported categories:\n"
            "• Groceries\n• Dining Out\n• Shopping\n• Other\n\n"
            "Format: Category Amount, Category Amount\n(e.g., Groceries 3000, Dining Out 2000)"
        )}
    except:
        return {**state, "response_text": "Invalid amount. Please reply with a number for your savings target."}

def process_budget_node(state: AgentState) -> AgentState:
    try:
        parts = state["message"].split(",")
        for part in parts:
            cat, amt = part.strip().rsplit(" ", 1)
            create_budget(state["phone_number"], cat.strip(), float(amt))
        update_user_status(state["phone_number"], "ONBOARDED")
        return {**state, "response_text": "🚀 Onboarding complete! Your budget boundaries are locked in. From now on, any purchase will be automatically recorded."}
    except:
        return {**state, "response_text": "Formatting error. Please use: Groceries 300, Dining Out 200, Shopping 300, Other 200"}

# --- RESET NODES ---

def initiate_reset_node(state: AgentState) -> AgentState:
    code = str(secrets.randbelow(9000) + 1000)
    set_mfa_code(state["phone_number"], code, time.time() + 300)
    update_user_status(state["phone_number"], "AWAITING_MFA")
    
    # 1. Print the code to your Uvicorn terminal (Visible to you, not the user)
    print(f"\n🔑 [SECURITY] Reset Code for {state['phone_number']}: {code}\n")
    
    # 2. Keep the chat response generic
    return {**state, "response_text": (
        "⚠️ DESTRUCTIVE ACTION COMMAND DETECTED\n"
        "A verification code has been generated. Please check the terminal logs and reply with the 4-digit code to complete the deletion."
    )}

def verify_reset_node(state: AgentState) -> AgentState:
    user = get_user(state["phone_number"])
    if state["message"].strip() == user.get("mfa_code"):
        delete_user_data(state["phone_number"])
        return {**state, "response_text": "🗑️ Done. All budgets and history have been permanently deleted. Text me anything to restart fresh."}
    return {**state, "response_text": "Invalid code. Reset cancelled."}

# --- TRANSACTION NODES ---

def handle_transaction_node(state: AgentState) -> AgentState:
    result = parse_and_process_message(state["phone_number"], state["message"])
    # If it is NOT a danger/alert, return empty string for silence
    return {**state, "response_text": result.get("alert_msg", "")}

def handle_status_node(state: AgentState) -> AgentState:
    budgets = get_budgets(state["phone_number"])
    lines = ["📊 Available Spending Balance:"] + [f"{b['category']}: ₹{b['monthly_limit'] - b['current_spent']:.2f} left" for b in budgets]
    return {**state, "response_text": "\n".join(lines)}

def accept_balanced_plan_node(state: AgentState) -> AgentState:
    user = get_user(state["phone_number"])
    data = json.loads(user.get("pending_budget_json", "{}"))
    apply_confirmed_budget(state["phone_number"], data.get("proposed_limits"), data.get("breached_category"))
    return {**state, "response_text": "✅ Plan applied."}

# --- ROUTER ---

def route_decision(state: AgentState) -> str:
    user = get_user(state["phone_number"])
    if not user: return "welcome_node"
    
    msg = state["message"].strip().lower()
    if msg == "/reset-all-data": return "initiate_reset_node"
    
    status = user.get("onboarding_status")
    if status == "AWAITING_MFA": return "verify_reset_node"
    if status == "AWAITING_METHOD": return "onboarding_method_node"
    if status == "AWAITING_GOAL": return "process_goal_node"
    if status == "AWAITING_BUDGET": return "process_budget_node"
    
    if msg == "/status": return "handle_status_node"
    if msg == "confirm": return "accept_balanced_plan_node"
    return "handle_transaction_node"

# --- GRAPH SETUP ---

builder = StateGraph(AgentState)
nodes = {
    "welcome_node": welcome_node,
    "onboarding_method_node": onboarding_method_node,
    "process_goal_node": process_goal_node,
    "process_budget_node": process_budget_node,
    "initiate_reset_node": initiate_reset_node,
    "verify_reset_node": verify_reset_node,
    "handle_transaction_node": handle_transaction_node,
    "handle_status_node": handle_status_node,
    "accept_balanced_plan_node": accept_balanced_plan_node
}

for name, func in nodes.items(): builder.add_node(name, func)
builder.set_conditional_entry_point(route_decision, {name: name for name in nodes})
for name in nodes: builder.add_edge(name, END)

spendwise_graph = builder.compile()