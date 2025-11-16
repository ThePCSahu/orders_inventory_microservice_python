from locust import HttpUser, task, between, events
import random
import time
import requests
import logging
from requests.exceptions import RequestException

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_database(host):
    """Helper to reset the database by calling the test endpoint."""
    try:
        response = requests.post(f"{host}/test/reset-db")
        if response.status_code == 204:
            logger.info("Successfully reset database")
        else:
            logger.error(f"Failed to reset database: {response.status_code} - {response.text}")
    except RequestException as e:
        logger.error(f"Error resetting database: {str(e)}")
        raise

# Read:Write ratio = 80:20 (weights 8 and 2). Reason: most real-world APIs are read-heavy
# (clients read product info far more often than they create orders). This focuses
# load on typical production patterns while still exercising the write paths.

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Reset database and pre-populate products before load test starts."""
    host = environment.host or "http://127.0.0.1:8000"
    logger.info("Resetting database before test...")
    reset_database(host)
    
    logger.info("Pre-populating products with high stock for load testing...")
    import requests
    host = environment.host or "http://127.0.0.1:8000"
    # Create multiple products with high stock to prevent quick depletion
    for i in range(10):
        sku = f"load-test-product-{i}"
        payload = {
            "sku": sku,
            "name": f"Load Test Product {i}",
            "price": 9.99 + i,
            "stock": 10000  # High stock to handle concurrent load
        }
        try:
            resp = requests.post(f"{host}/products/", json=payload, timeout=5)
            if resp.status_code in (201, 409):  # 409 means already exists, which is fine
                logger.info(f"Product {sku} ready (stock: 10000)")
        except Exception as e:
            logger.warning(f"Could not create product {sku}: {e}")
    logger.info("Pre-population complete. Starting load test...")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Clean up after load test completes."""
    host = environment.host or "http://127.0.0.1:8000"
    logger.info("Test complete. Resetting database...")
    reset_database(host)
    logger.info("Cleanup complete.")

class WebsiteUser(HttpUser):
    wait_time = between(0.5, 2.0)

    @task(8)
    def get_products(self):
        # Simulate paginated reads
        page = random.randint(1, 3)
        size = random.choice([5, 10, 20])
        with self.client.get(f"/products/?page={page}&size={size}", name="GET /products", catch_response=True) as resp:
            # we don't assert content in load tests, but mark failures if status != 200
            if resp.status_code != 200:
                resp.failure(f"unexpected status {resp.status_code}")

    @task(2)
    def create_order_flow(self):
        # Try to get a product; if none, create one and then place an order
        with self.client.get("/products/?page=1&size=10", name="GET /products/first", catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"list failed {r.status_code}")
                return
            data = r.json()
            items = data.get("items") or []

        if items:
            product = items[random.randint(0, min(len(items) - 1, 9))]  # Randomly select from available products
        else:
            # Fallback: create a product if none exist (shouldn't happen with pre-population)
            sku = f"locust-{int(time.time()*1000)}-{random.randint(1,1000)}"
            payload = {"sku": sku, "name": "Locust created product", "price": 9.99, "stock": 1000}
            resp = self.client.post("/products/", json=payload, name="POST /products/", catch_response=True)
            if resp.status_code not in (201, 409):
                resp.failure(f"create product failed {resp.status_code}")
                return
            # If 409 (duplicate), we still try to get a product again
            if resp.status_code == 201:
                product = resp.json()
            else:
                # retry fetching
                rr = self.client.get("/products/?page=1&size=10", name="GET /products/first_after_create")
                if rr.status_code != 200:
                    return
                items = rr.json().get("items") or []
                if not items:
                    return
                product = items[0]

        order_payload = {"product_id": product["id"], "quantity": 1}
        with self.client.post("/orders/", json=order_payload, name="POST /orders/", catch_response=True) as order_resp:
            if order_resp.status_code not in (201, 409, 400):
                order_resp.failure(f"order creation unexpected status {order_resp.status_code}")
