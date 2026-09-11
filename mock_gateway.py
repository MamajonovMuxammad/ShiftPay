"""
Adapter Pattern implementation for Crypto Acquiring Gateways.
Provides seamless mock integration with UzNEX / TRON Tether Gateway.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from fastapi import Depends
from database import DatabaseService, get_db

logger = logging.getLogger("shiftpay.gateway")


class CryptoGatewayAdapter(ABC):
    """Абстрактный адаптер крипто-шлюза (Adapter Pattern)"""

    @abstractmethod
    async def process_payment(self, transaction_id: str) -> Dict[str, Any]:
        """Обработка платежа покупателя и подтверждение блокчейн-транзакции"""
        pass


class MockUzNEXGateway(CryptoGatewayAdapter):
    """
    Адаптер имитации крипто-шлюза UzNEX (Tether USDT TRC-20 / TON).
    Имитирует валидацию смарт-контракта и списание с кошелька за 2 секунды.
    """

    def __init__(self, db: DatabaseService):
        self.db = db

    async def process_payment(self, transaction_id: str) -> Dict[str, Any]:
        logger.info(f"[MockUzNEXGateway] Initiating payment for transaction {transaction_id}...")

        # Проверяем существование транзакции
        tx = self.db.get_transaction(transaction_id)
        if not tx:
            raise ValueError(f"Транзакция с ID {transaction_id} не найдена.")

        if tx.get("status") == "success":
            return {
                "status": "success",
                "message": "Платеж уже был успешно подтвержден ранее.",
                "transaction_id": transaction_id
            }

        # 1. Переводим статус в processing
        self.db.update_transaction_status(transaction_id, "processing")
        logger.info(f"[MockUzNEXGateway] Tx {transaction_id} status changed to 'processing'. Verifying network...")

        # 2. Имитация блокчейн-подтверждения транзакции в сети UzNEX (2 секунды)
        await asyncio.sleep(2)

        # 3. Переводим статус в success
        updated_tx = self.db.update_transaction_status(transaction_id, "success")
        logger.info(f"[MockUzNEXGateway] Tx {transaction_id} successfully confirmed on-chain! Status: 'success'.")

        return {
            "status": "success",
            "message": "Платеж успешно подтвержден крипто-шлюзом UzNEX.",
            "transaction_id": transaction_id,
            "transaction": updated_tx
        }


def get_gateway(db: DatabaseService = Depends(get_db)) -> CryptoGatewayAdapter:
    """Dependency Provider для FastAPI Depends()"""
    return MockUzNEXGateway(db=db)
