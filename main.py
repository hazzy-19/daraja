#!/usr/bin/env python3
"""
Enhanced CLI for M-Pesa Payments with better transaction display
"""

import sys
import logging
from datetime import datetime
from mpesa_client import MpesaClient, ValidationError
from database import (
    get_transactions_by_phone,
    get_all_transactions,
    check_database_connection,
    save_transaction
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('mpesa.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def clear_screen():
    """Clear the console screen"""
    import os
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """Print application header"""
    print("\n" + "=" * 60)
    print("🚀 M-PESA PAYMENT TRACKER".center(60))
    print("=" * 60)

    # Check database connection
    success, message = check_database_connection()
    status = "✅ CONNECTED" if success else "❌ DISCONNECTED"
    print(f"📊 Database: {status}")
    print("=" * 60 + "\n")


def print_transactions(transactions, title="Recent Transactions"):
    """Pretty print transactions"""
    if not transactions:
        print(f"\n📭 No {title.lower()} found")
        return

    print(f"\n📊 {title}:")
    print("-" * 90)
    print(f"{'Date':<20} {'Phone':<15} {'Amount':<10} {'Status':<12} {'Receipt':<20}")
    print("-" * 90)

    for tx in transactions:
        date = tx.get('date', tx.get('formatted_date', 'N/A'))[:16]
        phone = tx.get('phone', tx.get('phone_number', 'N/A'))
        amount = f"KES {float(tx.get('amount', 0)):.2f}"
        status = tx.get('status', 'N/A')
        receipt = tx.get('receipt', tx.get('receipt_number', 'N/A'))

        # Add emoji based on status
        status_emoji = {
            'SUCCESS': '✅',
            'COMPLETED': '✅',
            'PENDING': '⏳',
            'FAILED': '❌',
            'CANCELLED': '🚫',
            'TIMEOUT': '⏰'
        }.get(status.upper(), '❓')

        print(f"{date:<20} {phone:<15} {amount:<10} {status_emoji} {status:<10} {receipt:<20}")


def print_payment_result(result):
    """Print payment result with details"""
    if not result:
        print("\n❌ No result returned")
        return

    print("\n" + "=" * 50)

    if result.get('success'):
        print("✅ PAYMENT SUCCESSFUL!".center(50))
        print("=" * 50)

        receipt = result.get('receipt')
        temp_receipt = result.get('temp_receipt')

        if receipt:
            print(f"📄 Receipt Number: {receipt}")
            print(f"💾 Saved to database with receipt: {receipt}")
        else:
            print(f"📄 Receipt: Pending (waiting for callback)")
            print(f"💾 Temporary ID: {temp_receipt}")
            print("\n⏳ The receipt will be updated automatically")
            print("   when Safaricom sends the callback.")
    else:
        print("❌ PAYMENT FAILED".center(50))
        print("=" * 50)
        print(f"❌ Reason: {result.get('reason', 'Unknown error')}")

    # Show polling stats if available
    if 'attempts' in result:
        print(f"🔄 Polling attempts: {result['attempts']}")
    if 'elapsed' in result:
        print(f"⏱️  Time elapsed: {result['elapsed']:.1f}s")

    print("=" * 50)

def main():
    """Main CLI function"""
    client = MpesaClient()

    while True:
        clear_screen()
        print_header()

        print("📌 OPTIONS:")
        print("  1. 💰 Make a payment")
        print("  2. 📋 View my transactions")
        print("  3. 🔍 Search transactions")
        print("  4. 📊 View all transactions")
        print("  5. 🧪 Test database")
        print("  6. 🚪 Exit")

        choice = input("\n👉 Select option (1-6): ").strip()

        if choice == '1':
            # Make payment
            print("\n" + "-" * 50)
            print("💰 MAKE PAYMENT".center(50))
            print("-" * 50)

            try:
                phone = input("📱 Phone Number (e.g., 0712345678): ").strip()
                if not phone:
                    print("❌ Phone number required")
                    input("\nPress Enter to continue...")
                    continue

                amount = input("💰 Amount (KES): ").strip()
                if not amount:
                    print("❌ Amount required")
                    input("\nPress Enter to continue...")
                    continue

                ref = input("📝 Reference (optional): ").strip()

                print(f"\n⏳ Processing payment...")
                print(f"📱 Phone: {phone}")
                print(f"💰 Amount: KES {amount}")
                if ref:
                    print(f"📝 Reference: {ref}")

                print("\n" + "-" * 30)
                result = client.stk_push(phone, amount, ref if ref else None)
                print_payment_result(result)

            except KeyboardInterrupt:
                print("\n\n⚠️ Payment cancelled")
            except Exception as e:
                logger.error(f"Error in payment: {e}")
                print(f"\n❌ Error: {e}")

            input("\nPress Enter to continue...")

        elif choice == '2':
            # View my transactions
            print("\n" + "-" * 50)
            print("📋 MY TRANSACTIONS".center(50))
            print("-" * 50)

            phone = input("📱 Enter your phone number: ").strip()

            if phone:
                print(f"\n🔍 Searching for transactions with {phone}...")
                transactions = get_transactions_by_phone(phone, limit=20)

                if transactions:
                    print_transactions(transactions, f"Transactions for {phone}")

                    # Option to view details
                    view_detail = input("\n🔍 Enter receipt number for details (or Enter to skip): ").strip()
                    if view_detail:
                        from database import get_transaction_by_receipt
                        tx = get_transaction_by_receipt(view_detail)
                        if tx:
                            print(f"\n📄 Details for {view_detail}:")
                            print(f"   Name: {tx.get('user_name')}")
                            print(f"   Phone: {tx.get('phone_number')}")
                            print(f"   Amount: KES {tx.get('amount')}")
                            print(f"   Date: {tx.get('transaction_date')}")
                            print(f"   Status: {tx.get('status')}")
                        else:
                            print(f"❌ No transaction found with receipt: {view_detail}")
                else:
                    print(f"\n❌ No transactions found for {phone}")
                    print("\n💡 Tips:")
                    print("  • Try with format: 254757611486")
                    print("  • Try with format: 0757611486")
                    print("  • Check if you've made any payments yet")
            else:
                print("❌ Phone number required")

            input("\nPress Enter to continue...")

        elif choice == '3':
            # Search transactions
            print("\n" + "-" * 50)
            print("🔍 SEARCH TRANSACTIONS".center(50))
            print("-" * 50)

            search_term = input("Enter phone number or receipt to search: ").strip()

            if search_term:
                # Check if it looks like a receipt (has letters and numbers)
                if any(c.isalpha() for c in search_term):
                    from database import get_transaction_by_receipt
                    tx = get_transaction_by_receipt(search_term)
                    if tx:
                        print(f"\n✅ Transaction found:")
                        print(f"   ID: {tx.get('id')}")
                        print(f"   Name: {tx.get('user_name')}")
                        print(f"   Phone: {tx.get('phone_number')}")
                        print(f"   Amount: KES {tx.get('amount')}")
                        print(f"   Date: {tx.get('transaction_date')}")
                        print(f"   Status: {tx.get('status')}")
                    else:
                        print(f"❌ No transaction found with receipt: {search_term}")
                else:
                    # Search by phone
                    transactions = get_transactions_by_phone(search_term, limit=20)
                    if transactions:
                        print_transactions(transactions, f"Transactions for {search_term}")
                    else:
                        print(f"❌ No transactions found for: {search_term}")

            input("\nPress Enter to continue...")

        elif choice == '4':
            # View all transactions
            print("\n" + "-" * 50)
            print("📊 ALL TRANSACTIONS".center(50))
            print("-" * 50)

            transactions = get_all_transactions(30)
            print_transactions(transactions, "All Recent Transactions")

            input("\nPress Enter to continue...")

        elif choice == '5':
            # Test database
            print("\n" + "-" * 50)
            print("🧪 DATABASE TEST".center(50))
            print("-" * 50)

            # Test connection
            success, message = check_database_connection()
            print(f"Connection: {'✅ OK' if success else '❌ Failed'}")
            print(f"Message: {message}")

            if success:
                # Show sample data
                transactions = get_all_transactions(5)
                if transactions:
                    print(f"\n📊 Sample of {len(transactions)} recent transactions:")
                    for tx in transactions:
                        print(f"  • {tx['phone_number']}: KES {tx['amount']} - {tx['status']} ({tx['formatted_date']})")
                else:
                    print("\n📭 No transactions in database")

                # Show database stats
                print(f"\n📊 Database: {os.getenv('DB_NAME')} on {os.getenv('DB_HOST')}")

            input("\nPress Enter to continue...")

        elif choice == '6':
            print("\n👋 Goodbye!")
            break

        else:
            input("❌ Invalid option. Press Enter to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        logger.exception("Unexpected error")
        print(f"\n❌ An error occurred: {e}")
        input("Press Enter to exit...")