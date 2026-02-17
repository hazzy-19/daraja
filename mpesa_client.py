"""
Enhanced M-Pesa client with best practices
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.auth import HTTPBasicAuth
import base64
from datetime import datetime, timedelta
import time
import logging
import os
from dotenv import load_dotenv
from database import save_transaction
from typing import Optional, Dict, Any

# ===================================================
# IMPORTANT: UPDATE THIS WITH YOUR NGROK URL
# ===================================================
NGROK_URL = "https://creamily-acarpelous-vicki.ngrok-free.dev"  # <-- CHANGE THIS
CALLBACK_URL = f"{NGROK_URL}/mpesa/callback"
# ===================================================

# Load secrets
load_dotenv("daraja.env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MpesaAPIError(Exception):
    """Custom exception for M-Pesa API errors"""
    pass


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


class MpesaClient:
    """
    Enhanced M-Pesa Client with best practices
    """

    def __init__(self):
        self.consumer_key = os.getenv("CONSUMER_KEY")
        self.consumer_secret = os.getenv("CONSUMER_SECRET")
        self.shortcode = "174379"
        self.passkey = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
        self.base_url = "https://sandbox.safaricom.co.ke"

        # Setup session with retry strategy
        self.session = self._create_session()

        # Cache for access token
        self._access_token = None
        self._token_expiry = None

        # Polling configuration
        self.max_poll_attempts = 60
        self.initial_poll_interval = 2
        self.max_poll_interval = 10

        logger.info("✅ MpesaClient initialized")

    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy"""
        session = requests.Session()

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def get_access_token(self) -> str:
        """Get OAuth access token with caching"""
        if self._access_token and self._token_expiry and datetime.now() < self._token_expiry:
            logger.debug("Using cached access token")
            return self._access_token

        try:
            logger.info("🔄 Requesting new access token...")

            response = self.session.get(
                f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials",
                auth=HTTPBasicAuth(self.consumer_key, self.consumer_secret),
                timeout=10
            )

            if response.status_code != 200:
                error_msg = f"Failed to get token: HTTP {response.status_code} - {response.text}"
                logger.error(f"❌ {error_msg}")
                raise MpesaAPIError(error_msg)

            data = response.json()
            self._access_token = data.get('access_token')

            if not self._access_token:
                raise MpesaAPIError("No access token in response")

            # Cache token for 50 minutes
            self._token_expiry = datetime.now() + timedelta(minutes=50)

            logger.info(f"✅ Access token obtained (expires at {self._token_expiry.strftime('%H:%M:%S')})")
            return self._access_token

        except Exception as e:
            logger.error(f"❌ Error getting token: {e}")
            raise MpesaAPIError(f"Token generation failed: {str(e)}")

    def validate_phone(self, phone: str) -> str:
        """Validate and format phone number to 254XXXXXXXXX"""
        if not phone:
            raise ValidationError("Phone number is required")

        clean = ''.join(filter(str.isdigit, phone))

        if not clean:
            raise ValidationError("Phone number must contain digits")

        if clean.startswith('0'):
            formatted = '254' + clean[1:]
        elif clean.startswith('254'):
            formatted = clean
        elif clean.startswith('7'):
            formatted = '254' + clean
        elif clean.startswith('+254'):
            formatted = clean[1:]
        else:
            formatted = clean

        if len(formatted) != 12:
            raise ValidationError(f"Phone number must be 12 digits (254XXXXXXXXX), got {len(formatted)} digits")

        logger.debug(f"Phone {phone} validated to {formatted}")
        return formatted

    def validate_amount(self, amount) -> int:
        """Validate transaction amount"""
        try:
            amount_float = float(amount)
        except (TypeError, ValueError):
            raise ValidationError(f"Invalid amount format: {amount}")

        if amount_float < 10:
            raise ValidationError("Amount must be at least KES 10")

        if amount_float > 150000:
            raise ValidationError("Amount cannot exceed KES 150,000")

        return int(amount_float)

    def generate_password(self, timestamp: str) -> str:
        """Generate base64 encoded password for STK Push"""
        password_str = self.shortcode + self.passkey + timestamp
        return base64.b64encode(password_str.encode()).decode()

    def wait_for_callback(self, checkout_id: str, timeout_seconds: int = 120) -> Optional[Dict]:
        """
        Wait for callback by polling the callback server's status endpoint
        """
        logger.info(f"⏳ Waiting for callback for checkout ID: {checkout_id}")

        # Using port 5000 (finally working!)
        callback_server = "http://127.0.0.1:5000"  # <-- CHANGED TO 5000

        # Check if callback server is reachable
        try:
            health = self.session.get(f"{callback_server}/health", timeout=2)
            if health.status_code == 200:
                logger.info(f"✅ Callback server is reachable at {callback_server}")
            else:
                logger.warning(f"⚠️ Callback server returned status {health.status_code}")
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ Cannot connect to callback server at {callback_server}")
            print(f"\n❌ ERROR: Callback server is NOT running at {callback_server}!")
            print("   Please start it in another terminal with:")
            print("   cd fast && uvicorn callback:app --reload --port 5000\n")
            return None
        except Exception as e:
            logger.error(f"❌ Error checking callback server: {e}")

        # Rest of the method stays the same
        start_time = time.time()
        poll_interval = 2
        attempts = 0

        while (time.time() - start_time) < timeout_seconds:
            attempts += 1
            elapsed = int(time.time() - start_time)

            try:
                if attempts % 3 == 0:
                    print(f"   ⏳ Waiting for callback... ({elapsed}s elapsed)")

                response = self.session.get(
                    f"{callback_server}/mpesa/callback-status/{checkout_id}",
                    timeout=3
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get('received'):
                        logger.info(f"✅ Callback received for {checkout_id} after {elapsed}s")
                        print(f"   ✅ Callback received! Processing...")
                        return data.get('data')

                time.sleep(poll_interval)
                poll_interval = min(poll_interval * 1.5, 8)

            except Exception as e:
                logger.debug(f"Error checking callback: {e}")
                time.sleep(poll_interval)

        logger.warning(f"⏰ Timeout waiting for callback after {timeout_seconds}s")
        print(f"\n⚠️ No callback received after {timeout_seconds} seconds")
        return None

    def stk_push(self, phone: str, amount, account_reference: str = None) -> Dict[str, Any]:
        """
        Initiate STK Push transaction
        Only saves to database AFTER callback confirms success
        """
        try:
            # Validate inputs
            logger.info("🔍 Validating inputs...")
            formatted_phone = self.validate_phone(phone)
            validated_amount = self.validate_amount(amount)
            logger.info(f"✅ Inputs valid: {formatted_phone} - KES {validated_amount}")

            # Get access token
            token = self.get_access_token()

            # Generate timestamp and password
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self.generate_password(timestamp)

            # Prepare payload with callback URL from top of file
            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": validated_amount,
                "PartyA": formatted_phone,
                "PartyB": self.shortcode,
                "PhoneNumber": formatted_phone,
                "CallBackURL": CALLBACK_URL,  # 👈 USING THE PLACEHOLDER
                "AccountReference": account_reference or f"REF-{formatted_phone[-4:]}",
                "TransactionDesc": "Payment"
            }

            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }

            logger.info(f"🚀 Sending STK Push to {formatted_phone} for KES {validated_amount}")
            logger.info(f"📞 Callback URL: {CALLBACK_URL}")

            # Make API request
            response = self.session.post(
                f"{self.base_url}/mpesa/stkpush/v1/processrequest",
                headers=headers,
                json=payload,
                timeout=30
            )

            logger.info(f"📥 Response status: {response.status_code}")

            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"❌ STK Push failed: {error_msg}")
                return {"success": False, "reason": error_msg}

            data = response.json()

            if data.get('ResponseCode') != "0":
                error_msg = data.get('errorMessage', data.get('ResponseDescription', 'Unknown error'))
                logger.error(f"❌ STK Push failed: {error_msg}")
                return {"success": False, "reason": error_msg}

            checkout_id = data['CheckoutRequestID']
            logger.info(f"✅ STK Push sent. CheckoutID: {checkout_id}")

            print(f"\n⏳ Waiting for M-Pesa to process your payment...")
            print(f"   Checkout ID: {checkout_id}")
            print(f"   Callback URL: {CALLBACK_URL}")
            print(f"   This may take 30-60 seconds...\n")

            # Wait for callback
            callback_data = self.wait_for_callback(checkout_id, timeout_seconds=120)

            if callback_data:
                # Extract the callback data
                stored_data = callback_data.get('full_data', {})
                body = stored_data.get('Body', {})
                stk_callback = body.get('stkCallback', {})

                if stk_callback.get('ResultCode') == 0:
                    # Extract receipt
                    metadata = stk_callback.get('CallbackMetadata', {})
                    items = metadata.get('Item', [])

                    receipt = None
                    amount_paid = None
                    phone_paid = None

                    for item in items:
                        if item.get('Name') == 'MpesaReceiptNumber':
                            receipt = item.get('Value')
                        elif item.get('Name') == 'Amount':
                            amount_paid = item.get('Value')
                        elif item.get('Name') == 'PhoneNumber':
                            phone_paid = item.get('Value')

                    if receipt:
                        # Convert phone_paid to string if it's an integer
                        phone_str = str(phone_paid) if phone_paid else ""
                        amount_str = str(amount_paid) if amount_paid else ""

                        # Save to database with proper string conversion
                        save_transaction(
                            name=f"Customer-{phone_str[-4:] if phone_str else formatted_phone[-4:]}",
                            phone=phone_str or formatted_phone,
                            amount=float(amount_str) if amount_str else validated_amount,
                            receipt=receipt,
                            status="SUCCESS"
                        )

                        print(f"\n✅ PAYMENT SUCCESSFUL!")
                        print(f"📄 Receipt Number: {receipt}")
                        print(f"💰 Amount: KES {amount_str or validated_amount}")
                        print(f"📱 Phone: {phone_str or formatted_phone}")

                        return {
                            "success": True,
                            "receipt": receipt,
                            "checkout_id": checkout_id
                        }
                else:
                    reason = stk_callback.get('ResultDesc', 'Transaction failed')
                    print(f"\n❌ Payment failed: {reason}")
                    return {"success": False, "reason": reason}
            else:
                print(f"\n❌ No callback received. Please check transaction status manually.")
                print(f"   Checkout ID: {checkout_id}")
                return {
                    "success": False,
                    "reason": "Callback timeout",
                    "checkout_id": checkout_id
                }

        except ValidationError as e:
            logger.error(f"❌ Validation error: {e}")
            return {"success": False, "reason": str(e)}
        except MpesaAPIError as e:
            logger.error(f"❌ M-Pesa API error: {e}")
            return {"success": False, "reason": str(e)}
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            logger.exception("Full traceback:")
            return {"success": False, "reason": f"Unexpected error: {str(e)}"}


# For backward compatibility
class AnyonaTracker(MpesaClient):
    """Keeping your original class name for compatibility"""

    def trigger_payment(self, phone, amount):
        return self.stk_push(phone, amount)