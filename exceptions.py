class MpesaError(Exception):
    """Base exception for M-Pesa errors"""
    pass

class MpesaAPIError(MpesaError):
    """Exception for API-related errors"""
    def __init__(self, message, response_data=None):
        self.message = message
        self.response_data = response_data
        super().__init__(self.message)

class ValidationError(MpesaError):
    """Exception for input validation errors"""
    pass

class TransactionError(MpesaError):
    """Exception for transaction processing errors"""
    pass