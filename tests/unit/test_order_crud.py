"""Unit tests for CRUD operations on Order model."""
import pytest

from src.app import models, schemas, crud


class TestOrderCRUD:
    """Tests for Order CRUD functions."""

    def test_create_order_atomic_stock_decrement(self, db):
        """create_order atomically decrements product stock."""
        # Setup: create product
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=10
        )
        product = crud.create_product(db, product_data)
        
        # Create order
        order_data = schemas.OrderCreate(product_id=product.id, quantity=5)
        order = crud.create_order(db, order_data)
        
        # Verify order created
        assert order.id is not None
        assert order.quantity == 5
        assert order.status == models.OrderStatus.PENDING
        
        # Verify stock decremented
        updated_product = crud.get_product(db, product.id)
        assert updated_product.stock == 5

    def test_create_order_insufficient_stock_raises_error(self, db):
        """create_order raises InsufficientStockError if stock < quantity."""
        # Setup: create product with low stock
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=3
        )
        product = crud.create_product(db, product_data)
        
        # Try to create order for more than available
        order_data = schemas.OrderCreate(product_id=product.id, quantity=10)
        
        with pytest.raises(crud.InsufficientStockError):
            crud.create_order(db, order_data)

    def test_create_order_product_not_found_raises_error(self, db):
        """create_order raises ProductNotFoundError if product doesn't exist."""
        order_data = schemas.OrderCreate(product_id=999, quantity=5)
        
        with pytest.raises(crud.ProductNotFoundError):
            crud.create_order(db, order_data)

    def test_get_order_success(self, db):
        """get_order returns the order if found."""
        # Setup
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=100
        )
        product = crud.create_product(db, product_data)
        order_data = schemas.OrderCreate(product_id=product.id, quantity=5)
        created = crud.create_order(db, order_data)
        
        # Test
        result = crud.get_order(db, created.id)
        assert result is not None
        assert result.product_id == product.id
        assert result.quantity == 5

    def test_get_order_not_found(self, db):
        """get_order returns None if order not found."""
        result = crud.get_order(db, 999)
        assert result is None

    def test_update_order_status_valid_transition(self, db):
        """update_order_status allows valid status transitions."""
        # Setup
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=100
        )
        product = crud.create_product(db, product_data)
        order_data = schemas.OrderCreate(product_id=product.id, quantity=5)
        order = crud.create_order(db, order_data)
        
        # Update PENDING -> PAID
        result = crud.update_order_status(db, order.id, models.OrderStatus.PAID)
        assert result.status == models.OrderStatus.PAID

    def test_update_order_status_invalid_transition_raises_error(self, db):
        """update_order_status raises ValueError for invalid transitions."""
        # Setup
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=100
        )
        product = crud.create_product(db, product_data)
        order_data = schemas.OrderCreate(product_id=product.id, quantity=5)
        order = crud.create_order(db, order_data)
        
        # Try invalid transition PENDING -> SHIPPED
        with pytest.raises(ValueError, match="Invalid transition"):
            crud.update_order_status(db, order.id, models.OrderStatus.SHIPPED)

    def test_update_order_status_cancel_restores_stock(self, db):
        """update_order_status to CANCELED restores product stock."""
        # Setup
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=10
        )
        product = crud.create_product(db, product_data)
        order_data = schemas.OrderCreate(product_id=product.id, quantity=5)
        order = crud.create_order(db, order_data)
        
        # Verify stock is decremented
        assert crud.get_product(db, product.id).stock == 5
        
        # Cancel order
        crud.update_order_status(db, order.id, models.OrderStatus.CANCELED)
        
        # Verify stock is restored
        assert crud.get_product(db, product.id).stock == 10

    def test_delete_order_pending_removes_order(self, db):
        """delete_order removes PENDING orders entirely."""
        # Setup
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=10
        )
        product = crud.create_product(db, product_data)
        order_data = schemas.OrderCreate(product_id=product.id, quantity=5)
        order = crud.create_order(db, order_data)
        
        # Delete PENDING order
        result = crud.delete_order(db, order.id)
        assert result is True
        
        # Verify it's deleted
        assert crud.get_order(db, order.id) is None
        
        # Verify stock is restored
        assert crud.get_product(db, product.id).stock == 10

    def test_delete_order_paid_converts_to_canceled(self, db):
        """delete_order converts PAID orders to CANCELED."""
        # Setup
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=10
        )
        product = crud.create_product(db, product_data)
        order_data = schemas.OrderCreate(product_id=product.id, quantity=5)
        order = crud.create_order(db, order_data)
        
        # Mark as PAID
        crud.update_order_status(db, order.id, models.OrderStatus.PAID)
        
        # Delete PAID order
        result = crud.delete_order(db, order.id)
        assert result is True
        
        # Verify it's converted to CANCELED
        updated = crud.get_order(db, order.id)
        assert updated.status == models.OrderStatus.CANCELED

    def test_delete_order_shipped_returns_false(self, db):
        """delete_order returns False for SHIPPED orders (cannot delete)."""
        # Setup
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=100
        )
        product = crud.create_product(db, product_data)
        order_data = schemas.OrderCreate(product_id=product.id, quantity=5)
        order = crud.create_order(db, order_data)
        
        # Mark as SHIPPED
        crud.update_order_status(db, order.id, models.OrderStatus.PAID)
        crud.update_order_status(db, order.id, models.OrderStatus.SHIPPED)
        
        # Try to delete SHIPPED order
        result = crud.delete_order(db, order.id)
        assert result is False

    def test_delete_order_not_found_returns_none(self, db):
        """delete_order returns None if order not found."""
        result = crud.delete_order(db, 999)
        assert result is None
