# Test Suite Organization

## Overview
The test suite has been reorganized into **Unit Tests** and **Integration Tests** for better separation of concerns and maintainability.

- **Total Tests**: 73 (28 unit tests + 45 integration tests)
- **All Passing** ✅
- **Execution Time**: < 2 seconds
- **Dependencies**: FastAPI 0.121.2, SQLAlchemy 2.0.44, Starlette 0.49.3, Pytest 9.0.1

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

### Run all tests:
```cmd
python -m pytest tests/ -v
```

### Run only unit tests:
```cmd
python -m pytest tests/unit -v
```

### Run only integration tests:
```cmd
python -m pytest tests/integration -v
```

### Run specific test class:
```cmd
python -m pytest tests/unit/test_product_crud.py::TestProductCRUD -v
```

### Run specific test:
```cmd
python -m pytest tests/integration/test_products.py::TestProductCreate::test_create_product_success -v
```

### Run with coverage:
```cmd
python -m pytest tests/ --cov=src.app --cov-report=term-missing
```

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
