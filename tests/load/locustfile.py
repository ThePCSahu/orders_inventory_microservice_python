from locust import HttpUser, task, between
import random
import time

# Read:Write ratio = 80:20 (weights 8 and 2). Reason: most real-world APIs are read-heavy
# (clients read product info far more often than they create orders). This focuses
# load on typical production patterns while still exercising the write paths.

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
        with self.client.get("/products/?page=1&size=1", name="GET /products/first", catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"list failed {r.status_code}")
                return
            data = r.json()
            items = data.get("items") or []

        if items:
            product = items[0]
        else:
            sku = f"locust-{int(time.time()*1000)}-{random.randint(1,1000)}"
            payload = {"sku": sku, "name": "Locust created product", "price": 9.99, "stock": 100}
            resp = self.client.post("/products/", json=payload, name="POST /products/", catch_response=True)
            if resp.status_code not in (201, 409):
                resp.failure(f"create product failed {resp.status_code}")
                return
            # If 409 (duplicate), we still try to get a product again
            if resp.status_code == 201:
                product = resp.json()
            else:
                # retry fetching
                rr = self.client.get("/products/?page=1&size=1", name="GET /products/first_after_create")
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
