"""Integration tests for Product API endpoints."""
import pytest


class TestProductCreate:
    """Tests for POST /products/"""

    def test_create_product_success(self, client):
        """Creating a product with valid data returns 201 with Location header."""
        response = client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        assert response.status_code == 201
        assert "Location" in response.headers
        data = response.json()
        assert data["id"] == 1
        assert data["sku"] == "SKU-001"
        assert data["name"] == "Widget"
        assert data["price"] == 9.99
        assert data["stock"] == 100

    def test_create_product_duplicate_sku_returns_409(self, client):
        """Creating a product with duplicate SKU returns 409 Conflict."""
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        response = client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Other", "price": 5.0, "stock": 50},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "sku already exists"

    def test_create_product_negative_stock_returns_400(self, client):
        """Creating a product with negative stock returns 400."""
        response = client.post(
            "/products/",
            json={"sku": "SKU-002", "name": "Widget", "price": 9.99, "stock": -1},
        )
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_create_product_zero_price_returns_422(self, client):
        """Creating a product with zero price returns 422 (pydantic validation)."""
        response = client.post(
            "/products/",
            json={"sku": "SKU-003", "name": "Widget", "price": 0.0, "stock": 10},
        )
        assert response.status_code == 422

    def test_create_product_negative_price_returns_422(self, client):
        """Creating a product with negative price returns 422."""
        response = client.post(
            "/products/",
            json={"sku": "SKU-004", "name": "Widget", "price": -5.0, "stock": 10},
        )
        assert response.status_code == 422


class TestProductRead:
    """Tests for GET /products/ and GET /products/{id}"""

    def test_get_products_empty(self, client):
        """GET /products/ returns empty list initially."""
        response = client.get("/products/")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["page"] == 1
        assert data["size"] == 10
        assert data["total"] == 0

    def test_get_products_with_pagination(self, client):
        """GET /products/ supports pagination via page and size params."""
        # Create 5 products
        for i in range(5):
            client.post(
                "/products/",
                json={
                    "sku": f"SKU-{i:03d}",
                    "name": f"Product {i}",
                    "price": 10.0 + i,
                    "stock": 100,
                },
            )
        # Get page 1 with size 2
        response = client.get("/products/?page=1&size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["size"] == 2
        assert data["total"] == 5

        # Get page 2
        response = client.get("/products/?page=2&size=2")
        data = response.json()
        assert len(data["items"]) == 2

    def test_get_product_by_id_success(self, client):
        """GET /products/{id} returns product details."""
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        response = client.get("/products/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["sku"] == "SKU-001"
        assert data["name"] == "Widget"

    def test_get_product_by_id_not_found(self, client):
        """GET /products/{id} returns 404 if product not found."""
        response = client.get("/products/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Product not found"


class TestProductUpdate:
    """Tests for PUT /products/{id}"""

    def test_update_product_full(self, client):
        """PUT /products/{id} with full data updates all fields."""
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        response = client.put(
            "/products/1",
            json={"sku": "SKU-002", "name": "Updated Widget", "price": 15.99, "stock": 75},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sku"] == "SKU-002"
        assert data["name"] == "Updated Widget"
        assert data["price"] == 15.99
        assert data["stock"] == 75

    def test_update_product_partial(self, client):
        """PUT /products/{id}?partial=true with partial data updates only provided fields."""
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        response = client.put(
            "/products/1?partial=true",
            json={"price": 15.99},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["price"] == 15.99
        assert data["name"] == "Widget"  # unchanged
        assert data["sku"] == "SKU-001"  # unchanged
        assert data["stock"] == 100  # unchanged

    def test_update_product_partial_multiple_fields(self, client):
        """PUT /products/{id}?partial=true with multiple fields."""
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        response = client.put(
            "/products/1?partial=true",
            json={"name": "Updated Widget", "stock": 75},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Widget"
        assert data["stock"] == 75
        assert data["sku"] == "SKU-001"  # unchanged

    def test_update_product_not_found(self, client):
        """PUT /products/{id} returns 404 if product not found."""
        response = client.put(
            "/products/999",
            json={"sku": "SKU-999", "name": "Ghost", "price": 1.0, "stock": 1},
        )
        assert response.status_code == 404

    def test_update_product_duplicate_sku_returns_409(self, client):
        """PUT /products/{id} with duplicate SKU returns 409."""
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Product 1", "price": 10.0, "stock": 100},
        )
        client.post(
            "/products/",
            json={"sku": "SKU-002", "name": "Product 2", "price": 20.0, "stock": 50},
        )
        response = client.put(
            "/products/2",
            json={"sku": "SKU-001", "name": "Product 2", "price": 20.0, "stock": 50},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "sku already exists"


class TestProductDelete:
    """Tests for DELETE /products/{id}"""

    def test_delete_product_success(self, client):
        """DELETE /products/{id} returns 204 on success."""
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        response = client.delete("/products/1")
        assert response.status_code == 204

    def test_delete_product_not_found(self, client):
        """DELETE /products/{id} returns 404 if product not found."""
        response = client.delete("/products/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Product not found"
