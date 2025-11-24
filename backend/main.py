from fastapi import FastAPI, Request, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from models import User, Transaction, Subscription
from nlp_engine import parse_expense
from utils import send_message, send_image, generate_pie_chart
import os
from datetime import datetime, timedelta

app = FastAPI()

# --- Startup ---
@app.on_event("startup")
async def start_db():
    client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
    await init_beanie(database=client.finance_bot, document_models=[User, Transaction, Subscription])

# --- Webhook Verification ---
@app.get("/webhook")
async def verify_webhook(request: Request):
    verify_token = os.getenv("VERIFY_TOKEN")
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == verify_token:
            return int(challenge)
        else:
            raise HTTPException(status_code=403, detail="Verification failed")
    return {"status": "ok"}

# --- Message Handling ---
@app.post("/webhook")
async def handle_message(request: Request):
    body = await request.json()
    
    if body.get("object") == "page":
        for entry in body.get("entry", []):
            for event in entry.get("messaging", []):
                if "message" in event and 'text' in event["message"]:
                    await process_user_message(event)
    return {"status": "received"}

async def process_user_message(event):
    psid = event["sender"]["id"]
    text = event["message"].get("text", "").strip()
    
    # Make sure user exits
    user = await User.find_one(User.psid == psid)
    if not user:
        user = User(psid=psid)
        await user.insert()
        send_message(psid, "Chao! Type 'Help' for commands.")
    
    # Hardcoded commands
    cmd = text.lower()

    if cmd == "report":
        await send_weekly_report(psid)
        return
    
    if cmd == "reset":
        await Transaction.find(Transaction.psid == psid).delete()
        await Subscription.find(Subscription.psid == psid).delete()
        user.weekly_limit = 0.0
        await user.save()
        send_message(psid, "All your data has been reset.")
        return

    if cmd == "undo":
        last_tx = await Transaction.find(Transaction.psid == psid).sort("-date").first_or_none()
        if last_tx:
            await last_tx.delete()
            send_message(psid, f"Last transaction '{last_tx.item_name} (${last_tx.amount})' has been removed.") 
            await check_budget_alert(psid, user.weekly_limit)
        else:
            send_message(psid, "No transactions found to undo.")
        return
    
    if cmd == "help":
        msg = (
            "Commands:\n"
            "- 'KFC 10': Log expense\n"
            "- 'Set limit 500': Set weekly limit\n"
            "- 'Add sub Netflix 15': Add subscription\n"
            "- 'Report': Get monthly report\n"
            "- 'Reset': Clear all data\n"
            "- 'Undo': Remove last item\n"
        )
        send_message(psid, msg)
        return

    # Send to NLP to analyze
    data = await parse_expense(text) # return JSON
    
    if not data:
        send_message(psid, "Sorry, I didn't catch that. Try: 'Taxi 10$'.")
        return

    msg_type = data.get("type", "expense")

    # Handle different types of inputs
    if msg_type == "set_limit":
        user.weekly_limit = float(data["amount"])
        await user.save()
        send_message(psid, f"Weekly limit set to ${user.weekly_limit}")
        await check_budget_alert(psid, user.weekly_limit)

    elif msg_type == "add_sub":
        amount = float(data["amount"])
        sub = Subscription(
            psid=psid,
            service_name=data.get("item", "Unknown"),
            amount=amount,
            next_billing_date=datetime.now() + timedelta(days=30)
        )
        await sub.insert()

        await Transaction(
            psid=psid,
            amount=amount,
            category="Subscription",
            item_name=data.get("item", "Unknown") + "(1st month)"
        ).insert()

        send_message(psid, f"Subscription added: {sub.service_name} (${sub.amount}/mo)")

    else: # Default to expense logging
        amount = float(data["amount"])
        
        # Save transaction
        await Transaction(
            psid=psid,
            amount=amount,
            category=data.get("category", "General"),
            item_name=data.get("item", "Unknown")
        ).insert()

        # Respond to user
        send_message(psid, f"Logged: {data.get('item')} (${amount}) - {data.get('category')}")

        # Check alert
        if user.weekly_limit > 0:
            await check_budget_alert(psid, user.weekly_limit)

async def check_budget_alert(psid, limit):
    # Find total transactions this week
    today = datetime.now()
    start_week = today - timedelta(days=today.weekday()) # Monday
    start_week = start_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    txs = await Transaction.find(
        Transaction.psid == psid,
        Transaction.date >= start_week
    ).to_list()
    
    total = sum(t.amount for t in txs)
    
    if total > limit:
        over_amount = total - limit
        send_message(psid, f"ALERT: You've spent ${total}, exceeding your limit of ${limit} by ${over_amount}!")

async def send_weekly_report(psid):
    # Get first day of current month
    today = datetime.now()
    start_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    txs = await Transaction.find(
        Transaction.psid == psid,
        Transaction.date >= start_month
    ).to_list()
    
    if not txs:
        send_message(psid, "No data found for this month.")
        return

    # Group by category
    cat_data = {}
    total = 0
    for t in txs:
        total += t.amount
        cat_data[t.category] = cat_data.get(t.category, 0) + t.amount

    # Send text report
    msg = f" Monthly Report ({today.strftime('%B')}):\nTotal: ${total:.2f}\n"
    for k, v in cat_data.items():
        msg += f"- {k}: ${v:.2f}\n"
    send_message(psid, msg)

    try:
        img_buf = generate_pie_chart(cat_data)
        send_image(psid, img_buf)
    except Exception as e:
        print(f"Chart Error: {e}")