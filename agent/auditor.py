import io
import json
import re
import pandas as pd
from agent.coach import get_llm
from database.client import create_transaction, get_budgets

# Define strict categories
CATEGORIES = ["Groceries", "Dining Out", "Entertainment", "Shopping"]

# --- NEW FUNCTION REQUIRED BY GRAPH.PY ---
def process_transaction(phone_number: str, message: str) -> dict:
    """
    Parses message, saves to DB, and checks budget limits for alerts.
    """
    # 1. Extract details using your existing logic
    data = extract_transaction_entities(message)
    
    # If extraction fails or data is incomplete, return silent result
    if not data.get("amount") or not data.get("category"):
        return {"is_danger": False, "alert_msg": ""}

    # 2. Save to database
    create_transaction(phone_number, data["amount"], data["category"], data["merchant"])
    
    # 3. Check against budget for "danger"
    budgets = get_budgets(phone_number)
    budget = next((b for b in budgets if b["category"] == data["category"]), None)
    
    if budget:
        available = budget["monthly_limit"] - budget["current_spent"]
        # If the purchase exceeds the remaining balance, trigger alert
        if data["amount"] > available:
            return {
                "is_danger": True, 
                "alert_msg": f"⚠️ Alert: Your {data['category']} budget is low. This spend of ₹{data['amount']} exceeds your remaining ₹{available:.2f}."
            }
            
    # 4. Return silent result if safe
    return {"is_danger": False, "alert_msg": ""}

# --- EXISTING CODE REMAINS UNCHANGED ---

def _clean_json(raw: str) -> str:
    """Strip markdown fences and extract the first {...} block."""
    s = re.sub(r'\x60{3}(?:json)?\s*', '', raw, flags=re.IGNORECASE).strip()
    match = re.search(r'(\{.*\}|\[.*\])', s, re.DOTALL)
    return match.group(1).strip() if match else s

def extract_transaction_entities(message_body: str) -> dict:
    """Uses the shared in-process LLM engine to extract transaction details."""
    llm = get_llm()
    if not llm:
        return {"amount": None, "category": None, "merchant": None}

    system_prompt = f"""
    You are the Auditor Agent for SpendWise, a personal finance assistant.
    Your job is to parse unstructured text messages about financial transactions and extract:
    1. The transaction amount (as a float).
    2. The category, which must be strictly one of these four: {CATEGORIES}.
    3. The merchant name.

    Category Mapping Rules:
    - Groceries: Grocery stores, supermarkets, wholesale clubs (e.g., Costco, Safeway, Trader Joes, Whole Foods).
    - Dining Out: Restaurants, cafes, coffee shops, bars, fast food, food delivery (e.g., Starbucks, McDonald's, UberEats, local diners).
    - Entertainment: Movies, streaming services, games, events, tickets (e.g., Netflix, Spotify, cinemas, concerts, Steam).
    - Shopping: Retail purchases, clothing, electronics, online shopping (e.g., Nike, Amazon, Zara, Best Buy).

    Return ONLY a raw, valid JSON object with keys: "amount", "category", "merchant".
    If a field is missing, set its value to null. 
    """
    
    formatted_prompt = f"<|system|>\n{system_prompt}\n<|user|>\nParse this: '{message_body}'\n<|assistant|>\n"
    
    try:
        response = llm(
            formatted_prompt,
            max_tokens=200,
            temperature=0.0,
            stop=["<|end|>", "\n<|"]
        )
        
        raw_content = response["choices"][0]["text"].strip()
        result = json.loads(_clean_json(raw_content))
        
        category = result.get("category")
        if category and category not in CATEGORIES:
            matched = [c for c in CATEGORIES if c.lower() == str(category).lower()]
            result["category"] = matched[0] if matched else None
            
        return result
    except Exception as e:
        print(f"Error in extract_transaction_entities: {e}")
        return {"amount": None, "category": None, "merchant": None}

def process_bank_statement_csv(csv_content_bytes: bytes) -> dict:
    """Cleans uploaded bank statement CSV using Pandas."""
    try:
        df = pd.read_csv(io.BytesIO(csv_content_bytes))
        df.columns = [c.lower().strip() for c in df.columns]
        
        amount_col = next((col for col in df.columns if "amount" in col or "charge" in col), None)
        desc_col = next((col for col in df.columns if "desc" in col or "merchant" in col or "payee" in col), None)
        date_col = next((col for col in df.columns if "date" in col or "time" in col), None)
            
        if not amount_col or not desc_col:
            raise ValueError("Could not identify critical CSV columns.")
            
        df[amount_col] = df[amount_col].astype(str).str.replace(r'[^\d.-]', '', regex=True)
        df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
        df = df.dropna(subset=[amount_col])
        df[desc_col] = df[desc_col].astype(str).str.lower().str.strip()
        
        total_months = 1.0
        if date_col:
            try:
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                df = df.dropna(subset=[date_col])
                if len(df) > 1:
                    days = (df[date_col].max() - df[date_col].min()).days
                    total_months = max(1.0, days / 30.4)
            except Exception: pass
                
        mappings = {
            "Groceries": ["grocer", "safeway", "kroger", "costco", "walmart", "wal-mart", "target", "whole foods", "trader joe", "aldi", "supermarket", "food store"],
            "Dining Out": ["starbucks", "mcdonald", "burger", "restaurant", "cafe", "pizza", "bar", "pub", "grill", "coffee", "diner", "sushi", "uber eats", "doordash", "deliveroo", "eats", "eatery"],
            "Entertainment": ["netflix", "spotify", "steam", "movie", "cinema", "concert", "ticket", "disney", "hulu", "nintendo", "playstation", "xbox", "theater", "show", "game"],
            "Shopping": ["amazon", "nike", "zara", "clothing", "apparel", "shoes", "ebay", "online", "mall", "best buy", "apple", "nordstrom", "h&m", "retail"]
        }
        
        def categorize(desc):
            for cat, keywords in mappings.items():
                if any(kw in desc for kw in keywords):
                    return cat
            return None
            
        df["mapped_category"] = df[desc_col].apply(categorize)
        grouped = df.groupby("mapped_category")[amount_col].sum()
        
        averages = {}
        for cat in CATEGORIES:
            total_spent = grouped.get(cat, 0.0)
            averages[cat] = round(abs(float(total_spent)) / total_months, 2)
            
        return averages
    except Exception as e:
        print(f"Error processing CSV: {e}")
        raise ValueError(f"CSV processing failed: {str(e)}")