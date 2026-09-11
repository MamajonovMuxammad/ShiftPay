"""
Shift Pay - Production-Ready MVP Crypto Acquiring
FastAPI Entry Point with Dependency Injection, Jinja2 Templates, CORS, and REST API.
"""

import os
import logging
from typing import Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

from database import DatabaseService, get_db
from mock_gateway import CryptoGatewayAdapter, get_gateway
from schemas import InvoiceCreate, InvoiceResponse, TransactionResponse, PaymentResponse

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("shiftpay.main")

# Конфигурация курса: 1 USDT = 12 700 UZS
EXCHANGE_RATE_USDT_UZS = float(os.getenv("EXCHANGE_RATE_USDT_UZS", "12700"))

app = FastAPI(
    title="Shift Pay B2C Crypto-Acquiring",
    description="Премиальный шлюз крипто-эквайринга для офлайн ритейла (UZS -> USDT)",
    version="1.0.0"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация шаблонов Jinja2
BASE_DIR = Path(__file__).resolve().parent
possible_dirs = [
    BASE_DIR / "templates",
    BASE_DIR.parent / "templates",
    Path.cwd() / "templates",
    Path("/var/task/templates")
]
TEMPLATES_DIR = next((p for p in possible_dirs if p.exists() and p.is_dir()), BASE_DIR / "templates")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ==========================================
# REST API ENDPOINTS
# ==========================================

@app.post(
    "/api/invoice",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создание счета на оплату (Терминал кассира)"
)
@app.post("/api/index.py/api/invoice", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_invoice(
    payload: InvoiceCreate,
    request: Request,
    db: DatabaseService = Depends(get_db)
):
    """
    Принимает сумму в национальной валюте UZS.
    Рассчитывает сумму в USDT по фиксированному курсу (1 USDT = 12 700 UZS).
    Создает запись в transactions со статусом 'pending' и возвращает ID с ссылкой на оплату.
    """
    if payload.amount_uzs <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сумма счета должна быть больше нуля."
        )

    # Конвертация в USDT с точностью до 2 десятичных знаков
    amount_usdt = round(payload.amount_uzs / EXCHANGE_RATE_USDT_UZS, 2)
    # Если сумма меньше 0.01 USDT, показываем 4 знака
    if amount_usdt == 0:
        amount_usdt = round(payload.amount_uzs / EXCHANGE_RATE_USDT_UZS, 4)

    tx = db.create_transaction(
        amount_uzs=payload.amount_uzs,
        amount_usdt=amount_usdt
    )

    # Учитываем прокси заголовки (Vercel, Cloudflare, Nginx)
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if forwarded_proto and forwarded_host:
        base_url = f"{forwarded_proto}://{forwarded_host}".rstrip("/")
    else:
        base_url = str(request.base_url).rstrip("/")

    checkout_url = f"{base_url}/checkout/{tx['id']}"

    return InvoiceResponse(
        transaction_id=tx["id"],
        amount_uzs=tx["amount_uzs"],
        amount_usdt=tx["amount_usdt"],
        status=tx["status"],
        checkout_url=checkout_url,
        created_at=tx["created_at"]
    )


@app.get(
    "/api/transactions/{transaction_id}",
    response_model=TransactionResponse,
    summary="Получение статуса транзакции (Long Polling)"
)
@app.get("/api/index.py/api/transactions/{transaction_id}", response_model=TransactionResponse, include_in_schema=False)
async def get_transaction(
    transaction_id: str,
    db: DatabaseService = Depends(get_db)
):
    """
    Возвращает актуальный статус транзакции для Long Polling опроса интерфейсом кассира.
    """
    tx = db.get_transaction(transaction_id)
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Транзакция не найдена."
        )

    return TransactionResponse(
        id=tx["id"],
        merchant_id=tx.get("merchant_id"),
        merchant_name=tx.get("merchant_name", "Shift Pay Flagship Store"),
        amount_uzs=tx["amount_uzs"],
        amount_usdt=tx["amount_usdt"],
        status=tx["status"],
        created_at=tx["created_at"]
    )


@app.post(
    "/api/pay/{transaction_id}",
    response_model=PaymentResponse,
    summary="Подтверждение и обработка платежа клиентом"
)
@app.post("/api/index.py/api/pay/{transaction_id}", response_model=PaymentResponse, include_in_schema=False)
async def process_payment(
    transaction_id: str,
    gateway: CryptoGatewayAdapter = Depends(get_gateway)
):
    """
    Вызывает MockUzNEXGateway.process_payment(), который эмулирует задержку сети 2 сек
    и переводит статус транзакции в 'success'.
    """
    try:
        result = await gateway.process_payment(transaction_id)
        return PaymentResponse(
            status=result["status"],
            message=result["message"],
            transaction_id=result["transaction_id"]
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Payment gateway error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка крипто-шлюза."
        )


# ==========================================
# FRONTEND TEMPLATE ROUTES
# ==========================================

@app.get("/", response_class=HTMLResponse, summary="Главная страница (Выбор интерфейса)")
@app.get("/api/index.py", response_class=HTMLResponse, include_in_schema=False)
@app.get("/api/index", response_class=HTMLResponse, include_in_schema=False)
@app.get("/api", response_class=HTMLResponse, include_in_schema=False)
async def page_index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"exchange_rate": int(EXCHANGE_RATE_USDT_UZS)}
    )


@app.get("/cashier", response_class=HTMLResponse, summary="Терминал кассира")
@app.get("/api/index.py/cashier", response_class=HTMLResponse, include_in_schema=False)
async def page_cashier(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="cashier.html",
        context={"exchange_rate": int(EXCHANGE_RATE_USDT_UZS)}
    )


@app.get("/scanner", response_class=HTMLResponse, summary="Сканнер QR-кода покупателя")
@app.get("/api/index.py/scanner", response_class=HTMLResponse, include_in_schema=False)
async def page_scanner(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="scanner.html",
        context={}
    )


@app.get("/checkout/{transaction_id}", response_class=HTMLResponse, summary="Экран оплаты покупателя")
@app.get("/api/index.py/checkout/{transaction_id}", response_class=HTMLResponse, include_in_schema=False)
async def page_checkout(
    request: Request,
    transaction_id: str,
    db: DatabaseService = Depends(get_db)
):
    tx = db.get_transaction(transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Транзакция не найдена")

    return templates.TemplateResponse(
        request=request,
        name="checkout.html",
        context={
            "tx": tx,
            "exchange_rate": int(EXCHANGE_RATE_USDT_UZS)
        }
    )



if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Запуск сервера Shift Pay на http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)
