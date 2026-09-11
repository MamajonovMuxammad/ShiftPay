from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class InvoiceCreate(BaseModel):
    """Схема запроса на выставление счета кассиром"""
    amount_uzs: float = Field(..., gt=0, description="Сумма в национальной валюте UZS")


class InvoiceResponse(BaseModel):
    """Схема ответа при создании инвойса"""
    transaction_id: str
    amount_uzs: float
    amount_usdt: float
    status: str
    checkout_url: str
    created_at: str


class TransactionResponse(BaseModel):
    """Схема статуса транзакции для Long Polling и экрана проверки"""
    id: str
    merchant_id: Optional[str] = None
    merchant_name: str = "Shift Pay Flagship Store"
    amount_uzs: float
    amount_usdt: float
    status: str
    created_at: str


class PaymentResponse(BaseModel):
    """Ответ после подтверждения платежа через шлюз"""
    status: str
    message: str
    transaction_id: str
