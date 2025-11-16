from sqlalchemy.orm import Session
from .. import models, schemas
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import IntegrityError as SAIntegrityError
from ..models import WebhookEvent
import os
from sqlalchemy import update


# Domain exceptions for deterministic error handling

class ProductNotFoundError(Exception):
    pass


class InsufficientStockError(Exception):
    pass


def get_product(db: Session, product_id: int):
    return db.query(models.Product).filter(models.Product.id == product_id).first()


def get_products(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Product).offset(skip).limit(limit).all()


def count_products(db: Session):
    return db.query(models.Product).count()


def create_product(db: Session, product: schemas.ProductCreate):
    db_product = models.Product(sku=product.sku, name=product.name, price=product.price, stock=product.stock)
    db.add(db_product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(db_product)
    return db_product


def update_product(db: Session, product_id: int, product: schemas.ProductCreate):
    db_product = get_product(db, product_id)
    if not db_product:
        return None
    db_product.sku = product.sku
    db_product.name = product.name
    db_product.price = product.price
    db_product.stock = product.stock
    db.commit()
    db.refresh(db_product)
    return db_product


def update_product_partial(db: Session, product_id: int, product: schemas.ProductUpdate):
    db_product = get_product(db, product_id)
    if not db_product:
        return None
    # Only update provided fields
    if product.sku is not None:
        db_product.sku = product.sku
    if product.name is not None:
        db_product.name = product.name
    if product.price is not None:
        db_product.price = product.price
    if product.stock is not None:
        db_product.stock = product.stock
    db.commit()
    db.refresh(db_product)
    return db_product


def delete_product(db: Session, product_id: int):
    db_product = get_product(db, product_id)
    if not db_product:
        return None
    db.delete(db_product)
    db.commit()
    return db_product


def create_order(db: Session, order: schemas.OrderCreate):
    """Create an order with atomic stock decrement using SELECT FOR UPDATE for better concurrency control.
    
    Uses pessimistic locking to prevent race conditions under high load.
    """
    # Use SELECT FOR UPDATE to lock the product row, preventing concurrent modifications
    # This ensures that only one transaction can check and update stock at a time
    product = (
        db.query(models.Product)
        .filter(models.Product.id == order.product_id)
        .with_for_update(nowait=False)  # Wait for lock, don't fail immediately
        .first()
    )
    
    if not product:
        raise ProductNotFoundError("Product not found")
    
    # Check stock availability while holding the lock
    if product.stock < order.quantity:
        raise InsufficientStockError("Insufficient stock")
    
    # Atomically decrement stock
    product.stock = product.stock - order.quantity
    
    # Create the order record
    db_order = models.Order(product_id=order.product_id, quantity=order.quantity)
    db.add(db_order)
    db.commit()  # Commit both the stock update and order creation
    db.refresh(db_order)
    return db_order


def update_order_status(db: Session, order_id: int, new_status: models.OrderStatus):
    db_order = get_order(db, order_id)
    if not db_order:
        return None
    # Define allowed transitions
    current = db_order.status
    allowed = {
        models.OrderStatus.PENDING: {models.OrderStatus.PAID, models.OrderStatus.CANCELED},
        models.OrderStatus.PAID: {models.OrderStatus.SHIPPED, models.OrderStatus.CANCELED},
        models.OrderStatus.SHIPPED: set(),
        models.OrderStatus.CANCELED: set(),
    }
    if new_status == current:
        return db_order
    if new_status not in allowed.get(current, set()):
        # invalid transition
        raise ValueError(f"Invalid transition from {current} to {new_status}")
    # If canceling, restore stock with locking to prevent race conditions
    if new_status == models.OrderStatus.CANCELED:
        product = (
            db.query(models.Product)
            .filter(models.Product.id == db_order.product_id)
            .with_for_update(nowait=False)
            .first()
        )
        if product:
            product.stock = product.stock + db_order.quantity
    db_order.status = new_status
    db.commit()
    db.refresh(db_order)
    return db_order


def delete_order(db: Session, order_id: int):
    db_order = get_order(db, order_id)
    if not db_order:
        return None
    # allow full deletion only for PENDING orders
    if db_order.status == models.OrderStatus.PENDING:
        # restore stock with locking to prevent race conditions
        product = (
            db.query(models.Product)
            .filter(models.Product.id == db_order.product_id)
            .with_for_update(nowait=False)
            .first()
        )
        if product:
            product.stock = product.stock + db_order.quantity
        db.delete(db_order)
        db.commit()
        return True
    # otherwise, convert to CANCELED if possible (not SHIPPED)
    if db_order.status in (models.OrderStatus.PAID, models.OrderStatus.PENDING):
        update_order_status(db, order_id, models.OrderStatus.CANCELED)
        return True
    # cannot delete or cancel shipped orders
    return False


def get_order(db: Session, order_id: int):
    return db.query(models.Order).filter(models.Order.id == order_id).first()


def record_webhook_event(db: Session, event_id: str) -> bool:
    """Try to record the webhook event id. Returns True if recorded, False if it already existed."""
    evt = WebhookEvent(event_id=event_id)
    db.add(evt)
    try:
        db.commit()
        return True
    except SAIntegrityError:
        db.rollback()
        return False


def process_payment_webhook(db: Session, event_id: str, order_id: int):
    """Idempotent processing of a payment.succeeded webhook.

    - Records the event id to prevent replays.
    - If recorded for the first time, updates the order status to PAID.
    - Returns:
       - True if processed now
       - False if event was already seen
       - Raises ProductNotFoundError if order not found
    """
    # Check if order exists first
    db_order = get_order(db, order_id)
    if not db_order:
        raise ProductNotFoundError("Order not found")
    
    # Attempt to record event; if already exists, treat as replay and return False
    recorded = record_webhook_event(db, event_id)
    if not recorded:
        return False

    # Proceed to mark the order as PAID
    try:
        updated = update_order_status(db, order_id, models.OrderStatus.PAID)
        return True
    except Exception:
        # rollback the event record
        db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).delete()
        raise
