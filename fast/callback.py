"""
M-Pesa Callback Handler - Separate FastAPI app for receiving callbacks
Run with: uvicorn callback:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "daraja.env")
load_dotenv(env_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('callbacks.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import database functions
try:
    from database import update_transaction_by_checkout, get_transaction_by_receipt, check_database_connection

    logger.info("✅ Database functions imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import database functions: {e}")


    def update_transaction_by_checkout(checkout_id, real_receipt, details=None):
        logger.warning(f"⚠️ Fallback: {checkout_id} -> {real_receipt}")
        return True


    def get_transaction_by_receipt(receipt):
        return None


    def check_database_connection():
        return True, "Fallback mode"

# Create FastAPI app
app = FastAPI(
    title="M-Pesa Callback Handler",
    description="Receives transaction results from Safaricom",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for callbacks
callback_store = {}


@app.get("/")
async def root():
    return {
        "name": "M-Pesa Callback Handler",
        "version": "1.0.0",
        "status": "running",
        "endpoints": [
            {"path": "/health", "method": "GET"},
            {"path": "/mpesa/callback", "method": "POST"},
            {"path": "/mpesa/callback-status/{checkout_id}", "method": "GET"},
            {"path": "/mpesa/callback-store", "method": "GET"}
        ]
    }


@app.get("/health")
async def health():
    db_status = "unknown"
    try:
        success, message = check_database_connection()
        db_status = "connected" if success else "disconnected"
    except:
        db_status = "error"

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": db_status,
        "callbacks_received": len(callback_store)
    }


@app.post("/mpesa/callback")
async def mpesa_callback(request: Request):
    client_ip = request.client.host
    logger.info(f"📥 Callback received from IP: {client_ip}")

    try:
        callback_data = await request.json()
        logger.info(f"📦 Callback data received")

        body = callback_data.get('Body', {})
        stk_callback = body.get('stkCallback', {})

        if not stk_callback:
            logger.error("❌ No stkCallback in response")
            return {"ResultCode": 1, "ResultDesc": "Invalid callback data"}

        checkout_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc')

        logger.info(f"📋 CheckoutID: {checkout_id}, ResultCode: {result_code}")

        # Store callback immediately
        callback_store[checkout_id] = {
            'received': True,
            'timestamp': datetime.now().isoformat(),
            'result_code': result_code,
            'result_desc': result_desc,
            'full_data': callback_data
        }

        if result_code == 0:
            # Extract receipt
            metadata = stk_callback.get('CallbackMetadata', {})
            items = metadata.get('Item', [])

            receipt = None
            for item in items:
                if item.get('Name') == 'MpesaReceiptNumber':
                    receipt = item.get('Value')
                    logger.info(f"✅ Receipt: {receipt}")
                    break

            if receipt:
                callback_store[checkout_id]['receipt'] = receipt

                # Update database
                try:
                    success = update_transaction_by_checkout(checkout_id, receipt, {})
                    if success:
                        logger.info(f"✅ Database updated with receipt {receipt}")
                        callback_store[checkout_id]['database_updated'] = True
                except Exception as e:
                    logger.error(f"❌ Database update failed: {e}")

        return {"ResultCode": 0, "ResultDesc": "Success"}

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return {"ResultCode": 0, "ResultDesc": "Success"}


@app.get("/mpesa/callback-status/{checkout_id}")
async def get_callback_status(checkout_id: str):
    """Check if callback has been received"""
    if checkout_id in callback_store:
        return {
            'received': True,
            'data': callback_store[checkout_id]
        }
    return {'received': False}


@app.get("/mpesa/callback-store")
async def show_store():
    """Debug endpoint to see all callbacks"""
    return callback_store


@app.post("/mpesa/test-callback")
async def test_callback():
    """Test endpoint to simulate a callback"""
    test_id = f"ws_CO_test_{datetime.now().strftime('%H%M%S')}"
    test_data = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": test_id,
                "ResultCode": 0,
                "ResultDesc": "Success",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 100},
                        {"Name": "MpesaReceiptNumber", "Value": "TEST123ABC"},
                        {"Name": "PhoneNumber", "Value": 254757611486}
                    ]
                }
            }
        }
    }

    # Store it
    callback_store[test_id] = {
        'received': True,
        'timestamp': datetime.now().isoformat(),
        'test': True,
        'full_data': test_data
    }

    return test_data


if __name__ == "__main__":
    import uvicorn

    print("=" * 50)
    print("🚀 M-PESA CALLBACK HANDLER".center(50))
    print("=" * 50)
    print("📡 Server: http://localhost:8000")
    print("📌 Callback URL: http://localhost:8000/mpesa/callback")
    print("🔍 Status: http://localhost:8000/mpesa/callback-status/CHECKOUT_ID")
    print("📊 Store: http://localhost:8000/mpesa/callback-store")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)