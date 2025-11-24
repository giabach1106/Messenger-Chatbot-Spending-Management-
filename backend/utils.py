import os
import requests
import matplotlib.pyplot as plt
import io

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")

def send_message(psid, text):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": psid},
        "message": {"text": text}
    }
    try:
        r = requests.post(url, json=payload)
        print(f"Sent Msg: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Error sending msg: {e}")

def send_image(psid, image_buffer):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    
    # Facebook requires specific multipart/form-data 
    payload = {
        'recipient': f'{{"id":"{psid}"}}',
        'message': '{"attachment":{"type":"image", "payload":{}}}'
    }
    files = {
        'filedata': ('chart.png', image_buffer, 'image/png')
    }
    try:
        requests.post(url, data=payload, files=files)
    except Exception as e:
        print(f"Error sending image: {e}")

def generate_pie_chart(data_dict):
    labels = list(data_dict.keys())
    sizes = list(data_dict.values())

    # Avoid conflict thread
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140)
    ax.axis('equal')
    
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig) 
    return buf