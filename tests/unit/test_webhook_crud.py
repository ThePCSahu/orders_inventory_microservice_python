"""Unit tests for CRUD operations on Webhook events."""
import pytest

from src.app import models, schemas, crud


class TestWebhookCRUD:
    """Tests for Webhook CRUD functions."""

    def test_record_webhook_event_success(self, db):
        """record_webhook_event records a new event and returns True."""
        result = crud.record_webhook_event(db, "evt_123")
        assert result is True
        
        # Verify it's in database
        event = db.query(models.WebhookEvent).filter_by(event_id="evt_123").first()
        assert event is not None

    def test_record_webhook_event_duplicate_returns_false(self, db):
        """record_webhook_event returns False for duplicate event_id."""
        # Record first time
        crud.record_webhook_event(db, "evt_123")
        
        # Try to record again
        result = crud.record_webhook_event(db, "evt_123")
        assert result is False

    def test_process_payment_webhook_idempotent(self, db):
        """process_payment_webhook is idempotent for same event_id."""
        # Setup: create product and order
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=100
        )
        product = crud.create_product(db, product_data)
        order_data = schemas.OrderCreate(product_id=product.id, quantity=5)
        order = crud.create_order(db, order_data)
        
        # Process payment webhook first time
        result1 = crud.process_payment_webhook(db, "evt_123", order.id)
        assert result1 is True
        
        # Order should be PAID
        updated = crud.get_order(db, order.id)
        assert updated.status == models.OrderStatus.PAID
        
        # Process same event again
        result2 = crud.process_payment_webhook(db, "evt_123", order.id)
        assert result2 is False  # Already processed

    def test_process_payment_webhook_different_events_separate(self, db):
        """process_payment_webhook processes different events separately."""
        # Setup: create two products and orders
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=100
        )
        product = crud.create_product(db, product_data)
        
        order1_data = schemas.OrderCreate(product_id=product.id, quantity=5)
        order1 = crud.create_order(db, order1_data)
        
        order2_data = schemas.OrderCreate(product_id=product.id, quantity=5)
        order2 = crud.create_order(db, order2_data)
        
        # Process first event
        result1 = crud.process_payment_webhook(db, "evt_123", order1.id)
        assert result1 is True
        
        # Process second event (different event_id)
        result2 = crud.process_payment_webhook(db, "evt_456", order2.id)
        assert result2 is True
        
        # Both orders should be PAID
        assert crud.get_order(db, order1.id).status == models.OrderStatus.PAID
        assert crud.get_order(db, order2.id).status == models.OrderStatus.PAID

    def test_process_payment_webhook_order_not_found_raises_error(self, db):
        """process_payment_webhook raises ProductNotFoundError if order not found."""
        with pytest.raises(crud.ProductNotFoundError):
            crud.process_payment_webhook(db, "evt_123", 999)
