from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    CheckConstraint,
    UniqueConstraint,
    ForeignKey,
    Enum as SAEnum,
    DateTime,
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum

Base = declarative_base()


class OrderStatus(enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    CANCELED = "CANCELED"


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("sku", name="uq_product_sku"),
        CheckConstraint("price > 0", name="ck_product_price_positive"),
        CheckConstraint("stock >= 0", name="ck_product_stock_non_negative"),
    )


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(SAEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    product = relationship("Product")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_quantity_positive"),
    )


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, nullable=False, unique=True, index=True)
    received_at = Column(DateTime, default=datetime.now, nullable=False)
