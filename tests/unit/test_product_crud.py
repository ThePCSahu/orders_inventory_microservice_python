"""Unit tests for CRUD operations on Product model."""
import pytest
from sqlalchemy.exc import IntegrityError

from src.app import models, schemas, crud


class TestProductCRUD:
    """Tests for Product CRUD functions."""

    def test_create_product_success(self, db):
        """Creating a product returns the product with all fields."""
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=100
        )
        result = crud.create_product(db, product_data)
        assert result.id is not None
        assert result.sku == "SKU-001"
        assert result.name == "Widget"
        assert result.price == 9.99
        assert result.stock == 100

    def test_create_product_duplicate_sku_raises_integrityerror(self, db):
        """Creating a product with duplicate SKU raises IntegrityError."""
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=100
        )
        crud.create_product(db, product_data)
        
        # Try to create another with same SKU
        with pytest.raises(IntegrityError):
            crud.create_product(db, product_data)

    def test_get_product_success(self, db):
        """get_product returns the product if found."""
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=100
        )
        created = crud.create_product(db, product_data)
        
        result = crud.get_product(db, created.id)
        assert result is not None
        assert result.sku == "SKU-001"

    def test_get_product_not_found(self, db):
        """get_product returns None if product not found."""
        result = crud.get_product(db, 999)
        assert result is None

    def test_get_products_list(self, db):
        """get_products returns all products with pagination."""
        for i in range(5):
            product_data = schemas.ProductCreate(
                sku=f"SKU-{i:03d}", name=f"Product {i}", price=10.0 + i, stock=100
            )
            crud.create_product(db, product_data)
        
        result = crud.get_products(db, skip=0, limit=10)
        assert len(result) == 5

    def test_count_products(self, db):
        """count_products returns total product count."""
        for i in range(3):
            product_data = schemas.ProductCreate(
                sku=f"SKU-{i:03d}", name=f"Product {i}", price=10.0 + i, stock=100
            )
            crud.create_product(db, product_data)
        
        count = crud.count_products(db)
        assert count == 3

    def test_update_product_full(self, db):
        """update_product replaces all fields."""
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=100
        )
        created = crud.create_product(db, product_data)
        
        updated_data = schemas.ProductCreate(
            sku="SKU-002", name="Updated Widget", price=19.99, stock=50
        )
        result = crud.update_product(db, created.id, updated_data)
        
        assert result.sku == "SKU-002"
        assert result.name == "Updated Widget"
        assert result.price == 19.99
        assert result.stock == 50

    def test_update_product_partial(self, db):
        """update_product_partial only updates provided fields."""
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=100
        )
        created = crud.create_product(db, product_data)
        
        update_data = schemas.ProductUpdate(price=15.99)
        result = crud.update_product_partial(db, created.id, update_data)
        
        assert result.price == 15.99
        assert result.sku == "SKU-001"  # unchanged
        assert result.name == "Widget"   # unchanged
        assert result.stock == 100       # unchanged

    def test_update_product_not_found(self, db):
        """update_product returns None if product not found."""
        update_data = schemas.ProductCreate(
            sku="SKU-999", name="Ghost", price=1.0, stock=1
        )
        result = crud.update_product(db, 999, update_data)
        assert result is None

    def test_delete_product_success(self, db):
        """delete_product removes the product from database."""
        product_data = schemas.ProductCreate(
            sku="SKU-001", name="Widget", price=9.99, stock=100
        )
        created = crud.create_product(db, product_data)
        
        result = crud.delete_product(db, created.id)
        assert result is not None
        
        # Verify it's deleted
        retrieved = crud.get_product(db, created.id)
        assert retrieved is None

    def test_delete_product_not_found(self, db):
        """delete_product returns None if product not found."""
        result = crud.delete_product(db, 999)
        assert result is None
