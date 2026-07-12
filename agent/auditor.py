import io
import json
import re
from typing import Optional
import pandas as pd
from agent.coach import get_llm
from database.client import create_transaction, get_budgets

# ── Canonical category list ──────────────────────────────────────────────────
CATEGORIES = ["Groceries", "Dining Out", "Entertainment", "Shopping"]

# ── Rule-based keyword → category map (used by both extraction paths) ────────
RULE_MAPPINGS = {
    "Groceries": [
        "grocer", "safeway", "kroger", "costco", "walmart", "wal-mart", "target",
        "whole foods", "trader joe", "aldi", "supermarket", "food store",
        "milk", "vegetable",
    ],
    "Dining Out": [
        "zomato", "swiggy", "starbucks", "mcdonald", "burger", "restaurant", "cafe",
        "pizza", "bar", "pub", "grill", "coffee", "diner", "sushi", "uber eats",
        "doordash", "deliveroo", "eats", "eatery", "eat",
    ],
    "Entertainment": [
        "netflix", "spotify", "steam", "movie", "cinema", "concert", "ticket",
        "disney", "hulu", "nintendo", "playstation", "xbox", "theater", "show", "game",
    ],
    "Shopping": [
        "amazon", "nike", "zara", "clothing", "apparel", "shoes", "ebay", "online",
        "mall", "best buy", "apple", "nordstrom", "h&m", "retail", "flipkart", "shop", "buy",
    ],
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def fallback_categorize_by_text(text: str) -> str:
    """
    Rule-based categorisation against RULE_MAPPINGS.
    Returns 'Other' when no keyword matches.
    """
    text_lower = text.lower()
    for cat, keywords in RULE_MAPPINGS.items():
        if any(kw in text_lower for kw in keywords):
            return cat
    return "Other"


def _clean_json(raw: str) -> str:
    """Strip markdown fences and return the first JSON object/array found."""
    s = re.sub(r'\x60{3}(?:json)?\s*', '', raw, flags=re.IGNORECASE).strip()
    match = re.search(r'(\{.*\}|\[.*\])', s, re.DOTALL)
    return match.group(1).strip() if match else s


# ── Core extraction ──────────────────────────────────────────────────────────

def _categorize_merchant(merchant_text: str) -> Optional[str]:
    """
    Given a merchant name (or any relevant text), attempt rule-based categorisation.
    Returns None if no rule matches.
    """
    text_lower = merchant_text.lower()
    for cat, keywords in RULE_MAPPINGS.items():
        if any(kw in text_lower for kw in keywords):
            return cat
    return None


def _llm_categorize(merchant: str) -> Optional[str]:
    """
    Ask the LLM to categorise a merchant name.
    Returns None if the LLM is unavailable or returns an invalid category.
    """
    llm = get_llm()
    if not llm:
        print("[AUDITOR DEBUG] LLM instance not available.")
        return None

    system_prompt = (
        "You are the Auditor Agent. Given a merchant name, return ONLY valid JSON with a single key 'category'. "
        f"The category must be one of: {CATEGORIES}. "
        "Use your internal knowledge of the merchant to intelligently assign the most appropriate category. "
        "For example: 'Zomato' → 'Dining Out', 'Zara' → 'Shopping', 'Netflix' → 'Entertainment'. "
        "Do not include any explanation or extra text."
    )
    prompt = f"<|system|>\n{system_prompt}\n<|user|>\nMerchant: '{merchant}'\n<|assistant|>\n"

    try:
        response = llm(prompt, max_tokens=60, temperature=0.0, stop=["<|end|>", "\n<|"])
        raw = response["choices"][0]["text"]
        print(f"[AUDITOR DEBUG] LLM raw output: {raw}")
        parsed = json.loads(_clean_json(raw))
        cat = parsed.get("category")
        if cat in CATEGORIES:
            return cat
        print(f"[AUDITOR DEBUG] LLM returned invalid category: '{cat}'")
    except Exception as e:
        print(f"[AUDITOR DEBUG] LLM categorisation failed: {e}")
    return None


# ── Public API ───────────────────────────────────────────────────────────────

def parse_and_process_message(phone_number: str, message: str) -> dict:
    """
    Compatibility entry point for graph.py's conversational WhatsApp flow.
    Parses a free-form transaction message to extract amount and merchant,
    then delegates to process_transaction (the single DB-write source of truth).
    """
    print(f"[AUDITOR DEBUG] parse_and_process_message: '{message}'")

    # Extract amount
    amount_match = re.search(r'(?:[\$₹]|rs\.?)\s*([\d,]+(?:\.\d+)?)', message, re.IGNORECASE)
    if amount_match:
        amount = float(amount_match.group(1).replace(',', ''))
    else:
        nums = re.findall(r'\d+(?:\.\d+)?', message)
        amount = float(next((n for n in nums if len(n) < 7), 0))

    # Extract merchant from patterns like 'to/at <Merchant>'
    merchant_match = re.search(
        r'\b(?:to|at|paid to|spent at)\s+([A-Za-z][A-Za-z0-9\s\-&\'\.]{1,30}?)(?:\s+(?:on|for|from|via|using|through|in|by)|[.,!?\n]|$)',
        message,
        re.IGNORECASE,
    )
    if merchant_match:
        candidate = merchant_match.group(1).strip()
        merchant = candidate if (candidate and not re.match(r'^\+?[\d\s\-()]+$', candidate)) else "Unknown"
    else:
        merchant = "Unknown"

    return process_transaction(phone_number=phone_number, amount=amount, merchant=merchant, body=message)


def process_transaction(phone_number: str, amount: float, merchant: str, body: str = "") -> dict:
    """
    Definitive source for database persistence.

    1. Determines the category using a 3-stage fallback:
       a. Rule-based match on merchant name.
       b. Rule-based match on full SMS body (catches 'groceries' in body text).
       c. LLM categorisation of merchant name.
       d. Hard fallback to 'Other'.
    2. Calls create_transaction EXACTLY ONCE.
    3. Returns a dict with 'extracted_data' (amount, category, merchant) for the caller.
    """
    print(f"[AUDITOR DEBUG] process_transaction called → phone={phone_number}, amount={amount}, merchant='{merchant}', body='{body}'")

    # Stage a: rule-based on merchant name
    category = _categorize_merchant(merchant)

    # Stage b: rule-based on the full SMS body (handles 'groceries' appearing in context)
    if not category and body:
        category = _categorize_merchant(body)
        if category:
            print(f"[AUDITOR DEBUG] Body-text rule match → {category}")

    # Stage c: LLM on merchant name (only if merchant is meaningful)
    if not category and merchant and merchant.lower() not in ("unknown", "bank alert", ""):
        print(f"[AUDITOR DEBUG] Rule-based failed. Trying LLM for merchant '{merchant}'...")
        category = _llm_categorize(merchant)

    # Stage d: hard fallback
    if not category:
        print(f"[AUDITOR DEBUG] All categorisation stages failed — defaulting to 'Other'.")
        category = "Other"

    print(f"[AUDITOR DEBUG] Final → category={category}, merchant={merchant}, amount={amount}")

    # Persist to database (single write)
    create_transaction(phone_number, amount, category, merchant)
    print(f"[AUDITOR DEBUG] ✅ Transaction saved to database.")

    # Check against budget limits
    budgets = get_budgets(phone_number)
    budget = next((b for b in budgets if b["category"] == category), None)

    extracted_data = {"amount": amount, "category": category, "merchant": merchant}

    if budget:
        available = budget["monthly_limit"] - budget["current_spent"]
        if amount > available:
            return {
                "is_danger": True,
                "alert_msg": (
                    f"⚠️ Alert: Your {category} budget is low. "
                    f"This spend of ₹{amount} exceeds your remaining ₹{available:.2f}."
                ),
                "extracted_data": extracted_data,
            }

    return {"is_danger": False, "alert_msg": "", "extracted_data": extracted_data}


# ── Legacy / CSV helpers (unchanged) ────────────────────────────────────────

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
            except Exception:
                pass

        def categorize(desc):
            for cat, keywords in RULE_MAPPINGS.items():
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