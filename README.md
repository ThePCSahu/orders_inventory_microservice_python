# Orders Inventory Microservice

A production-ready FastAPI microservice for orders and inventory management with:
- **Layered Architecture**: Models, Schemas, CRUD, Database, API layers
- **Atomic Order Creation**: Concurrent-safe stock decrement using conditional SQL updates
- **Webhook Security**: HMAC-SHA256 signature verification with replay protection
- **Complete API Documentation**: Swagger UI with examples for every endpoint
- **Deterministic Error Handling**: Consistent JSON error responses
- **Full Test Coverage**: Unit tests for all endpoints, CRUD ops, and webhook flows

## Quick Start (Windows cmd.exe)

### 1. Activate virtualenv and install dependencies
```cmd
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the API
```cmd
uvicorn src.app.main:app --reload
```
Open http://127.0.0.1:8000/docs for Swagger UI with interactive examples.

### 3. Run tests
```cmd
python -m pytest tests/ -v
```

### 4. Run specific test directory
```cmd
python -m pytest tests/unit -v
python -m pytest tests/integration -v
```

### 5. Run specific test file
```cmd
python -m pytest tests/integration/test_products.py -v
python -m pytest tests/integration/test_orders.py -v
python -m pytest tests/integration/test_webhooks.py -v
```

## Project Structure

```
src/app/
  ├── main.py              # FastAPI app and endpoints
  ├── models/              # SQLAlchemy ORM models (Product, Order, WebhookEvent)
  ├── schemas/             # Pydantic request/response schemas with examples
  ├── crud/                # Business logic (CRUD operations, webhook processing)
  └── database/            # SQLAlchemy session and engine setup

tests/
  ├── unit/
  │   ├── conftest.py              # Unit test fixtures
  │   ├── test_product_crud.py     # Product CRUD unit tests
  │   ├── test_order_crud.py       # Order CRUD unit tests
  │   └── test_webhook_crud.py     # Webhook CRUD unit tests
  └── integration/
      ├── conftest.py              # Integration test fixtures
      ├── test_products.py         # Product API endpoint tests
      ├── test_orders.py           # Order API endpoint tests
      └── test_webhooks.py         # Webhook API endpoint tests

requirements.txt           # Pinned dependencies
.venv/                     # Virtual environment (created)
```

## Key Features

### Products API
- `POST /products/` — Create product (returns 201 with Location header)
- `GET /products/` — List products with pagination (page, size)
- `GET /products/{id}` — Get product (404 if not found)
- `PUT /products/{id}` — Full or partial update (use ?partial=true)
- `DELETE /products/{id}` — Delete product (204 on success)

### Orders API
- `POST /orders/` — Create order (atomic stock decrement, 409 on insufficient stock)
- `GET /orders/{id}` — Get order with nested product details
- `PUT /orders/{id}` — Update order status (enforced state transitions)
- `DELETE /orders/{id}` — Delete or cancel order (restores stock on cancel)

### Webhook API
- `POST /webhooks/payment` — Payment provider webhook receiver
  - Verifies HMAC-SHA256 signature in `X-Signature` header
  - Processes `payment.succeeded` events (marks order as PAID)
  - Prevents replay attacks via unique event_id tracking

## Test Coverage

### Product Tests (test_products.py)
- Create product (201, 409 duplicate SKU, 400 invalid price)
- List with pagination (empty, valid pages, invalid page)
- Get by id (200, 404)
- Update full and partial (200, 404, 409 duplicate SKU)
- Delete (204, 404)

### Order Tests (test_orders.py)
- Create order (201, 409 insufficient stock, 404 product not found)
- Get order with product details (200, 404)
- Status transitions (PENDING → PAID/CANCELED, PAID → SHIPPED/CANCELED, SHIPPED/CANCELED → no transitions)
- Stock restoration on cancel/delete
- Delete order (200 PENDING, convert PAID to CANCELED, 400 SHIPPED)

### Webhook Tests (test_webhooks.py)
- HMAC-SHA256 signature verification (201 valid, 401 invalid/missing)
- Tampered body fails signature (401)
- Payment processing (order marked PAID, 404 if order missing)
- Malformed JSON returns 400
- Replay protection (same event_id returns "event already processed", idempotent)
- Different event_ids process separately

## Environment Variables

```cmd
set WEBHOOK_SECRET=your-secret-here
```
Store the webhook secret securely (e.g., .env file, secrets manager). Do not commit it.

## Deterministic Error Responses

All API errors return a consistent JSON shape:
```json
{"detail": "error message"}
```

Example:
- 400: `{"detail": "stock must be >= 0"}`
- 404: `{"detail": "Product not found"}`
- 409: `{"detail": "sku already exists"}` or `{"detail": "Insufficient stock"}`
- 401: `{"detail": "invalid signature"}`

## Running Tests

### Full test suite
```cmd
python -m pytest tests/ -v
```

### Run unit tests only
```cmd
python -m pytest tests/unit -v
```

### Run integration tests only
```cmd
python -m pytest tests/integration -v
```

### With coverage report
```cmd
python -m pytest tests/ --cov=src.app --cov-report=term-missing
```

### Run specific test class
```cmd
python -m pytest tests/integration/test_products.py::TestProductCreate -v
```

### Run single test
```cmd
python -m pytest tests/integration/test_webhooks.py::TestWebhookReplayProtection::test_webhook_idempotent_replay_same_event_id -v
```
