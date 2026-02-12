import requests

# PASTE YOUR CURRENT NGROK URL HERE (Don't forget /callback)
url = "https://creamily-acarpelous-vicki.ngrok-free.dev/callback"

payload = {
    "Body": {
        "stkCallback": {
            "MerchantRequestID": "TEST-123",
            "CheckoutRequestID": "TEST-456",
            "ResultCode": 0,
            "ResultDesc": "The service request is processed successfully.",
            "CallbackMetadata": {
                "Item": [
                    {"Name": "Amount", "Value": 1.00},
                    {"Name": "MpesaReceiptNumber", "Value": "TEST12345"},
                    {"Name": "TransactionDate", "Value": 20260212120000},
                    {"Name": "PhoneNumber", "Value": 254700000000}
                ]
            }
        }
    }
}

print(f"Testing URL: {url}")
try:
    response = requests.post(url, json=payload)
    print(f"Server Response: {response.status_code}")
    print("Check your main.py terminal now!")
except Exception as e:
    print(f"Connection failed: {e}")