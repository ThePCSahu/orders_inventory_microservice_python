"""Integration tests for Webhook API endpoint."""
import json
import hmac
import hashlib
import pytest


class TestWebhookSecurity:
    """Tests for HMAC-SHA256 signature verification"""

    def compute_signature(self, payload_bytes, secret):
        """Helper to compute HMAC-SHA256 signature."""
        return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    def test_webhook_valid_signature_accepted(self, client, monkeypatch):
        """Webhook with valid signature is accepted."""
        # Setup: create product and order
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        client.post("/orders/", json={"product_id": 1, "quantity": 1})

        secret = "test-secret-123"
        monkeypatch.setenv("WEBHOOK_SECRET", secret)

        payload = {
            "event_id": "evt_123",
            "type": "payment.succeeded",
            "order_id": 1,
            "amount": 9.99,
        }
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = self.compute_signature(payload_bytes, secret)

        response = client.post(
            "/webhooks/payment",
            content=payload_bytes,
            headers={"X-Signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json()["detail"] == "ok"

    def test_webhook_missing_signature_returns_401(self, client):
        """Webhook without signature header returns 401."""
        payload = {
            "event_id": "evt_123",
            "type": "payment.succeeded",
            "order_id": 1,
        }
        payload_bytes = json.dumps(payload).encode("utf-8")

        response = client.post(
            "/webhooks/payment",
            content=payload_bytes,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 401
        assert "signature" in response.json()["detail"].lower()

    def test_webhook_invalid_signature_returns_401(self, client):
        """Webhook with invalid signature returns 401."""
        payload = {
            "event_id": "evt_123",
            "type": "payment.succeeded",
            "order_id": 1,
        }
        payload_bytes = json.dumps(payload).encode("utf-8")

        response = client.post(
            "/webhooks/payment",
            content=payload_bytes,
            headers={
                "X-Signature": "invalid-signature-abc123",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "invalid signature"

    def test_webhook_tampered_body_fails_signature(self, client, monkeypatch):
        """Webhook with tampered body fails signature verification."""
        secret = "test-secret-123"
        monkeypatch.setenv("WEBHOOK_SECRET", secret)

        original_payload = {
            "event_id": "evt_123",
            "type": "payment.succeeded",
            "order_id": 1,
            "amount": 9.99,
        }
        original_bytes = json.dumps(original_payload, separators=(",", ":")).encode("utf-8")
        signature = self.compute_signature(original_bytes, secret)

        # Tamper with body but keep the signature
        tampered_payload = {
            "event_id": "evt_123",
            "type": "payment.succeeded",
            "order_id": 2,  # Changed
            "amount": 100.0,  # Changed
        }
        tampered_bytes = json.dumps(tampered_payload).encode("utf-8")

        response = client.post(
            "/webhooks/payment",
            content=tampered_bytes,
            headers={"X-Signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 401


class TestWebhookPaymentProcessing:
    """Tests for payment.succeeded event handling"""

    def compute_signature(self, payload_bytes, secret):
        """Helper to compute HMAC-SHA256 signature."""
        return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    def webhook_call(self, client, event_id, order_id, secret):
        """Helper to make a valid webhook call."""
        payload = {
            "event_id": event_id,
            "type": "payment.succeeded",
            "order_id": order_id,
            "amount": 9.99,
        }
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = self.compute_signature(payload_bytes, secret)

        return client.post(
            "/webhooks/payment",
            content=payload_bytes,
            headers={"X-Signature": signature, "Content-Type": "application/json"},
        )

    def test_payment_succeeded_marks_order_paid(self, client, monkeypatch):
        """payment.succeeded event marks order as PAID."""
        # Setup
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        client.post("/orders/", json={"product_id": 1, "quantity": 1})

        secret = "test-secret-123"
        monkeypatch.setenv("WEBHOOK_SECRET", secret)

        # Send webhook
        response = self.webhook_call(client, "evt_123", 1, secret)
        assert response.status_code == 200

        # Verify order is PAID
        order_response = client.get("/orders/1")
        assert order_response.json()["status"] == "PAID"

    def test_payment_succeeded_order_not_found(self, client, monkeypatch):
        """payment.succeeded for non-existent order returns 404."""
        secret = "test-secret-123"
        monkeypatch.setenv("WEBHOOK_SECRET", secret)

        response = self.webhook_call(client, "evt_123", 999, secret)
        assert response.status_code == 404

    def test_webhook_missing_event_id_returns_400(self, client, monkeypatch):
        """Webhook without event_id returns 400."""
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        client.post("/orders/", json={"product_id": 1, "quantity": 1})

        secret = "test-secret-123"
        monkeypatch.setenv("WEBHOOK_SECRET", secret)

        payload = {
            "type": "payment.succeeded",
            "order_id": 1,
            "amount": 9.99,
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        signature = self.compute_signature(payload_bytes, secret)

        response = client.post(
            "/webhooks/payment",
            content=payload_bytes,
            headers={"X-Signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 400
        assert "missing event_id" in response.json()["detail"]

    def test_webhook_malformed_json_returns_400(self, client, monkeypatch):
        """Webhook with invalid JSON returns 400."""
        secret = "test-secret-123"
        monkeypatch.setenv("WEBHOOK_SECRET", secret)

        payload_bytes = b"not valid json"
        signature = self.compute_signature(payload_bytes, secret)

        response = client.post(
            "/webhooks/payment",
            content=payload_bytes,
            headers={"X-Signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 400
        assert "invalid payload" in response.json()["detail"]


class TestWebhookReplayProtection:
    """Tests for replay attack prevention"""

    def compute_signature(self, payload_bytes, secret):
        """Helper to compute HMAC-SHA256 signature."""
        return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    def webhook_call(self, client, event_id, order_id, secret):
        """Helper to make a valid webhook call."""
        payload = {
            "event_id": event_id,
            "type": "payment.succeeded",
            "order_id": order_id,
            "amount": 9.99,
        }
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = self.compute_signature(payload_bytes, secret)

        return client.post(
            "/webhooks/payment",
            content=payload_bytes,
            headers={"X-Signature": signature, "Content-Type": "application/json"},
        )

    def test_webhook_idempotent_replay_same_event_id(self, client, monkeypatch):
        """Calling webhook twice with same event_id is idempotent."""
        # Setup
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        client.post("/orders/", json={"product_id": 1, "quantity": 1})

        secret = "test-secret-123"
        monkeypatch.setenv("WEBHOOK_SECRET", secret)

        # First call
        response1 = self.webhook_call(client, "evt_123", 1, secret)
        assert response1.status_code == 200
        assert response1.json()["detail"] == "ok"

        # Order should be PAID now
        order_response = client.get("/orders/1")
        assert order_response.json()["status"] == "PAID"

        # Second call with same event_id
        response2 = self.webhook_call(client, "evt_123", 1, secret)
        assert response2.status_code == 200
        assert response2.json()["detail"] == "event already processed"

        # Order status should not change (still PAID, not transitioned again)
        order_response = client.get("/orders/1")
        assert order_response.json()["status"] == "PAID"

    def test_webhook_different_event_ids_process_separately(self, client, monkeypatch):
        """Two different event_ids are processed separately."""
        # Setup: create two orders
        client.post(
            "/products/",
            json={"sku": "SKU-001", "name": "Widget", "price": 9.99, "stock": 100},
        )
        client.post("/orders/", json={"product_id": 1, "quantity": 1})  # order 1
        client.post("/orders/", json={"product_id": 1, "quantity": 1})  # order 2

        secret = "test-secret-123"
        monkeypatch.setenv("WEBHOOK_SECRET", secret)

        # Process first event
        response1 = self.webhook_call(client, "evt_123", 1, secret)
        assert response1.status_code == 200

        # Process second event with different event_id
        response2 = self.webhook_call(client, "evt_124", 2, secret)
        assert response2.status_code == 200

        # Both orders should be PAID
        resp1 = client.get("/orders/1")
        assert resp1.json()["status"] == "PAID"
        resp2 = client.get("/orders/2")
        assert resp2.json()["status"] == "PAID"
