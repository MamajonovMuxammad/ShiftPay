import urllib.request
import json
import time

base = "http://127.0.0.1:8000"

print("--- 1. Testing GET / ---")
resp = urllib.request.urlopen(f"{base}/")
assert resp.status == 200, f"GET / failed: {resp.status}"
print("[OK] GET / returned 200 OK")

print("\n--- 2. Testing GET /cashier ---")
resp = urllib.request.urlopen(f"{base}/cashier")
assert resp.status == 200, f"GET /cashier failed: {resp.status}"
print("[OK] GET /cashier returned 200 OK")

print("\n--- 3. Testing POST /api/invoice ---")
req_data = json.dumps({"amount_uzs": 127000.0}).encode("utf-8")
req = urllib.request.Request(
    f"{base}/api/invoice",
    data=req_data,
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req) as response:
    assert response.status == 201
    data = json.loads(response.read().decode())
    tx_id = data["transaction_id"]
    usdt = data["amount_usdt"]
    assert usdt == 10.0, f"Expected 10.0 USDT, got {usdt}"
    assert data["status"] == "pending"
    print(f"[OK] Created Invoice: tx_id={tx_id}, {data['amount_uzs']} UZS -> {usdt} USDT")

print(f"\n--- 4. Testing GET /api/transactions/{tx_id} (Long Polling) ---")
with urllib.request.urlopen(f"{base}/api/transactions/{tx_id}") as response:
    assert response.status == 200
    tx_status = json.loads(response.read().decode())
    assert tx_status["status"] == "pending"
    print(f"[OK] Polling check: Status is pending")

print(f"\n--- 5. Testing GET /checkout/{tx_id} ---")
with urllib.request.urlopen(f"{base}/checkout/{tx_id}") as response:
    assert response.status == 200
    html = response.read().decode()
    assert "10.00" in html
    assert "USDT" in html
    print(f"[OK] Checkout page rendered with correct USDT amount")

print(f"\n--- 6. Testing POST /api/pay/{tx_id} (MockUzNEXGateway 2s delay) ---")
t0 = time.time()
pay_req = urllib.request.Request(
    f"{base}/api/pay/{tx_id}",
    data=b"{}",
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(pay_req) as response:
    assert response.status == 200
    pay_res = json.loads(response.read().decode())
    elapsed = time.time() - t0
    assert pay_res["status"] == "success"
    print(f"[OK] Payment processed in {elapsed:.2f}s! Message: {pay_res['message']}")

print(f"\n--- 7. Verifying status after payment ---")
with urllib.request.urlopen(f"{base}/api/transactions/{tx_id}") as response:
    assert response.status == 200
    tx_status = json.loads(response.read().decode())
    assert tx_status["status"] == "success"
    print(f"[OK] Final status is SUCCESS! Cashier terminal will transition to receipt.")

print("\n================================================")
print("  ALL SHIFT PAY MVP INTEGRATION TESTS PASSED!   ")
print("================================================")
