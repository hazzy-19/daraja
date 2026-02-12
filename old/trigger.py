import requests
from requests.auth import HTTPBasicAuth
import base64
from datetime import datetime
import sys

# --- YOUR DATA GOES HERE ---
CONSUMER_KEY = "g52vwAS7XdGB4GfoyG96pKySAIGVWVtEH3KfDGzRUfJ4OTNz"
CONSUMER_SECRET = "4sNAd8QmBNoRSYbK9L5gCG1x6v429xB32YZboSEMaBApa7285GNak8MBW0MCp8Yz"
PHONE_NUMBER = "254718095685"

# IMPORTANT: Make sure this matches the URL in your 'tunnel.py' terminal!
CALLBACK_URL = "https://webhook.site/d791e9b3-6d1e-4b0a-ab10-2558f020058e"

# --- SAFARICOM DATA ---
BUSINESS_SHORT_CODE = "174379"
PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
URL_TOKEN = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
URL_STK = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"


def send_money():
    print("1. Generating Access Token...")
    try:
        res = requests.get(URL_TOKEN, auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET))
        res.raise_for_status()  # Check for errors
        access_token = res.json().get('access_token')
        print("   Token received!")
    except Exception as e:
        print(f"❌ Error getting token: {e}")
        return

    # 2. GENERATE PASSWORD
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password_str = BUSINESS_SHORT_CODE + PASSKEY + timestamp
    password_bytes = password_str.encode('ascii')
    password = base64.b64encode(password_bytes).decode('utf-8')

    # 3. PREPARE HEADERS (This was missing!)
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    # 4. PREPARE PAYLOAD
    payload = {
        "BusinessShortCode": BUSINESS_SHORT_CODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": 1,
        "PartyA": PHONE_NUMBER,
        "PartyB": BUSINESS_SHORT_CODE,
        "PhoneNumber": PHONE_NUMBER,
        "CallBackURL": CALLBACK_URL,
        "AccountReference": "AnyonaTracker",
        "TransactionDesc": "Test"
    }

    print(f"2. Sending request to {PHONE_NUMBER}...")
    print(f"📡 Callback URL: {CALLBACK_URL}")

    try:
        response = requests.post(URL_STK, headers=headers, json=payload, timeout=30)

        print("\n--- SAFARICOM RESPONSE ---")
        print(response.json())  # Print the JSON nicely

    except requests.exceptions.Timeout:
        print("❌ TIMEOUT: Safaricom didn't reply in 30 seconds.")
    except Exception as e:
        print(f"❌ ERROR: {e}")


if __name__ == "__main__":
    send_money()