from flask import Flask, request, jsonify
import re
import sys
import os
from typing import Optional
import requests as http_requests
from dotenv import load_dotenv

# 📂 Ensure Python can find your project modules relative to this file
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 📁 Load environment variables portably from your project root folder
load_dotenv()

app = Flask(__name__)

# 🔗 Internal endpoint on the FastAPI server (single source of truth for audit + DB write)
SMS_ALERT_ENDPOINT = "http://127.0.0.1:8000/sms-alert"

# 🔗 LangGraph conversational orchestrator — receives ALL incoming WhatsApp messages
WHATSAPP_WEBHOOK_ENDPOINT = "http://127.0.0.1:8000/webhook"

# 🛡️ Retrieve the shared-secret handshake token for secure internal communication
SMS_ALERT_SECRET = os.getenv("SMS_ALERT_SECRET")

# Hardcoded user phone number
CLEAN_PHONE = "+918657979055"

# ---------------------------------------------------------------------------
# Known bank identifier keywords → clean display name.
# ---------------------------------------------------------------------------
BANK_KEYWORDS = {
    "kotak": "Kotak Bank",
    "hdfc": "HDFC Bank",
    "sbi": "SBI",
    "icici": "ICICI Bank",
    "axis": "Axis Bank",
    "pnb": "PNB",
    "yes bank": "Yes Bank",
    "idbi": "IDBI Bank",
    "canara": "Canara Bank",
    "paytm": "Paytm",
    "gpay": "Google Pay",
    "phonepe": "PhonePe",
}

# Placeholder values that phone apps sometimes inject instead of a real sender
SENDER_PLACEHOLDERS = {"{phone}", "phone", "unknown", "null", "none", ""}


def resolve_sender(sms_sender: str, sms_body: str) -> str:
    """
    Safeguard against apps that pass a literal '{phone}' template string,
    or other meaningless placeholder values, as the SMS sender.
    """
    cleaned = sms_sender.strip() if sms_sender else ""

    # Detect unresolved template braces (e.g. "{phone}") or known placeholders
    is_placeholder = (
        cleaned.lower() in SENDER_PLACEHOLDERS
        or "{" in cleaned
        or "}" in cleaned
    )

    if not is_placeholder:
        return cleaned  # Sender looks legitimate — trust it

    # Try to identify the bank from the message body
    body_lower = sms_body.lower()
    for keyword, bank_name in BANK_KEYWORDS.items():
        if keyword in body_lower:
            print(f"🏦 Resolved placeholder sender → '{bank_name}' (matched keyword '{keyword}' in body)")
            return bank_name

    print("⚠️  Could not resolve sender from body — defaulting to 'Bank Alert'")
    return "Bank Alert"


def extract_amount(sms_body: str) -> Optional[float]:
    """Extract a transaction amount from an SMS body using regex."""
    match = re.search(r'(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d{1,2})?)', sms_body, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(',', ''))
    return None


def extract_merchant(sms_body: str) -> Optional[str]:
    """
    Extract the recipient/merchant name from patterns like:
      'Sent Rs 230 to Zara'
      'Paid Rs 500 at McDonald's'
      'Debited Rs 100 from your account to Amazon'
    Returns None if no merchant name is found.
    """
    # Match 'to <Merchant>' or 'at <Merchant>' — stop at sentence-ending punctuation or common prepositions
    merchant_match = re.search(
        r'\b(?:to|at|paid to|spent at)\s+([A-Za-z][A-Za-z0-9\s\-&\'\.]{1,30}?)(?:\s+(?:on|for|from|via|using|through|in|by)|[.,!?\n]|$)',
        sms_body,
        re.IGNORECASE
    )
    if merchant_match:
        candidate = merchant_match.group(1).strip()
        # Reject if the "merchant" looks like a phone number
        if candidate and not re.match(r'^\+?[\d\s\-()]+$', candidate):
            return candidate
    return None


