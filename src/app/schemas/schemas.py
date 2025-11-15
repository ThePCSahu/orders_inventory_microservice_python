from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from ..models import OrderStatus  # Import from models, not define locally


class ProductBase(BaseModel):
    sku: str
    name: str
    price: float = Field(..., gt=0)
    stock: int = 0


class ProductCreate(ProductBase):
    pass

    class Config:
        schema_extra = {
            "example": {
                "sku": "SKU-001",
                "name": "Example Widget",
                "price": 9.99,
                "stock": 100,
            }
        }


class ProductUpdate(BaseModel):
    sku: Optional[str] = None
    name: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    stock: Optional[int] = Field(None, ge=0)

    class Config:
        schema_extra = {
            "example": {"price": 12.5, "stock": 50}
        }


class Product(ProductBase):
    id: int

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {"id": 1, "sku": "SKU-001", "name": "Example Widget", "price": 9.99, "stock": 100}
        }


class OrderBase(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)


class OrderCreate(OrderBase):
    pass

    class Config:
        schema_extra = {"example": {"product_id": 1, "quantity": 2}}


class Order(OrderBase):
    id: int
    status: OrderStatus
    created_at: datetime

    @validator('status', pre=True)
    def parse_status(cls, v):
        if isinstance(v, str):
            return OrderStatus(v)
        return v

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {"id": 1, "product_id": 1, "quantity": 2, "status": "PENDING", "created_at": "2025-11-13T12:00:00Z"}
        }


class ProductList(BaseModel):
    items: list[Product]
    page: int
    size: int
    total: int

    class Config:
        schema_extra = {
            "example": {
                "items": [
                    {"id": 1, "sku": "SKU-001", "name": "Example Widget", "price": 9.99, "stock": 100}
                ],
                "page": 1,
                "size": 10,
                "total": 1,
            }
        }


class OrderDetail(Order):
    product: Optional[Product]

    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "product_id": 1,
                "quantity": 2,
                "status": "PAID",
                "created_at": "2025-11-13T12:00:00Z",
                "product": {"id": 1, "sku": "SKU-001", "name": "Example Widget", "price": 9.99, "stock": 98},
            }
        }
