import warnings
import sys
import os
import asyncio
import secrets as _secrets
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request, HTTPException, Response, Depends, BackgroundTasks
from twilio.request_validator import RequestValidator
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

# Silence the LangChain deprecation warning
warnings.filterwarnings("ignore", category=UserWarning, module="langgraph.checkpoint.serde.jsonplus")

load_dotenv()

from agent.graph import spendwise_graph

app = FastAPI(title="SpendWise Webhook API", version="1.0.0")

_graph_executor = ThreadPoolExecutor(max_workers=4)

TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
DISABLE_TWILIO_SIGNATURE = os.getenv("DISABLE_TWILIO_SIGNATURE", "false").lower() == "true"
validator = RequestValidator(TWILIO_AUTH_TOKEN) if TWILIO_AUTH_TOKEN else None


async def verify_twilio_request(request: Request):
    if DISABLE_TWILIO_SIGNATURE or not validator:
        return True
    signature = request.headers.get("X-Twilio-Signature", "")
    x_forwarded_proto = request.headers.get("X-Forwarded-Proto", "https")
    x_forwarded_host = request.headers.get("X-Forwarded-Host", request.headers.get("Host", "localhost:8000"))
    url = f"{x_forwarded_proto}://{x_forwarded_host}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
    form_params = await request.form()
    if not validator.validate(url, dict(form_params), signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio Signature.")
    return True


@app.post("/webhook")
async def webhook(request: Request, verified: bool = Depends(verify_twilio_request)):
    form_data = await request.form()
    phone_number = form_data.get("From", "").replace("whatsapp:", "").strip()
    body = form_data.get("Body", "").strip()

    state_input = {"phone_number": phone_number, "message": body, "response_text": ""}
    try:
        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(_graph_executor, spendwise_graph.invoke, state_input)
        resp = MessagingResponse()
        msg_text = output.get("response_text")
        if msg_text and msg_text.strip():
            resp.message(msg_text)
        return Response(content=str(resp), media_type="application/xml")
    except Exception as e:
        resp = MessagingResponse()
        resp.message(f"⚠️ System Error: {str(e)}")
        return Response(content=str(resp), media_type="application/xml")


def _run_coach_pipeline(phone_number: str, amount: float, category: str, merchant: str):
    """
    Background task: passes the auditor-validated data to the Coach agent.
    The DB write has already happened in process_transaction; this only handles coaching/alerts.
    """
    from agent.coach import process_automated_transaction

    print(f"🤖 [Background Agent] Running coach pipeline for ₹{amount} | {merchant} | {category}...")
    try:
        result = process_automated_transaction(phone_number, amount, category, merchant)

        whatsapp_msg = None
        if result.get("is_flagged", False) or result.get("alert", False):
            whatsapp_msg = result.get("coaching_message") or result.get("whatsapp_suggestion")

        if whatsapp_msg:
            TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
            TWILIO_AUTH_TOKEN_VAL = os.getenv("TWILIO_AUTH_TOKEN")
            TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

            if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN_VAL:
                twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN_VAL)
                twilio_client.messages.create(
                    from_=TWILIO_WHATSAPP_NUMBER,
                    to=f"whatsapp:{phone_number}",
                    body=whatsapp_msg,
                )
                print(f"🚨 [Background Agent] Alert dispatched to {phone_number}!")
    except Exception as e:
        print(f"❌ [Background Agent] Coach pipeline error: {e}")


@app.post("/sms-alert")
async def sms_alert(request: Request, background_tasks: BackgroundTasks):
    """
    Receives JSON from listen_sms.py with phone_number, amount, and merchant.
    Calls process_transaction (the single source of truth for DB writes + categorization),
    then hands the validated data off to the Coach via BackgroundTasks.
    """
    _sms_secret = os.getenv("SMS_ALERT_SECRET")
    if _sms_secret:
        token = request.headers.get("X-Internal-Token", "")
        if not _secrets.compare_digest(token, _sms_secret):
            raise HTTPException(status_code=403, detail="Forbidden")

    data = await request.json()
    phone_number = data.get("phone_number", "").strip()
    amount = float(data.get("amount", 0))
    merchant = data.get("merchant", "").strip()
    body = data.get("body", "").strip()  # raw SMS text for body-level categorisation

    if not phone_number or amount <= 0:
        raise HTTPException(status_code=422, detail="phone_number and a positive amount are required.")

    # Step 1: Audit + persist (single DB write, returns validated category/merchant/amount)
    from agent.auditor import process_transaction
    audit_result = process_transaction(
        phone_number=phone_number,
        amount=amount,
        merchant=merchant,
        body=body,
    )

    validated = audit_result.get("extracted_data", {})
    final_category = validated.get("category", "Other")
    final_merchant = validated.get("merchant") or merchant
    final_amount = validated.get("amount") or amount

    print(f"📊 [Webhook] Audit complete → category={final_category}, merchant={final_merchant}, amount=₹{final_amount}")

    # Step 2: Hand off to Coach in the background (no second DB write)
    loop = asyncio.get_event_loop()
    background_tasks.add_task(
        lambda: loop.run_in_executor(
            _graph_executor,
            _run_coach_pipeline,
            phone_number,
            final_amount,
            final_category,
            final_merchant,
        )
    )

    return {"status": "processing", "category": final_category, "merchant": final_merchant, "amount": final_amount}


@app.get("/health")
def health():
    return {"status": "ok", "app": "SpendWise"}