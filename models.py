from sqlalchemy import create_engine, Column, String, DateTime, Float, Integer, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

Base = declarative_base()


class MpesaTransaction(Base):
    """M-Pesa Transaction Model"""
    __tablename__ = 'mpesa_transactions'

    id = Column(Integer, primary_key=True)
    checkout_request_id = Column(String(100), unique=True, index=True)
    merchant_request_id = Column(String(100))
    phone_number = Column(String(20), index=True)
    amount = Column(Float)
    mpesa_receipt_number = Column(String(50), unique=True, index=True)
    transaction_date = Column(DateTime)
    status = Column(String(50), index=True)  # PENDING, COMPLETED, FAILED, CANCELLED
    result_code = Column(String(10))
    result_desc = Column(String(255))
    raw_callback_data = Column(Text)  # Store raw JSON for debugging

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'checkout_request_id': self.checkout_request_id,
            'phone_number': self.phone_number,
            'amount': self.amount,
            'mpesa_receipt_number': self.mpesa_receipt_number,
            'status': self.status,
            'transaction_date': self.transaction_date.isoformat() if self.transaction_date else None
        }


class ApiLog(Base):
    """API Request/Response Log for debugging"""
    __tablename__ = 'api_logs'

    id = Column(Integer, primary_key=True)
    endpoint = Column(String(255))
    request_data = Column(Text)
    response_data = Column(Text)
    status_code = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)