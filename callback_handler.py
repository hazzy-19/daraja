from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import logging
from database import TransactionRepository, get_db
from config import get_settings
import json

logger = logging.getLogger(__name__)
settings = get_settings()
app = FastAPI(title="M-Pesa Payment Tracker")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# IP whitelist middleware
@app.middleware("http")
async def ip_whitelist(request: Request, call_next):
    """Only allow requests from Safaricom IPs for callback endpoints"""
    if request.url.path.startswith("/api/mpesa/callback"):
        client_ip = request.client.host

        # Skip IP check in development/sandbox
        if settings.environment == "production":
            if client_ip not in settings.ip_whitelist:
                logger.warning(f"Blocked request from unauthorized IP: {client_ip}")
                raise HTTPException(status_code=403, detail="Access denied")

    response = await call_next(request)
    return response


@app.post("/api/mpesa/callback")
async def mpesa_callback(request: Request):
    """
    Handle M-Pesa STK Push callback
    This endpoint receives transaction results from Safaricom
    """
    try:
        # Get callback data
        callback_data = await request.json()
        logger.info(f"Received callback: {json.dumps(callback_data)}")

        # Extract transaction details
        body = callback_data.get('Body', {})
        stk_callback = body.get('stkCallback', {})

        checkout_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc')

        # Update transaction in database
        transaction_repo = TransactionRepository()
        update_data = {
            'result_code': str(result_code),
            'result_desc': result_desc,
            'raw_callback_data': json.dumps(callback_data)
        }

        # Check if transaction was successful
        if result_code == 0:
            # Extract metadata for successful transaction
            metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])

            for item in metadata:
                if item.get('Name') == 'MpesaReceiptNumber':
                    update_data['mpesa_receipt_number'] = item.get('Value')
                elif item.get('Name') == 'TransactionDate':
                    update_data['transaction_date'] = item.get('Value')
                elif item.get('Name') == 'PhoneNumber':
                    update_data['phone_number'] = str(item.get('Value'))
                elif item.get('Name') == 'Amount':
                    update_data['amount'] = item.get('Value')

            update_data['status'] = 'COMPLETED'
            logger.info(f"Payment completed: {update_data.get('mpesa_receipt_number')}")

        elif result_code == 1032:
            update_data['status'] = 'CANCELLED'
            logger.info("Transaction cancelled by user")
        else:
            update_data['status'] = 'FAILED'
            logger.error(f"Transaction failed: {result_desc}")

        # Update database
        transaction_repo.update_transaction(checkout_id, update_data)

        # Return success response to Safaricom
        return {
            "ResultCode": 0,
            "ResultDesc": "Success"
        }

    except Exception as e:
        logger.error(f"Error processing callback: {e}")
        # Still return success to Safaricom to prevent retries
        return {
            "ResultCode": 0,
            "ResultDesc": "Success"
        }


@app.get("/api/transactions/{checkout_id}")
async def get_transaction(checkout_id: str):
    """Get transaction details by checkout ID"""
    transaction_repo = TransactionRepository()
    transaction = transaction_repo.get_transaction(checkout_id)

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return transaction.to_dict()


@app.get("/api/transactions/receipt/{receipt_number}")
async def get_transaction_by_receipt(receipt_number: str):
    """Get transaction details by M-Pesa receipt number"""
    transaction_repo = TransactionRepository()
    transaction = transaction_repo.get_transaction_by_receipt(receipt_number)

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return transaction.to_dict()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "timestamp": datetime.now().isoformat()
    }