@app.route('/sms', methods=['POST'])
def receive_sms():
    # 🛠️ CHECK: Detect whether incoming data is form-encoded (Twilio) or JSON (curl/Postman)
    raw_sender = None
    sms_body = None

    if request.form:
        raw_sender = request.form.get('From', '')
        sms_body = request.form.get('Body', '')
    else:
        data = request.json or {}
        raw_sender = data.get('from', '')
        sms_body = data.get('body', '')

    if not sms_body:
        return jsonify({"status": "error", "message": "No message body detected"}), 400

    # Parse out sender metadata if embedded in the body
    if sms_body and "From :" in sms_body:
        raw_sender = sms_body.split("From :")[1].split("\n")[0].strip()
    else:
        raw_sender = raw_sender.replace("whatsapp:", "").strip() if raw_sender else ""

    # Resolve the sender display name, guarding against placeholder text
    sms_sender = resolve_sender(raw_sender, sms_body)

    print(f"\n📱 NEW MESSAGE RECEIVED VIA GATEWAY")
    print(f"👤 Account Holder: {CLEAN_PHONE}")
    print(f"🏛️  Resolved Sender: {sms_sender} (raw='{raw_sender}')")
    print(f"💬 Message Body: {sms_body}")

    # ── Transaction branch: only fires when a debit keyword is present ────────
    if any(kw in sms_body.lower() for kw in ["sent", "debited", "spent", "txn"]):
        print("💳 Transaction keyword detected — parsing details...")

        amount = extract_amount(sms_body)

        if amount is None:
            print("⚠️  Amount regex found no match. Skipping.")
            print("-" * 50)
            return jsonify({"status": "skipped", "reason": "no_amount"}), 200

        # Extract merchant name purely from the SMS body — NEVER use the sender phone number
        merchant = extract_merchant(sms_body) or ""

        print(f"💰 Amount  : ₹{amount}")
        print(f"🏪 Merchant: {merchant}")

        # POST to the FastAPI auditor — it is the ONLY place that writes to the DB
        try:
            payload = {
                "phone_number": CLEAN_PHONE,
                "amount": amount,
                "merchant": merchant,
                "body": sms_body,   # raw text for body-level keyword categorisation
            }
            headers = {"X-Internal-Token": SMS_ALERT_SECRET}
            resp = http_requests.post(
                SMS_ALERT_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=120,
            )

            if resp.ok:
                print(f"✅ /sms-alert accepted: {resp.json()}")
            else:
                print(f"⚠️  /sms-alert returned HTTP {resp.status_code}: {resp.text}")

        except Exception as e:
            print(f"⚠️  Could not reach /sms-alert: {e}")

        print("-" * 50)
        return jsonify({"status": "success"}), 200

    # ── Conversational branch: forward to LangGraph orchestrator ─────────────
    else:
        print("🔀 Forwarding message to LangGraph orchestrator...")
        try:
            webhook_payload = {
                "From": f"whatsapp:{CLEAN_PHONE}",
                "Body": sms_body,
                "sender_name": sms_sender,
            }
            headers = {"X-Internal-Token": SMS_ALERT_SECRET}
            resp = http_requests.post(
                WHATSAPP_WEBHOOK_ENDPOINT,
                data=webhook_payload,
                headers=headers,
                timeout=45,
            )

            if resp.ok:
                print(f"✅ LangGraph responded: HTTP {resp.status_code}")
                return resp.text, 200, {'Content-Type': 'application/xml'}
            else:
                print(f"⚠️  /webhook returned HTTP {resp.status_code}: {resp.text}")
                return jsonify({"status": "error", "message": "Backend engine failure"}), resp.status_code

        except Exception as e:
            print(f"⚠️  Could not reach /webhook endpoint: {e}")
            return jsonify({"status": "error", "message": "Backend engine offline"}), 500


if __name__ == '__main__':
    print("🚀 Local SMS Gateway Server Starting...")
    print(f"🔗 Transactions will POST to: {SMS_ALERT_ENDPOINT}")

    if not SMS_ALERT_SECRET:
        print("🛑 WARNING: 'SMS_ALERT_SECRET' is missing from your .env file! Submissions will fail authentication.")

    print("📍 Listening on port 5000... (Press Ctrl+C to stop)")
    app.run(host='0.0.0.0', port=5000, debug=False)