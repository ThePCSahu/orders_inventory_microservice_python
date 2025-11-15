"""Integration tests for Order API endpoints."""
import pytest


class TestOrderCreate:
    """Tests for POST /orders/"""

    def test_create_order_success(self, client):
        """Creating an order with sufficient stock returns 201."""
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        response = client.post("/orders/", json={"product_id": 1, "quantity": 5})
        assert response.status_code == 201
        assert "Location" in response.headers
        data = response.json()
        assert data["id"] == 1
        assert data["product_id"] == 1
        assert data["quantity"] == 5
        assert data["status"] == "PENDING"

    def test_create_order_insufficient_stock_returns_409(self, client):
        """Creating an order with insufficient stock returns 409."""
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 5},
        )
        response = client.post("/orders/", json={"product_id": 1, "quantity": 10})
        assert response.status_code == 409
        assert response.json()["detail"] == "Insufficient stock"

    def test_create_order_product_not_found_returns_404(self, client):
        """Creating an order for non-existent product returns 404."""
        response = client.post("/orders/", json={"product_id": 999, "quantity": 5})
        assert response.status_code == 404
        assert response.json()["detail"] == "Product not found"

    def test_create_order_zero_quantity_returns_422(self, client):
        """Creating an order with zero quantity returns 422."""
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        response = client.post("/orders/", json={"product_id": 1, "quantity": 0})
        assert response.status_code == 422

    def test_create_order_atomically_decrements_stock(self, client):
        """Creating an order atomically decrements product stock."""
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 10},
        )
        # Create order for 5 items
        client.post("/orders/", json={"product_id": 1, "quantity": 5})

        # Check product stock is now 5
        response = client.get("/products/1")
        assert response.json()["stock"] == 5


class TestOrderRead:
    """Tests for GET /orders/{id}"""

    def test_get_order_success(self, client):
        """GET /orders/{id} returns order details with product info."""
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        client.post("/orders/", json={"product_id": 1, "quantity": 5})

        response = client.get("/orders/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["product_id"] == 1
        assert data["quantity"] == 5
        assert data["status"] == "PENDING"
        assert data["product"]["id"] == 1
        assert data["product"]["name"] == "Widget"

    def test_get_order_not_found(self, client):
        """GET /orders/{id} returns 404 if order not found."""
        response = client.get("/orders/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Order not found"


class TestOrderStatusTransitions:
    """Tests for PUT /orders/{id} status updates"""

    def setup_order(self, client):
        """Helper to create product and order."""
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        client.post("/orders/", json={"product_id": 1, "quantity": 5})

    def test_pending_to_paid_transition(self, client):
        """PENDING -> PAID transition is allowed."""
        self.setup_order(client)
        response = client.put("/orders/1", json="PAID")
        assert response.status_code == 200
        assert response.json()["status"] == "PAID"

    def test_pending_to_canceled_transition(self, client):
        """PENDING -> CANCELED transition is allowed and restores stock."""
        self.setup_order(client)
        # Check initial stock
        resp = client.get("/products/1")
        initial_stock = resp.json()["stock"]

        # Cancel the order
        response = client.put("/orders/1", json="CANCELED")
        assert response.status_code == 200
        assert response.json()["status"] == "CANCELED"

        # Check stock is restored
        resp = client.get("/products/1")
        assert resp.json()["stock"] == initial_stock + 5

    def test_paid_to_shipped_transition(self, client):
        """PAID -> SHIPPED transition is allowed."""
        self.setup_order(client)
        client.put("/orders/1", json="PAID")
        response = client.put("/orders/1", json="SHIPPED")
        assert response.status_code == 200
        assert response.json()["status"] == "SHIPPED"

    def test_paid_to_canceled_transition(self, client):
        """PAID -> CANCELED transition is allowed and restores stock."""
        self.setup_order(client)
        client.put("/orders/1", json="PAID")

        # Check stock (should be 95 after order creation)
        resp = client.get("/products/1")
        stock_before = resp.json()["stock"]

        # Cancel the PAID order
        response = client.put("/orders/1", json="CANCELED")
        assert response.status_code == 200
        assert response.json()["status"] == "CANCELED"

        # Check stock is restored
        resp = client.get("/products/1")
        assert resp.json()["stock"] == stock_before + 5

    def test_shipped_no_transitions_allowed(self, client):
        """SHIPPED order cannot transition to any other status."""
        self.setup_order(client)
        client.put("/orders/1", json="PAID")
        client.put("/orders/1", json="SHIPPED")

        # Try invalid transition from SHIPPED
        response = client.put("/orders/1", json="CANCELED")
        assert response.status_code == 400
        assert "Invalid transition" in response.json()["detail"]

    def test_canceled_no_transitions_allowed(self, client):
        """CANCELED order cannot transition to any other status."""
        self.setup_order(client)
        client.put("/orders/1", json="CANCELED")

        # Try invalid transition from CANCELED
        response = client.put("/orders/1", json="PAID")
        assert response.status_code == 400
        assert "Invalid transition" in response.json()["detail"]

    def test_invalid_status_value_returns_400(self, client):
        """PUT /orders/{id} with invalid status returns 400."""
        self.setup_order(client)
        response = client.put("/orders/1", json="INVALID_STATUS")
        assert response.status_code == 400

    def test_order_not_found_returns_404(self, client):
        """PUT /orders/{id} returns 404 if order not found."""
        response = client.put("/orders/999", json="PAID")
        assert response.status_code == 404


class TestOrderDelete:
    """Tests for DELETE /orders/{id}"""

    def setup_order(self, client):
        """Helper to create product and order."""
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        client.post("/orders/", json={"product_id": 1, "quantity": 5})

    def test_delete_pending_order_success(self, client):
        """DELETE /orders/{id} deletes PENDING order and restores stock."""
        self.setup_order(client)
        resp = client.get("/products/1")
        stock_before = resp.json()["stock"]

        response = client.delete("/orders/1")
        assert response.status_code == 204

        # Verify stock restored
        resp = client.get("/products/1")
        assert resp.json()["stock"] == stock_before + 5

    def test_delete_paid_order_converts_to_canceled(self, client):
        """DELETE /orders/{id} on PAID order converts it to CANCELED."""
        self.setup_order(client)
        client.put("/orders/1", json="PAID")
        resp = client.get("/products/1")
        stock_before = resp.json()["stock"]

        response = client.delete("/orders/1")
        assert response.status_code == 204

        # Verify order is now CANCELED
        resp = client.get("/orders/1")
        assert resp.json()["status"] == "CANCELED"

        # Verify stock restored
        resp = client.get("/products/1")
        assert resp.json()["stock"] == stock_before + 5

    def test_delete_shipped_order_returns_400(self, client):
        """DELETE /orders/{id} on SHIPPED order returns 400."""
        self.setup_order(client)
        client.put("/orders/1", json="PAID")
        client.put("/orders/1", json="SHIPPED")

        response = client.delete("/orders/1")
        assert response.status_code == 400
        assert "cannot be deleted or canceled" in response.json()["detail"]

    def test_delete_order_not_found(self, client):
        """DELETE /orders/{id} returns 404 if order not found."""
        response = client.delete("/orders/999")
        assert response.status_code == 404
