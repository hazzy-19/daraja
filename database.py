import psycopg2
import os
from dotenv import load_dotenv

load_dotenv("daraja.env")


def get_db_connection():
    # If DB_PASS is empty in .env, this will be an empty string ""
    password = os.getenv("DB_PASS")

    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=password,  # It's okay if this is empty!
        host=os.getenv("DB_HOST", "localhost"),  # Defaults to localhost if missing
        port=os.getenv("DB_PORT", "5432")  # Defaults to 5432 if missing
    )


def save_transaction(name, phone, amount, receipt, status):
    """Saves the transaction to Postgres"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 1. Create table if it doesn't exist yet (Safety check)
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            user_name VARCHAR(100),
            phone_number VARCHAR(15),
            amount DECIMAL(10, 2),
            receipt_number VARCHAR(50),
            transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(20)
        );
        """
        cur.execute(create_table_sql)

        # 2. Insert the data
        sql = """
        INSERT INTO transactions (user_name, phone_number, amount, receipt_number, status)
        VALUES (%s, %s, %s, %s, %s)
        """

        cur.execute(sql, (name, phone, amount, receipt, status))
        conn.commit()

        print(f"💾 DATABASE SUCCESS: Saved {name}'s payment.")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ DATABASE ERROR: Could not save record.\nReason: {e}")


# --- QUICK TEST ---
# Run this file directly to test the connection: 'python database.py'
if __name__ == "__main__":
    print("Testing Database Connection...")
    save_transaction("Test User", "0700000000", 1.00, "TEST1234", "Success")