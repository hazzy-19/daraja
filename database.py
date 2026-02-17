"""
Enhanced database module with proper error handling and phone number format normalization.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
from datetime import datetime

# Load environment variables
load_dotenv("daraja.env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom database exception"""
    pass


class DatabaseConnection:
    """
    Database connection manager with better error handling.
    """

    def __init__(self):
        self.connection_params = {
            'dbname': os.getenv("DB_NAME"),
            'user': os.getenv("DB_USER"),
            'password': os.getenv("DB_PASS", ""),
            'host': os.getenv("DB_HOST", "localhost"),
            'port': os.getenv("DB_PORT", "5432")
        }

        # Validate required parameters
        if not all([self.connection_params['dbname'], self.connection_params['user']]):
            raise DatabaseError("Database name and user are required in .env file")

    @contextmanager
    def get_connection(self):
        """Get a database connection with error handling"""
        conn = None
        try:
            conn = psycopg2.connect(**self.connection_params)
            yield conn
        except psycopg2.OperationalError as e:
            logger.error(f"❌ Cannot connect to database: {e}")
            raise DatabaseError(f"Database connection failed: {e}")
        except Exception as e:
            logger.error(f"❌ Unexpected database error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    @contextmanager
    def get_cursor(self, cursor_factory=None):
        """Get a database cursor with error handling"""
        with self.get_connection() as conn:
            try:
                if cursor_factory:
                    cur = conn.cursor(cursor_factory=cursor_factory)
                else:
                    cur = conn.cursor()
                yield cur
                conn.commit()
            except psycopg2.Error as e:
                conn.rollback()
                logger.error(f"❌ Database error: {e}")
                raise DatabaseError(f"Database operation failed: {e}")
            except Exception as e:
                conn.rollback()
                logger.error(f"❌ Unexpected error: {e}")
                raise
            finally:
                cur.close()


# Create global database instance
try:
    db = DatabaseConnection()
    logger.info(f"✅ Database connection configured for {os.getenv('DB_NAME')}")
except DatabaseError as e:
    logger.error(f"❌ Failed to configure database: {e}")
    raise


def normalize_phone(phone: str) -> list:
    """
    Normalize phone number to multiple formats for searching.
    Returns a list of possible formats.
    """
    if not phone:
        return []

    # Remove all non-digits
    clean = ''.join(filter(str.isdigit, phone))

    formats = []

    # Original format
    if clean:
        formats.append(clean)

    # If starts with 0, also try 254 format
    if clean.startswith('0'):
        formats.append('254' + clean[1:])

    # If starts with 254, also try 0 format
    if clean.startswith('254') and len(clean) > 3:
        formats.append('0' + clean[3:])

    # If starts with 7, add 254 and 0 formats
    if clean.startswith('7') and len(clean) == 9:
        formats.append('254' + clean)
        formats.append('0' + clean)

    # Remove duplicates
    seen = set()
    unique_formats = []
    for fmt in formats:
        if fmt not in seen:
            seen.add(fmt)
            unique_formats.append(fmt)

    logger.debug(f"Phone {phone} normalized to: {unique_formats}")
    return unique_formats


def save_transaction(name, phone, amount, receipt, status):
    """
    Save a transaction to database
    """
    try:
        # Normalize phone
        phone_formats = normalize_phone(phone)
        stored_phone = phone_formats[0] if phone_formats else phone

        with db.get_cursor() as cur:
            sql = """
            INSERT INTO transactions (user_name, phone_number, amount, receipt_number, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """
            cur.execute(sql, (name, stored_phone, amount, receipt, status))
            transaction_id = cur.fetchone()[0]

        logger.info(f"💾 Saved transaction {transaction_id} - {receipt}")
        return transaction_id

    except Exception as e:
        logger.error(f"❌ Error saving transaction: {e}")
        return None


def get_transactions_by_phone(phone, limit=10):
    """
    Get transactions by phone number
    """
    try:
        phone_formats = normalize_phone(phone)
        if not phone_formats:
            return []

        placeholders = ','.join(['%s'] * len(phone_formats))
        query = f"""
            SELECT 
                id,
                user_name,
                phone_number,
                amount,
                receipt_number,
                TO_CHAR(transaction_date, 'YYYY-MM-DD HH24:MI:SS') as formatted_date,
                status
            FROM transactions 
            WHERE phone_number IN ({placeholders})
            ORDER BY transaction_date DESC 
            LIMIT %s;
        """

        params = phone_formats + [limit]

        with db.get_cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            results = cur.fetchall()

            transactions = []
            for row in results:
                transactions.append({
                    'id': row['id'],
                    'user_name': row['user_name'],
                    'phone': row['phone_number'],
                    'amount': float(row['amount']) if row['amount'] else 0,
                    'receipt': row['receipt_number'],
                    'date': row['formatted_date'],
                    'status': row['status']
                })

            return transactions

    except Exception as e:
        logger.error(f"❌ Error in get_transactions_by_phone: {e}")
        return []


def get_transaction_by_receipt(receipt_number):
    """
    Get a transaction by receipt number
    """
    try:
        with db.get_cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM transactions WHERE receipt_number = %s",
                (receipt_number,)
            )
            return cur.fetchone()
    except Exception as e:
        logger.error(f"❌ Error fetching transaction: {e}")
        return None


def update_transaction_by_checkout(checkout_id: str, real_receipt: str, details: dict = None):
    """
    Update transaction using checkout_id
    Note: This requires a checkout_id column in your transactions table
    If you don't have it, this function will just log
    """
    try:
        # First check if checkout_id column exists
        with db.get_cursor() as cur:
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'transactions' AND column_name = 'checkout_id'
            """)
            has_column = cur.fetchone() is not None

            if not has_column:
                logger.warning("⚠️ checkout_id column doesn't exist in transactions table")
                logger.info(f"Would update: {checkout_id} -> {real_receipt}")
                return True

            # Update using checkout_id
            cur.execute("""
                UPDATE transactions 
                SET receipt_number = %s, status = 'SUCCESS'
                WHERE checkout_id = %s
                RETURNING id
            """, (real_receipt, checkout_id))

            result = cur.fetchone()
            if result:
                logger.info(f"✅ Updated transaction with receipt {real_receipt}")
                return True
            else:
                logger.warning(f"⚠️ No transaction found with checkout_id: {checkout_id}")
                return False

    except Exception as e:
        logger.error(f"❌ Error updating by checkout: {e}")
        return False


def get_all_transactions(limit=50):
    """Get all recent transactions"""
    try:
        with db.get_cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    id,
                    user_name,
                    phone_number,
                    amount,
                    receipt_number,
                    TO_CHAR(transaction_date, 'YYYY-MM-DD HH24:MI:SS') as formatted_date,
                    status
                FROM transactions 
                ORDER BY transaction_date DESC 
                LIMIT %s
            """, (limit,))
            return cur.fetchall()
    except Exception as e:
        logger.error(f"❌ Error fetching all transactions: {e}")
        return []


def check_database_connection():
    """Test database connection"""
    try:
        with db.get_cursor() as cur:
            cur.execute("SELECT 1")

            # Check if transactions table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'transactions'
                );
            """)
            table_exists = cur.fetchone()[0]

            if table_exists:
                cur.execute("SELECT COUNT(*) FROM transactions")
                count = cur.fetchone()[0]
                return True, f"Connected, {count} transactions"
            else:
                return True, "Connected, no transactions table"

    except Exception as e:
        return False, str(e)


# --- TESTING ---
if __name__ == "__main__":
    print("🔧 Testing Database Connection...")
    success, message = check_database_connection()
    print(f"📊 Status: {message}")