from fastapi import FastAPI, HTTPException, Depends, Response, status, Body, APIRouter
from fastapi import Request
from sqlalchemy.orm import Session
from . import models, schemas, crud, database
from sqlalchemy.exc import IntegrityError, OperationalError
import os
import hmac
import hashlib
import time
import random

app = FastAPI(title="Orders Inventory Microservice")

# Create tables on startup (for this minimal scaffold)
models.Base.metadata.create_all(bind=database.engine)

# Test routes
router = APIRouter(prefix="/test", tags=["test"])

@router.post("/reset-db", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
def reset_database(db: Session = Depends(database.get_db)):
    """
    Clear all data from database tables. For testing purposes only.
    """
    try:
        # Delete all data from tables (order matters due to foreign key constraints)
        db.query(models.WebhookEvent).delete()
        db.query(models.Order).delete()
        db.query(models.Product).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to reset database: {str(e)}")

# Include test routes
app.include_router(router)


@app.post(
    "/products/",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Product,
    responses={
        201: {
            "description": "Product created",
            "content": {"application/json": {"example": schemas.Product.Config.schema_extra["example"]}},
        },
        409: {"description": "Conflict - SKU exists", "content": {"application/json": {"example": {"detail": "sku already exists"}}}},
        400: {"description": "Bad Request", "content": {"application/json": {"example": {"detail": "stock must be >= 0"}}}},
    },
)
def create_product(product: schemas.ProductCreate, response: Response, db: Session = Depends(database.get_db)):
    """Create a new product.

    - Returns 201 and a Location header on success.
    - Returns 409 if the `sku` already exists.
    - Returns 400 for validation errors (e.g. negative stock).
    """
    # validate stock locally (not caught by pydantic)
    if product.stock < 0:
        raise HTTPException(status_code=400, detail="stock must be >= 0")
    try:
        db_product = crud.create_product(db, product)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="sku already exists")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    response.headers["Location"] = f"/products/{db_product.id}"
    return db_product


@app.get(
    "/products/",
    response_model=schemas.ProductList,
    responses={
        200: {
            "description": "Paged list of products",
            "content": {"application/json": {"example": schemas.ProductList.Config.schema_extra["example"]}},
        },
        400: {"description": "Bad Request", "content": {"application/json": {"example": {"detail": "page and size must be >= 1"}}}},
    },
)
def read_products(page: int = 1, size: int = 10, db: Session = Depends(database.get_db)):
    if page < 1 or size < 1:
        raise HTTPException(status_code=400, detail="page and size must be >= 1")
    skip = (page - 1) * size
    items = crud.get_products(db, skip=skip, limit=size)
    total = crud.count_products(db)
    return {"items": items, "page": page, "size": size, "total": total}


@app.get(
    "/products/{product_id}",
    response_model=schemas.Product,
    responses={
        404: {"description": "Not Found", "content": {"application/json": {"example": {"detail": "Product not found"}}}}
    },
)
def read_product(product_id: int, db: Session = Depends(database.get_db)):
    """Retrieve a product by id. Returns 404 if not found."""
    db_product = crud.get_product(db, product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product


@app.put(
    "/products/{product_id}",
    response_model=schemas.Product,
    responses={
        200: {"description": "Updated product", "content": {"application/json": {"example": schemas.Product.Config.schema_extra["example"]}}},
        400: {"description": "Bad Request", "content": {"application/json": {"example": {"detail": "invalid value"}}}},
        404: {"description": "Not Found", "content": {"application/json": {"example": {"detail": "Product not found"}}}},
        409: {"description": "Conflict - SKU exists", "content": {"application/json": {"example": {"detail": "sku already exists"}}}},
    },
)
def update_product(product_id: int, partial: bool = False, db: Session = Depends(database.get_db), product_data: dict = Body(...)):
    """Update a product. Pass `?partial=true` to perform a partial update (only provided fields are changed); otherwise a full update is expected."""
    try:
        if partial:
            product_obj = schemas.ProductUpdate(**product_data)
            db_product = crud.update_product_partial(db, product_id, product_obj)
        else:
            product_obj = schemas.ProductCreate(**product_data)
            db_product = crud.update_product(db, product_id, product_obj)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="sku already exists")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product


@app.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Not Found", "content": {"application/json": {"example": {"detail": "Product not found"}}}}},
)
def delete_product(product_id: int, db: Session = Depends(database.get_db)):
    """Delete a product. Returns 204 No Content on success or 404 if not found."""
    db_product = crud.delete_product(db, product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(
    "/orders/",
    response_model=schemas.Order,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Order created", "content": {"application/json": {"example": schemas.Order.Config.schema_extra["example"]}}},
        404: {"description": "Product not found", "content": {"application/json": {"example": {"detail": "Product not found"}}}},
        409: {"description": "Insufficient stock", "content": {"application/json": {"example": {"detail": "Insufficient stock"}}}},
    },
)
def create_order(order: schemas.OrderCreate, response: Response, db: Session = Depends(database.get_db)):
    """Create an order atomically (stock is decremented atomically). Returns 201 on success with Location header.

    Uses retry logic with exponential backoff for transient database lock conflicts.
    Errors are returned in deterministic shape, for example: {"detail": "Insufficient stock"}.
    """
    max_retries = 3
    base_delay = 0.01  # 10ms base delay
    
    for attempt in range(max_retries):
        try:
            db_order = crud.create_order(db, order)
            response.headers["Location"] = f"/orders/{db_order.id}"
            return db_order
        except crud.ProductNotFoundError:
            raise HTTPException(status_code=404, detail="Product not found")
        except crud.InsufficientStockError:
            # Don't retry on insufficient stock - it's a business logic error, not a transient issue
            raise HTTPException(status_code=409, detail="Insufficient stock")
        except (OperationalError, IntegrityError) as e:
            # Retry on database lock/timeout errors with exponential backoff
            if attempt < max_retries - 1:
                # Exponential backoff with jitter to prevent thundering herd
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.01)
                time.sleep(delay)
                # Refresh the session to clear any stale state
                db.rollback()
                continue
            else:
                # Last attempt failed, raise the error
                raise HTTPException(status_code=503, detail="Service temporarily unavailable, please try again")
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))
    
    # Should never reach here, but just in case
    raise HTTPException(status_code=500, detail="Internal server error")


