"""
Database module for Shift Pay MVP.
Supports Supabase Cloud Client with automatic fallback to high-speed in-memory store
if Supabase credentials are not yet configured in .env.

--------------------------------------------------------------------------------
DATABASE SCHEMA (SUPABASE / POSTGRESQL SQL CODE)
Выполните данный SQL код в Supabase SQL Editor для создания структуры:
--------------------------------------------------------------------------------

-- Включение расширения для генерации UUID (если еще не включено)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Таблица мерчантов (торговых точек)
CREATE TABLE IF NOT EXISTS merchants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL DEFAULT 'Shift Pay Partner',
    wallet_address TEXT NOT NULL DEFAULT 'EQB_ShiftPayOfficialTetherWallet_9921'
);

-- Таблица транзакций эквайринга
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    merchant_id UUID REFERENCES merchants(id) ON DELETE SET NULL,
    amount_uzs NUMERIC(15, 2) NOT NULL,
    amount_usdt NUMERIC(15, 4) NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'processing', 'success'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::TEXT, now()) NOT NULL
);

-- Добавление стартового мерчанта
INSERT INTO merchants (id, name, wallet_address)
VALUES ('00000000-0000-0000-0000-000000000001', 'Shift Pay Flagship Store', 'EQB_ShiftPayOfficialTetherWallet_9921')
ON CONFLICT (id) DO NOTHING;

--------------------------------------------------------------------------------
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("shiftpay.database")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

DEFAULT_MERCHANT_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_MERCHANT_NAME = "Shift Pay Flagship Store"


class DatabaseService:
    """Абстрактный интерфейс сервиса базы данных"""

    def create_transaction(
        self, amount_uzs: float, amount_usdt: float, merchant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def update_transaction_status(
        self, transaction_id: str, status: str
    ) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


class SupabaseDatabaseService(DatabaseService):
    """Реализация работы с Supabase через официальный SDK"""

    def __init__(self, client):
        self.client = client
        logger.info("Connected to Supabase successfully.")

    def create_transaction(
        self, amount_uzs: float, amount_usdt: float, merchant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        m_id = merchant_id or DEFAULT_MERCHANT_ID
        tx_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        
        payload = {
            "id": tx_id,
            "merchant_id": m_id,
            "amount_uzs": float(amount_uzs),
            "amount_usdt": float(amount_usdt),
            "status": "pending",
            "created_at": now_iso
        }
        
        response = self.client.table("transactions").insert(payload).execute()
        if response.data and len(response.data) > 0:
            row = response.data[0]
            row["merchant_name"] = DEFAULT_MERCHANT_NAME
            return row
        payload["merchant_name"] = DEFAULT_MERCHANT_NAME
        return payload

    def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        response = self.client.table("transactions").select("*").eq("id", transaction_id).execute()
        if response.data and len(response.data) > 0:
            row = response.data[0]
            row["merchant_name"] = DEFAULT_MERCHANT_NAME
            return row
        return None

    def update_transaction_status(
        self, transaction_id: str, status: str
    ) -> Optional[Dict[str, Any]]:
        response = self.client.table("transactions").update({"status": status}).eq("id", transaction_id).execute()
        if response.data and len(response.data) > 0:
            row = response.data[0]
            row["merchant_name"] = DEFAULT_MERCHANT_NAME
            return row
        return None


class InMemoryDatabaseService(DatabaseService):
    """
    Автономный In-Memory эмулятор БД для мгновенного запуска и демонстрации,
    если Supabase URL/KEY еще не сконфигурированы.
    """

    def __init__(self):
        self.merchants: Dict[str, Dict[str, Any]] = {
            DEFAULT_MERCHANT_ID: {
                "id": DEFAULT_MERCHANT_ID,
                "name": DEFAULT_MERCHANT_NAME,
                "wallet_address": "EQB_ShiftPayOfficialTetherWallet_9921"
            }
        }
        self.transactions: Dict[str, Dict[str, Any]] = {}
        logger.info("Using In-Memory Database (Demo Mode). Ready for immediate operation.")

    def create_transaction(
        self, amount_uzs: float, amount_usdt: float, merchant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        tx_id = str(uuid.uuid4())
        m_id = merchant_id or DEFAULT_MERCHANT_ID
        merchant = self.merchants.get(m_id, {"name": DEFAULT_MERCHANT_NAME})
        
        tx_data = {
            "id": tx_id,
            "merchant_id": m_id,
            "merchant_name": merchant.get("name", DEFAULT_MERCHANT_NAME),
            "amount_uzs": float(amount_uzs),
            "amount_usdt": float(amount_usdt),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        self.transactions[tx_id] = tx_data
        return tx_data

    def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        return self.transactions.get(transaction_id)

    def update_transaction_status(
        self, transaction_id: str, status: str
    ) -> Optional[Dict[str, Any]]:
        if transaction_id in self.transactions:
            self.transactions[transaction_id]["status"] = status
            return self.transactions[transaction_id]
        return None


# Инициализация единого экземпляра
_db_instance: Optional[DatabaseService] = None


def init_database() -> DatabaseService:
    global _db_instance
    if _db_instance is not None:
        return _db_instance

    is_valid_supabase = (
        SUPABASE_URL
        and SUPABASE_KEY
        and not SUPABASE_URL.startswith("https://your-project")
        and not SUPABASE_KEY.startswith("your-anon-key")
    )

    if is_valid_supabase:
        try:
            from supabase import create_client
            client = create_client(SUPABASE_URL, SUPABASE_KEY)
            _db_instance = SupabaseDatabaseService(client)
            return _db_instance
        except Exception as e:
            logger.warning(f"Failed to connect to Supabase: {e}. Falling back to In-Memory DB.")

    _db_instance = InMemoryDatabaseService()
    return _db_instance


def get_db() -> DatabaseService:
    """Dependency Provider для внедрения через FastAPI Depends(get_db)"""
    return init_database()
