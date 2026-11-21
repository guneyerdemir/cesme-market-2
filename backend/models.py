from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    full_name = Column(String(120), nullable=False)
    role = Column(String(32), nullable=False, default="STAFF")  # ADMIN or STAFF
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    slug = Column(String(120), unique=True, index=True, nullable=False)
    icon = Column(String(32), nullable=False, default="🛒")
    # Retained for compatibility with existing local databases; hidden from the app/API.
    default_aisle_code = Column(String(64), nullable=False, default="general")
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, nullable=False)

    products = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    barcode = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(180), nullable=False, index=True)
    slug = Column(String(200), index=True, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    price = Column(Float, nullable=False)
    unit = Column(String(32), nullable=False, default="Adet")  # Adet, Kg, Litre, Paket
    stock_quantity = Column(Integer, nullable=False, default=0)
    is_stock_verified = Column(Boolean, default=False, nullable=False)
    is_sample_data = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)
    campaign_badge = Column(String(64), nullable=True)

    # Legacy database columns retained for compatibility; no storefront/admin feature uses them.
    aisle_code = Column(String(64), index=True, nullable=False, default="general")
    shelf_unit = Column(Integer, nullable=False, default=1)
    shelf_row = Column(Integer, nullable=False, default=2)
    shelf_slot = Column(Integer, nullable=False, default=1)
    model_type = Column(String(32), nullable=False, default="box")

    primary_color = Column(String(32), nullable=False, default="#F5C518")
    secondary_color = Column(String(32), nullable=False, default="#1E293B")

    last_synced_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    category = relationship("Category", back_populates="products")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(40), unique=True, index=True, nullable=False)
    idempotency_key = Column(String(120), unique=True, index=True, nullable=True)
    customer_name = Column(String(140), nullable=False)
    customer_phone = Column(String(40), nullable=False, index=True)
    customer_email = Column(String(140), nullable=True)
    order_note = Column(Text, nullable=True)
    delivery_type = Column(String(40), nullable=False, default="MAGAZADAN_TESLIM")
    payment_method = Column(String(40), nullable=False, default="MAGAZADA_ODEME")
    status = Column(String(40), nullable=False, default="YENI_SIPARIS", index=True)
    subtotal_amount = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    status_logs = relationship("OrderStatusLog", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    barcode_snapshot = Column(String(64), nullable=False)
    product_name_snapshot = Column(String(180), nullable=False)
    unit_price_snapshot = Column(Float, nullable=False)
    unit_snapshot = Column(String(32), nullable=False)
    quantity = Column(Integer, nullable=False)
    line_total = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")


class OrderStatusLog(Base):
    __tablename__ = "order_status_logs"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    previous_status = Column(String(40), nullable=True)
    new_status = Column(String(40), nullable=False)
    changed_by_username = Column(String(64), nullable=False, default="sistem")
    note = Column(String(300), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    order = relationship("Order", back_populates="status_logs")


class CustomerLiveLocation(Base):
    __tablename__ = "customer_live_locations"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    token_hash = Column(String(64), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    accuracy_meters = Column(Float, nullable=True)
    consent_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    order = relationship("Order")


class StoreMedia(Base):
    __tablename__ = "store_media"

    id = Column(Integer, primary_key=True, index=True)
    placement = Column(String(24), nullable=False, index=True)  # gallery or sponsor
    title = Column(String(180), nullable=False, default="")
    image_url = Column(String(500), nullable=False)
    link_url = Column(String(1000), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class SystemMetadata(Base):
    __tablename__ = "system_metadata"

    key = Column(String(80), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
