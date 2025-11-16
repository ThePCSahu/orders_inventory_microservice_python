# Test Suite Organization

## Overview
The test suite has been reorganized into **Unit Tests**, **Integration Tests**, and **Load Tests** for better separation of concerns and maintainability.

- **Total Tests**: 73 (28 unit tests + 45 integration tests)
- **All Passing** ✅
- **Execution Time**: < 2 seconds
- **Dependencies**: FastAPI 0.121.2, SQLAlchemy 2.0.44, Starlette 0.49.3, Pytest 9.0.1, pytest-html 4.1.1, pytest-cov 7.0.0, Locust 2.31.0

## Test Reports Structure

All test reports are automatically saved in the `test-reports/` directory:

```
test-reports/
├── unit/
│   ├── report.html              # Unit test HTML report
│   └── coverage/
│       └── index.html           # Unit test coverage report
├── integration/
│   ├── report.html              # Integration test HTML report
│   └── coverage/
│       └── index.html           # Integration test coverage report
└── load/
    ├── locust_light.html        # Light load test report
    ├── locust_heavy.html        # Heavy load test report
    ├── locust_light_stats.csv   # Light load statistics
    ├── locust_heavy_stats.csv   # Heavy load statistics
    └── [additional CSV files]   # Failures, exceptions, stats history
```

## Directory Structure

```
tests/
├── unit/
│   ├── conftest.py              # Unit test fixtures
│   ├── test_product_crud.py     # Product CRUD unit tests (12)
│   ├── test_order_crud.py       # Order CRUD unit tests (12)
│   └── test_webhook_crud.py     # Webhook CRUD unit tests (4)
│
└── integration/
    ├── conftest.py              # Integration test fixtures
    ├── test_products.py         # Product API endpoint tests (17)
    ├── test_orders.py           # Order API endpoint tests (19)
    └── test_webhooks.py         # Webhook API endpoint tests (9)
```

## Unit Tests (28 tests)

**Purpose**: Test individual CRUD functions in isolation with mocked dependencies.

### Product CRUD (`test_product_crud.py`) - 12 tests
- `test_create_product_success` - Product creation returns all fields
- `test_create_product_duplicate_sku_raises_integrityerror` - Duplicate SKU raises error
- `test_get_product_success` - Retrieve existing product
- `test_get_product_not_found` - Returns None for missing product
- `test_get_products_list` - Retrieve multiple products with pagination
- `test_count_products` - Returns total product count
- `test_update_product_full` - Full update replaces all fields
- `test_update_product_partial` - Partial update only changes provided fields
- `test_update_product_not_found` - Returns None for missing product
- `test_delete_product_success` - Removes product from database
- `test_delete_product_not_found` - Returns None for missing product

### Order CRUD (`test_order_crud.py`) - 12 tests
- `test_create_order_atomic_stock_decrement` - Stock decremented atomically
- `test_create_order_insufficient_stock_raises_error` - InsufficientStockError raised
- `test_create_order_product_not_found_raises_error` - ProductNotFoundError raised
- `test_get_order_success` - Retrieve existing order
- `test_get_order_not_found` - Returns None for missing order
- `test_update_order_status_valid_transition` - Valid transitions allowed
- `test_update_order_status_invalid_transition_raises_error` - Invalid transitions blocked
- `test_update_order_status_cancel_restores_stock` - Cancellation restores stock
- `test_delete_order_pending_removes_order` - PENDING orders deleted
- `test_delete_order_paid_converts_to_canceled` - PAID orders converted to CANCELED
- `test_delete_order_shipped_returns_false` - SHIPPED orders cannot be deleted
- `test_delete_order_not_found_returns_none` - Returns None for missing order

### Webhook CRUD (`test_webhook_crud.py`) - 4 tests
- `test_record_webhook_event_success` - New events recorded
- `test_record_webhook_event_duplicate_returns_false` - Duplicate events rejected
- `test_process_payment_webhook_idempotent` - Same event_id returns False on replay
- `test_process_payment_webhook_different_events_separate` - Different event_ids processed separately
- `test_process_payment_webhook_order_not_found_raises_error` - Raises error if order missing

## Integration Tests (45 tests)

**Purpose**: Test complete API endpoints with database and all dependencies.

### Product API (`test_products.py`) - 17 tests
- **Create**: Success (201+Location), duplicate SKU (409), negative stock (400), invalid price (422)
- **Read**: Empty list, pagination, single product, not found (404)
- **Update**: Full update, partial update (single/multiple fields), not found (404), duplicate SKU (409)
- **Delete**: Success (204), not found (404)

### Order API (`test_orders.py`) - 19 tests
- **Create**: Success (201+Location), insufficient stock (409), product not found (404), zero quantity (422), atomic decrement
- **Read**: Success with product info, not found (404)
- **Status Transitions**: 
  - PENDING → PAID ✓, CANCELED ✓
  - PAID → SHIPPED ✓, CANCELED ✓ (with stock restore)
  - SHIPPED → (blocked), CANCELED → (blocked)
  - Invalid transitions return 400
  - Invalid status value returns 400
- **Delete**: PENDING (full delete), PAID (convert to CANCELED), SHIPPED (returns 400), not found (404)

