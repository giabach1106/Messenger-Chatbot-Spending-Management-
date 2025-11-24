from openai import OpenAI
import os
import json
from datetime import datetime

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def parse_expense(text: str):
    prompt = f"""
    Analyze text: "{text}".
    Extract: item_name, amount, currency (default USD).
    Infer category from: [Food/Dining, Living/Utilities, Transport, Shopping, Entertainment, Health, Special Occasion, Subscription].
    
    Rules:
    1. If limit setting (e.g. "Limit 500", "Budget 200"), type="set_limit".
    2. If subscription (e.g. "Add sub Netflix 15", "Sub Adobe 10"), type="add_sub".
    3. Else type="expense".
    
    Output JSON only. Example: {{"type": "expense", "item": "kfc", "amount": 30, "currency": "USD", "category": "Food/Dining"}}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a financial assistant API that outputs strict JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"NLP Error: {e}")
        return None