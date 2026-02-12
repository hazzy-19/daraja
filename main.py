import requests
from requests.auth import HTTPBasicAuth
import base64
from datetime import datetime
import time
import os
from dotenv import load_dotenv
from database import save_transaction  # <--- Importing your DB file!

# Load secrets
load_dotenv()


class AnyonaTracker:
    def __init__(self):
        self.consumer_key = os.getenv("CONSUMER_KEY")
        self.consumer_secret = os.getenv("CONSUMER_SECRET")
        self.shortcode = "174379"
        self.passkey = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
        self.base_url = "https://sandbox.safaricom.co.ke"

    def get_token(self):
        res = requests.get(
            f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials",
            auth=HTTPBasicAuth(self.consumer_key, self.consumer_secret)
        )
        return res.json().get('access_token')

    def trigger_payment(self, name, phone, amount):
        token = self.get_token()
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode((self.shortcode + self.passkey + timestamp).encode()).decode()

        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

        # 1. SEND REQUEST
        print(f"🚀 Sending request to {name} ({phone})...")
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": self.shortcode,
            "PhoneNumber": phone,
            "CallBackURL": "https://example.com",
            "AccountReference": "AnyonaTracker",
            "TransactionDesc": "Fee"
        }

        res = requests.post(f"{self.base_url}/mpesa/stkpush/v1/processrequest", headers=headers, json=payload)
        data = res.json()

        if data.get('ResponseCode') != "0":
            print(f"❌ Error: {data.get('errorMessage')}")
            return

        checkout_id = data['CheckoutRequestID']
        print("✅ Check your phone and enter PIN!")

        # 2. WAIT AND CHECK (POLLING)
        self.check_status(headers, password, timestamp, checkout_id, name, phone, amount)

    def check_status(self, headers, password, timestamp, checkout_id, name, phone, amount):
        """Asks Safaricom 'Did they pay?' every 5 seconds"""
        for i in range(5):
            print(f"🔎 Checking status... ({i + 1}/5)")
            time.sleep(5)

            query_payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_id
            }

            res = requests.post(f"{self.base_url}/mpesa/stkpushquery/v1/query", headers=headers, json=query_payload)
            data = res.json()

            # --- HANDLE RESULTS ---
            if data.get('ResultCode') == "0":
                print("🎉 SUCCESS! Payment Received.")
                # SAVE TO DB
                save_transaction(name, phone, amount, "RECEIPT_MISSING_IN_SANDBOX", "Success")
                return

            elif data.get('ResultCode') == "1032":
                print("❌ User Cancelled.")
                save_transaction(name, phone, amount, "N/A", "Cancelled")
                return

            elif data.get('ResultCode') == "4999":
                continue  # Still waiting

            else:
                print(f"❌ Failed: {data.get('ResultDesc')}")
                save_transaction(name, phone, amount, "N/A", "Failed")
                return


# --- RUN THE APP ---
if __name__ == "__main__":
    app = AnyonaTracker()

    # Ask for details manually for now
    user_name = input("Enter Customer Name: ")
    user_phone = input("Enter Phone (254...): ")
    amount = 1

    app.trigger_payment(user_name, user_phone, amount)