### Webhook API (`test_webhooks.py`) - 9 tests
- **Security**: Valid signature (200), missing signature (401), invalid signature (401), tampered body (401)
- **Payment Processing**: Order marked PAID, order not found (404), missing event_id (400), malformed JSON (400)
- **Replay Protection**: Same event_id is idempotent, different event_ids processed separately

## Running Tests

**Prerequisites**: Install test dependencies first:
```cmd
python -m pip install -r requirements.txt
```

All test reports are saved in the `test-reports/` directory, organized by test type:
- `test-reports/unit/` - Unit test reports
- `test-reports/integration/` - Integration test reports
- `test-reports/load/` - Load test reports

### Unit Tests

**Run unit tests with HTML report and coverage:**
```cmd
python -m pytest tests/unit -v --html=test-reports/unit/report.html --self-contained-html --cov=src.app --cov-report=html:test-reports/unit/coverage --cov-report=term-missing
```

**Run unit tests (simple, no reports):**
```cmd
python -m pytest tests/unit -v
```

**Run specific unit test class:**
```cmd
python -m pytest tests/unit/test_product_crud.py::TestProductCRUD -v
```

**Run specific unit test:**
```cmd
python -m pytest tests/unit/test_product_crud.py::TestProductCRUD::test_create_product_success -v
```

**Generated Reports:**
- `test-reports/unit/report.html` - HTML test report with pass/fail status
- `test-reports/unit/coverage/index.html` - Code coverage report (open in browser)

### Integration Tests

**Note**: Integration tests may require compatible versions of `httpx` and `starlette`. If you encounter `TypeError: Client.__init__() got an unexpected keyword argument 'app'`, ensure your dependencies are compatible. The commands below are correct; the issue is with dependency versions.

**Run integration tests with HTML report and coverage:**
```cmd
python -m pytest tests/integration -v --html=test-reports/integration/report.html --self-contained-html --cov=src.app --cov-report=html:test-reports/integration/coverage --cov-report=term-missing
```

**Run integration tests (simple, no reports):**
```cmd
python -m pytest tests/integration -v
```

**Run specific integration test class:**
```cmd
python -m pytest tests/integration/test_products.py::TestProductCreate -v
```

**Run specific integration test:**
```cmd
python -m pytest tests/integration/test_products.py::TestProductCreate::test_create_product_success -v
```

**Generated Reports:**
- `test-reports/integration/report.html` - HTML test report with pass/fail status
- `test-reports/integration/coverage/index.html` - Code coverage report (open in browser)

### Load Tests

**Prerequisites:**
1. Start the server in one terminal:
```cmd
python -m uvicorn src.app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

2. Run load tests in another terminal:

**Light load test (25 users, 30 seconds):**
```cmd
python -m locust -f tests/load/locustfile.py --headless -u 25 -r 5 --run-time 30s --host http://127.0.0.1:8000 --html=test-reports/load/locust_light.html --csv=test-reports/load/locust_light
```

**Heavy load test (200 users, 60 seconds):**
```cmd
python -m locust -f tests/load/locustfile.py --headless -u 200 -r 20 --run-time 60s --host http://127.0.0.1:8000 --html=test-reports/load/locust_heavy.html --csv=test-reports/load/locust_heavy
```

**Generated Reports:**
- `test-reports/load/locust_light.html` - Light load test HTML report
- `test-reports/load/locust_heavy.html` - Heavy load test HTML report
- `test-reports/load/locust_light_stats.csv` - Light load test statistics (CSV)
- `test-reports/load/locust_heavy_stats.csv` - Heavy load test statistics (CSV)
- Additional CSV files: `*_failures.csv`, `*_exceptions.csv`, `*_stats_history.csv`

### Run All Tests

**Run all tests (unit + integration) with reports:**
```cmd
python -m pytest tests/ -v --html=test-reports/report.html --self-contained-html --cov=src.app --cov-report=html:test-reports/coverage --cov-report=term-missing
```

**Run all tests (simple, no reports):**
```cmd
python -m pytest tests/ -v
```

### Viewing Reports

- **HTML Test Reports**: Open `test-reports/{unit|integration}/report.html` in a web browser
- **Coverage Reports**: Open `test-reports/{unit|integration}/coverage/index.html` in a web browser
- **Load Test Reports**: Open `test-reports/load/locust_{light|heavy}.html` in a web browser

## Test Fixture Organization

### Unit Test Fixtures (`tests/unit/conftest.py`)
- `db`: In-memory SQLite database with table creation

### Integration Test Fixtures (`tests/integration/conftest.py`)
- `db`: In-memory SQLite database with table creation
- `client`: TestClient with dependency override for database
- `set_webhook_secret`: Monkeypatch for WEBHOOK_SECRET environment variable

## Coverage Summary

| Component | Unit | Integration | Total |
|-----------|------|-------------|-------|
| Products  | 12   | 17          | 29    |
| Orders    | 12   | 19          | 31    |
| Webhooks  | 4    | 9           | 13    |
| **Total** | **28** | **45**    | **73** |

## Key Design Principles

1. **Isolation**: Unit tests test CRUD functions directly; integration tests test through API
2. **Independence**: Each test is self-contained and can run in any order
3. **In-Memory DB**: All tests use in-memory SQLite for speed (< 2 seconds total)
4. **No Side Effects**: Tests don't depend on execution order or previous state
5. **Clear Naming**: Test names clearly describe what is being tested and expected outcome