@app.get(
    "/orders/{order_id}",
    response_model=schemas.OrderDetail,
    responses={404: {"description": "Not Found", "content": {"application/json": {"example": {"detail": "Order not found"}}}}},
)
def read_order(order_id: int, db: Session = Depends(database.get_db)):
    """Retrieve order details for basic tracking. Returns nested product info where available."""
    db_order = crud.get_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    product = crud.get_product(db, db_order.product_id)
    detail = schemas.OrderDetail.from_orm(db_order)
    detail.product = schemas.Product.from_orm(product) if product else None
    return detail


@app.put(
    "/orders/{order_id}",
    response_model=schemas.Order,
    responses={
        200: {"description": "Order updated", "content": {"application/json": {"example": schemas.Order.Config.schema_extra["example"]}}},
        400: {"description": "Invalid state transition", "content": {"application/json": {"example": {"detail": "Invalid transition from PENDING to SHIPPED"}}}},
        404: {"description": "Not Found", "content": {"application/json": {"example": {"detail": "Order not found"}}}},
    },
)
def update_order(order_id: int, status: str = Body(...), db: Session = Depends(database.get_db)):
    """Update the order's status. Only status changes are accepted here.

    Allowed transitions:
    - PENDING -> PAID | CANCELED
    - PAID -> SHIPPED | CANCELED
    - SHIPPED -> (no transitions)
    - CANCELED -> (no transitions)
    """
    try:
        new_status = models.OrderStatus(status)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid status")
    try:
        db_order = crud.update_order_status(db, order_id, new_status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order


@app.delete(
    "/orders/{order_id}",
    responses={
        204: {"description": "Order deleted or canceled"},
        400: {"description": "Cannot delete/cancel shipped order", "content": {"application/json": {"example": {"detail": "Order cannot be deleted or canceled (already shipped)"}}}},
        404: {"description": "Not Found", "content": {"application/json": {"example": {"detail": "Order not found"}}}},
    },
)
def delete_order(order_id: int, db: Session = Depends(database.get_db)):
    """Delete or cancel an order.

    - Fully deletes PENDING orders (stock is restored).
    - Converts PAID orders to CANCELED (stock restored).
    - Shipped orders cannot be deleted or canceled.
    """
    res = crud.delete_order(db, order_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if res is False:
        raise HTTPException(status_code=400, detail="Order cannot be deleted or canceled (already shipped)")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(
    "/webhooks/payment",
    responses={
        200: {"description": "Webhook accepted", "content": {"application/json": {"example": {"detail": "ok"}}}},
        400: {"description": "Bad Request", "content": {"application/json": {"example": {"detail": "invalid payload"}}}},
        401: {"description": "Invalid signature", "content": {"application/json": {"example": {"detail": "invalid signature"}}}},
    },
)
async def payment_webhook(request: Request, db: Session = Depends(database.get_db)):
    """Webhook receiver for payment provider.

    Security:
    - Expects header `X-Signature` containing HMAC-SHA256 hex digest of the raw request body computed with WEBHOOK_SECRET.

    Payload (example):
    {
      "event_id": "evt_123",
      "type": "payment.succeeded",
      "order_id": 1,
      "amount": 9.99
    }
    """

    # Header name choice: X-Signature
    sig_header = request.headers.get("X-Signature")
    if not sig_header:
        raise HTTPException(status_code=401, detail="missing signature")

    body = await request.body()  # raw bytes

    secret = os.getenv("WEBHOOK_SECRET")
    if not secret:
        # Fail closed if secret isn't configured
        raise HTTPException(status_code=500, detail="webhook secret not configured")

    # Compute HMAC-SHA256 on the raw body and compare using compare_digest
    computed = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, sig_header):
        # Do not log secret or computed HMAC
        raise HTTPException(status_code=401, detail="invalid signature")

    # Parse JSON payload now that signature verified
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid payload")

    event_type = payload.get("type")
    event_id = payload.get("event_id")

    if event_type == "payment.succeeded":
        order_id = payload.get("order_id")
        if not event_id or not order_id:
            raise HTTPException(status_code=400, detail="missing event_id or order_id")
        try:
            processed = crud.process_payment_webhook(db, event_id, int(order_id))
        except crud.ProductNotFoundError:
            raise HTTPException(status_code=404, detail="Order or product not found")
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not processed:
            # replayed event
            return {"detail": "event already processed"}
        return {"detail": "ok"}

    # unknown event types: accept but ignore
    return {"detail": "ignored"}
