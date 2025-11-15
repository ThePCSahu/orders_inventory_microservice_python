"""CRUD package re-exports for easy imports from `src.app.crud`."""
from .crud import (
    get_product,
    get_products,
    count_products,
    create_product,
    update_product,
    update_product_partial,
    delete_product,
    create_order,
    get_order,
    update_order_status,
    delete_order,
    record_webhook_event,
    process_payment_webhook,
)

__all__ = [
    "get_product",
    "get_products",
    "count_products",
    "create_product",
    "update_product",
    "update_product_partial",
    "delete_product",
    "create_order",
    "get_order",
    "update_order_status",
    "delete_order",
    "record_webhook_event",
    "process_payment_webhook",
]

# re-export exceptions
from .crud import ProductNotFoundError, InsufficientStockError
__all__.extend(["ProductNotFoundError", "InsufficientStockError"])
