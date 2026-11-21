import os
import secrets
import hashlib
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
import jwt

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.config import (
    ALGORITHM,
    APP_NAME,
    BASE_DIR,
    SECRET_KEY,
    STORE_ADDRESS,
    STORE_MAPS_URL,
    STORE_PHONE,
    STORE_WHATSAPP,
    UPLOAD_DIR,
)
from backend.database import Base, SessionLocal, engine, get_db
from backend.models import (
    Category,
    CustomerLiveLocation,
    Order,
    OrderItem,
    OrderStatusLog,
    Product,
    StoreMedia,
    SystemMetadata,
    User,
)
from backend.notifications import notification_service
from backend.pos_integration import POSIntegrationService, slugify_tr
from backend.schemas import (
    ORDER_STATUS_LABELS,
    ORDER_STATUS_LIST,
    AdminPasswordChangeRequest,
    CartValidationRequest,
    CategorySchema,
    LoginRequest,
    OrderCreateRequest,
    OrderCreatedResponseSchema,
    OrderResponseSchema,
    OrderStatusUpdateRequest,
    CustomerLocationStopRequest,
    CustomerLocationUpdateRequest,
    ProductCreateUpdateSchema,
    ProductSchema,
    StoreContactUpdateRequest,
    StoreMediaCreateUpdateSchema,
    StoreMediaSchema,
    TokenResponse,
)
from backend.security import (
    create_access_token,
    get_current_user,
    hash_password,
    login_rate_limiter,
    order_rate_limiter,
    require_admin,
    require_staff_or_admin,
    verify_password,
)
from backend.seed import seed_initial_data

app = FastAPI(
    title=APP_NAME,
    description="Çeşme Market 2 – Online Sipariş ve Mağaza Yönetim API",
    version="1.0.0",
)

_location_cleanup_task: Optional[asyncio.Task] = None


async def _expire_stale_customer_locations() -> None:
    while True:
        await asyncio.sleep(300)
        db = SessionLocal()
        try:
            stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
            locations = db.query(CustomerLiveLocation).filter(CustomerLiveLocation.is_active.is_(True)).all()
            changed = False
            for location in locations:
                updated_at = location.updated_at
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                if (
                    not location.order
                    or location.order.status in {"HAZIR", "TESLIM_EDILDI", "IPTAL_EDILDI"}
                    or updated_at < stale_cutoff
                ):
                    location.is_active = False
                    location.latitude = None
                    location.longitude = None
                    location.accuracy_meters = None
                    changed = True
            if changed:
                db.commit()
        finally:
            db.close()


@app.on_event("startup")
async def start_customer_location_cleanup() -> None:
    global _location_cleanup_task
    _location_cleanup_task = asyncio.create_task(_expire_stale_customer_locations())


@app.on_event("shutdown")
async def stop_customer_location_cleanup() -> None:
    global _location_cleanup_task
    if _location_cleanup_task:
        _location_cleanup_task.cancel()
        try:
            await _location_cleanup_task
        except asyncio.CancelledError:
            pass
        _location_cleanup_task = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()


app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


def _serialize_product(p: Product) -> ProductSchema:
    schema = ProductSchema.model_validate(p)
    schema.category_name = p.category.name if p.category else ""
    return schema


def _serialize_store_media(item: StoreMedia) -> StoreMediaSchema:
    return StoreMediaSchema.model_validate(item)


def _serialize_order(o: Order) -> OrderResponseSchema:
    schema = OrderResponseSchema.model_validate(o)
    schema.status_label = ORDER_STATUS_LABELS.get(o.status, o.status)
    return schema


# ---------------------------------------------------------------------------
# PUBLIC STOREFRONT ENDPOINTS
# ---------------------------------------------------------------------------


@app.get("/api/v1/health")
def health_check():
    return {
        "status": "ok",
        "service": APP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _get_store_contact(db: Session) -> dict:
    meta_rows = (
        db.query(SystemMetadata)
        .filter(
            SystemMetadata.key.in_(
                ["store_address", "store_phone", "store_whatsapp", "store_maps_url"]
            )
        )
        .all()
    )
    meta_map = {r.key: r.value for r in meta_rows if r.value and r.value.strip()}
    return {
        "address": meta_map.get("store_address") or STORE_ADDRESS,
        "phone": meta_map.get("store_phone") or STORE_PHONE,
        "whatsapp": meta_map.get("store_whatsapp") or STORE_WHATSAPP,
        "maps_url": meta_map.get("store_maps_url") or STORE_MAPS_URL,
    }


@app.get("/api/v1/store/layout")
def get_store_layout(db: Session = Depends(get_db)):
    categories = (
        db.query(Category)
        .filter(Category.is_active.is_(True))
        .order_by(Category.sort_order.asc())
        .all()
    )
    integration_info = POSIntegrationService.get_integration_status(db)
    return {
        "store_name": "ÇEŞME MARKET 2",
        "delivery_model": "Online Sipariş & Mağazadan Teslim (Ödeme Mağazada)",
        "contact": _get_store_contact(db),
        "categories": [CategorySchema.model_validate(c) for c in categories],
        "integration": integration_info,
    }


@app.get("/api/v1/categories", response_model=List[CategorySchema])
def list_categories(db: Session = Depends(get_db)):
    return (
        db.query(Category)
        .filter(Category.is_active.is_(True))
        .order_by(Category.sort_order.asc())
        .all()
    )


@app.get("/api/v1/products", response_model=List[ProductSchema])
def list_products(
    q: Optional[str] = Query(default=None, description="Ürün adı veya barkod arama"),
    category_id: Optional[int] = Query(default=None),
    featured_only: bool = Query(default=False),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    query = db.query(Product)
    if not include_inactive:
        query = query.filter(Product.is_active.is_(True))
    if category_id is not None:
        query = query.filter(Product.category_id == category_id)
    if featured_only:
        query = query.filter(Product.is_featured.is_(True))
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Product.name.ilike(term),
                Product.barcode.ilike(term),
                Product.description.ilike(term),
            )
        )

    products = query.order_by(Product.name.asc()).all()
    return [_serialize_product(p) for p in products]


@app.get("/api/v1/products/{product_id}", response_model=ProductSchema)
def get_product_detail(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı.")
    return _serialize_product(product)


@app.get("/api/v1/store/media", response_model=List[StoreMediaSchema])
def list_store_media(db: Session = Depends(get_db)):
    return [
        _serialize_store_media(item)
        for item in db.query(StoreMedia)
        .filter(StoreMedia.is_active.is_(True))
        .order_by(StoreMedia.placement.asc(), StoreMedia.sort_order.asc(), StoreMedia.id.asc())
        .all()
    ]


# ---------------------------------------------------------------------------
# SHOPPING CART VALIDATION & ORDER CREATION (SERVER-SIDE PRICE VERIFICATION)
# ---------------------------------------------------------------------------


@app.post("/api/v1/cart/validate")
def validate_cart(payload: CartValidationRequest, db: Session = Depends(get_db)):
    validated_items = []
    warnings = []
    subtotal = 0.0

    for item in payload.items:
        product = (
            db.query(Product)
            .filter(Product.id == item.product_id, Product.is_active.is_(True))
            .first()
        )
        if not product:
            warnings.append(f"Ürün ID #{item.product_id} artık aktif değil veya bulunamadı.")
            continue

        available_qty = max(0, product.stock_quantity)
        if available_qty == 0:
            warnings.append(f"'{product.name}' şu anda stokta kalmamıştır.")
            continue

        effective_qty = min(item.quantity, available_qty)
        if effective_qty < item.quantity:
            warnings.append(
                f"'{product.name}' için stok sınırı nedeniyle miktar {effective_qty} {product.unit} olarak güncellendi."
            )

        line_total = round(product.price * effective_qty, 2)
        subtotal = round(subtotal + line_total, 2)
        validated_items.append(
            {
                "product_id": product.id,
                "barcode": product.barcode,
                "name": product.name,
                "unit_price": product.price,
                "unit": product.unit,
                "requested_quantity": item.quantity,
                "effective_quantity": effective_qty,
                "line_total": line_total,
                "is_stock_verified": product.is_stock_verified,
            }
        )

    return {
        "items": validated_items,
        "subtotal_amount": subtotal,
        "total_amount": subtotal,
        "warnings": warnings,
        "payment_method_label": "Mağazadan Teslim Alırken Ödeme (Nakit / Kredi Kartı)",
    }


def _create_customer_location_token(order: Order) -> str:
    created_at = order.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    expiry = int(created_at.astimezone(timezone.utc).timestamp()) + 12 * 60 * 60
    return jwt.encode(
        {"sub": order.order_number, "scope": "customer_location", "exp": expiry},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def _build_order_created_response(order: Order) -> OrderCreatedResponseSchema:
    return OrderCreatedResponseSchema(
        **_serialize_order(order).model_dump(),
        location_session_token=_create_customer_location_token(order),
    )


@app.post("/api/v1/orders", response_model=OrderCreatedResponseSchema, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    order_rate_limiter.check(request, "create_order")

    if not payload.kvkk_approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sipariş oluşturabilmek için KVKK aydınlatma metnini onaylamanız gerekmektedir.",
        )

    # 1. Idempotency check (Prevents duplicate order creation on double-click)
    if payload.idempotency_key:
        existing_order = (
            db.query(Order)
            .filter(Order.idempotency_key == payload.idempotency_key)
            .first()
        )
        if existing_order:
            return _build_order_created_response(existing_order)

    # Merge duplicate product IDs in the request
    merged_quantities: dict[int, int] = {}
    for item in payload.items:
        merged_quantities[item.product_id] = merged_quantities.get(item.product_id, 0) + item.quantity

    order_items_to_create: List[OrderItem] = []
    subtotal = 0.0

    for product_id, qty in merged_quantities.items():
        product = (
            db.query(Product)
            .filter(Product.id == product_id, Product.is_active.is_(True))
            .first()
        )
        if not product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sepetinizdeki bir ürün (#{product_id}) bulunamadı veya satışa kapatıldı.",
            )
        if product.stock_quantity < qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{product.name}' ürünü için yeterli stok yok (Mevcut: {product.stock_quantity} {product.unit}).",
            )

        # IMPORTANT: Unit price is always read from the server database, NEVER from client input
        line_total = round(product.price * qty, 2)
        subtotal = round(subtotal + line_total, 2)

        # Deduct stock quantity
        product.stock_quantity -= qty

        order_items_to_create.append(
            OrderItem(
                product_id=product.id,
                barcode_snapshot=product.barcode,
                product_name_snapshot=product.name,
                unit_price_snapshot=product.price,
                unit_snapshot=product.unit,
                quantity=qty,
                line_total=line_total,
            )
        )

    # Generate unique order number: CM2-YYYYMMDD-XXXX
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_suffix = secrets.randbelow(9000) + 1000
    order_number = f"CM2-{date_part}-{random_suffix}"
    while db.query(Order).filter(Order.order_number == order_number).first():
        random_suffix = secrets.randbelow(9000) + 1000
        order_number = f"CM2-{date_part}-{random_suffix}"

    new_order = Order(
        order_number=order_number,
        idempotency_key=payload.idempotency_key,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=payload.customer_email,
        order_note=payload.order_note,
        delivery_type="MAGAZADAN_TESLIM",
        payment_method="MAGAZADA_ODEME",
        status="YENI_SIPARIS",
        subtotal_amount=subtotal,
        total_amount=subtotal,
    )
    db.add(new_order)
    db.flush()

    for oi in order_items_to_create:
        oi.order_id = new_order.id
        db.add(oi)

    db.add(
        OrderStatusLog(
            order_id=new_order.id,
            previous_status=None,
            new_status="YENI_SIPARIS",
            changed_by_username="musteri",
            note="Müşteri tarafından online sipariş oluşturuldu.",
        )
    )
    db.commit()
    db.refresh(new_order)

    notification_service.notify_new_order(
        order_number=new_order.order_number,
        customer_name=new_order.customer_name,
        total_amount=new_order.total_amount,
    )

    return _build_order_created_response(new_order)


def _get_location_order(order_number: str, token: str, db: Session) -> Order:
    try:
        claims = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Konum paylaşım oturumunun süresi dolmuş veya geçersiz.")
    cleaned_number = order_number.strip().upper()
    if claims.get("scope") != "customer_location" or claims.get("sub") != cleaned_number:
        raise HTTPException(status_code=403, detail="Bu sipariş için konum paylaşım yetkisi bulunamadı.")
    order = db.query(Order).filter(Order.order_number == cleaned_number).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı.")
    if order.status in {"HAZIR", "TESLIM_EDILDI", "IPTAL_EDILDI"}:
        raise HTTPException(status_code=409, detail="Sipariş için konum paylaşımı artık kapalı.")
    return order


@app.post("/api/v1/orders/location/share")
def share_customer_location(payload: CustomerLocationUpdateRequest, db: Session = Depends(get_db)):
    if not payload.consent:
        raise HTTPException(status_code=400, detail="Konum paylaşımı için açık onay gereklidir.")
    order = _get_location_order(payload.order_number, payload.location_session_token, db)
    token_hash = hashlib.sha256(payload.location_session_token.encode("utf-8")).hexdigest()
    location = db.query(CustomerLiveLocation).filter(CustomerLiveLocation.order_id == order.id).first()
    now = datetime.now(timezone.utc)
    if location and location.token_hash != token_hash:
        raise HTTPException(status_code=403, detail="Konum paylaşım anahtarı geçersiz.")
    if not location:
        location = CustomerLiveLocation(order_id=order.id, token_hash=token_hash, consent_at=now)
        db.add(location)
    elif not location.is_active:
        location.consent_at = now
    location.latitude = payload.latitude
    location.longitude = payload.longitude
    location.accuracy_meters = payload.accuracy_meters
    location.updated_at = now
    location.is_active = True
    db.commit()
    return {"active": True, "updated_at": now.isoformat()}


@app.post("/api/v1/orders/location/stop")
def stop_customer_location(payload: CustomerLocationStopRequest, db: Session = Depends(get_db)):
    try:
        claims = jwt.decode(payload.location_session_token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Konum paylaşım oturumunun süresi dolmuş veya geçersiz.")
    order_number = payload.order_number.strip().upper()
    if claims.get("scope") != "customer_location" or claims.get("sub") != order_number:
        raise HTTPException(status_code=403, detail="Bu sipariş için konum paylaşım yetkisi bulunamadı.")
    order = db.query(Order).filter(Order.order_number == order_number).first()
    location = db.query(CustomerLiveLocation).filter(CustomerLiveLocation.order_id == order.id).first() if order else None
    if not location or location.token_hash != hashlib.sha256(payload.location_session_token.encode("utf-8")).hexdigest():
        raise HTTPException(status_code=404, detail="Aktif konum paylaşımı bulunamadı.")
    location.is_active = False
    location.latitude = None
    location.longitude = None
    location.accuracy_meters = None
    db.commit()
    return {"active": False}


@app.get("/api/v1/orders/track/{order_number}", response_model=OrderResponseSchema)
def track_order(
    order_number: str,
    phone_last4: Optional[str] = Query(default=None, description="Güvenlik için telefon son 4 hanesi"),
    db: Session = Depends(get_db),
):
    cleaned_no = order_number.strip().upper()
    order = db.query(Order).filter(Order.order_number == cleaned_no).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu sipariş numarasına ait kayıt bulunamadı.",
        )

    if phone_last4 and phone_last4.strip():
        order_digits = "".join(ch for ch in order.customer_phone if ch.isdigit())
        input_digits = "".join(ch for ch in phone_last4 if ch.isdigit())
        if len(input_digits) >= 4 and not order_digits.endswith(input_digits[-4:]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sipariş numarası ile telefon numarasının son 4 hanesi eşleşmedi.",
            )

    return _serialize_order(order)


# ---------------------------------------------------------------------------
# AUTHENTICATION & STORE MANAGEMENT PANEL ENDPOINTS (ADMIN & STAFF)
# ---------------------------------------------------------------------------


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login_for_access_token(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    login_rate_limiter.check(request, "login")

    user = (
        db.query(User)
        .filter(User.username == payload.username.strip(), User.is_active.is_(True))
        .first()
    )
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya şifre hatalı.",
        )

    token = create_access_token(data={"sub": user.username, "role": user.role})
    return TokenResponse(
        access_token=token,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
    )


@app.get("/api/v1/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "role": current_user.role,
    }


@app.get("/api/v1/admin/dashboard")
def get_admin_dashboard(
    current_user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    counts_by_status = {s: 0 for s in ORDER_STATUS_LIST}
    rows = db.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    for st, cnt in rows:
        counts_by_status[st] = cnt

    total_orders = sum(counts_by_status.values())
    active_revenue = (
        db.query(func.coalesce(func.sum(Order.total_amount), 0.0))
        .filter(Order.status != "IPTAL_EDILDI")
        .scalar()
    )
    low_stock_products = (
        db.query(Product)
        .filter(Product.is_active.is_(True), Product.stock_quantity <= 10)
        .count()
    )

    return {
        "total_orders": total_orders,
        "new_orders": counts_by_status["YENI_SIPARIS"] + counts_by_status["ONAY_BEKLIYOR"],
        "approved_orders": counts_by_status["ONAYLANDI"],
        "preparing_orders": counts_by_status["HAZIRLANIYOR"],
        "ready_orders": counts_by_status["HAZIR"],
        "delivered_orders": counts_by_status["TESLIM_EDILDI"],
        "cancelled_orders": counts_by_status["IPTAL_EDILDI"],
        "counts_by_status": counts_by_status,
        "active_revenue": round(float(active_revenue or 0.0), 2),
        "low_stock_products": low_stock_products,
        "recent_notifications": notification_service.get_admin_feed()[:15],
        "integration": POSIntegrationService.get_integration_status(db),
        "contact": _get_store_contact(db),
        "current_user": {
            "username": current_user.username,
            "full_name": current_user.full_name,
            "role": current_user.role,
        },
    }


@app.get("/api/v1/admin/users")
def list_admin_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.id.asc()).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
        }
        for u in users
    ]


@app.post("/api/v1/admin/users/change-password")
def change_user_password(
    payload: AdminPasswordChangeRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_admin_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mevcut yönetici şifrenizi hatalı girdiniz.",
        )

    target_user = (
        db.query(User)
        .filter(User.username == payload.target_username.strip())
        .first()
    )
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Şifresi değiştirilecek kullanıcı bulunamadı.",
        )

    target_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {
        "updated": True,
        "username": target_user.username,
        "role": target_user.role,
        "message": f"'{target_user.username}' hesabının şifresi başarıyla güncellendi.",
    }


@app.put("/api/v1/admin/settings/contact")
def update_store_contact_settings(
    payload: StoreContactUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    updates = {
        "store_address": payload.address.strip(),
        "store_phone": payload.phone.strip(),
        "store_whatsapp": payload.whatsapp.strip(),
        "store_maps_url": payload.maps_url.strip(),
    }
    for key, val in updates.items():
        row = db.query(SystemMetadata).filter(SystemMetadata.key == key).first()
        if row:
            row.value = val
        else:
            db.add(SystemMetadata(key=key, value=val))
    db.commit()
    return _get_store_contact(db)


@app.get("/api/v1/admin/orders", response_model=List[OrderResponseSchema])
def list_admin_orders(
    status_filter: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    current_user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Order)
    if status_filter and status_filter != "ALL":
        query = query.filter(Order.status == status_filter)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Order.order_number.ilike(term),
                Order.customer_name.ilike(term),
                Order.customer_phone.ilike(term),
            )
        )
    orders = query.order_by(Order.created_at.desc()).all()
    return [_serialize_order(o) for o in orders]


@app.patch("/api/v1/admin/orders/{order_id}/status", response_model=OrderResponseSchema)
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdateRequest,
    current_user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı.")

    # Role policy: If an order is already DELIVERED, only ADMIN can revert or cancel it
    if order.status == "TESLIM_EDILDI" and current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teslim edilmiş bir siparişin durumu yalnızca Mağaza Yöneticisi tarafından değiştirilebilir.",
        )

    prev_status = order.status
    if prev_status == payload.status:
        return _serialize_order(order)

    # Restore stock if transitioning to CANCELLED
    if payload.status == "IPTAL_EDILDI" and prev_status != "IPTAL_EDILDI":
        for item in order.items:
            prod = db.query(Product).filter(Product.id == item.product_id).first()
            if prod:
                prod.stock_quantity += item.quantity

    order.status = payload.status
    if payload.status in {"HAZIR", "TESLIM_EDILDI", "IPTAL_EDILDI"}:
        location = db.query(CustomerLiveLocation).filter(CustomerLiveLocation.order_id == order.id).first()
        if location:
            location.is_active = False
            location.latitude = None
            location.longitude = None
            location.accuracy_meters = None
    db.add(
        OrderStatusLog(
            order_id=order.id,
            previous_status=prev_status,
            new_status=payload.status,
            changed_by_username=current_user.username,
            note=payload.note or f"Durum '{ORDER_STATUS_LABELS.get(payload.status)}' olarak güncellendi.",
        )
    )
    db.commit()
    db.refresh(order)

    notification_service.notify_status_change(
        order_number=order.order_number,
        customer_phone=order.customer_phone,
        new_status=order.status,
        note=payload.note,
    )

    return _serialize_order(order)


@app.get("/api/v1/admin/live-locations")
def list_live_customer_locations(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(hours=2)
    locations = db.query(CustomerLiveLocation).filter(CustomerLiveLocation.is_active.is_(True)).all()
    changed = False
    active_locations = []
    for location in locations:
        order = location.order
        if (
            not order
            or order.status in {"HAZIR", "TESLIM_EDILDI", "IPTAL_EDILDI"}
            or location.updated_at.replace(tzinfo=timezone.utc) < stale_cutoff
        ):
            location.is_active = False
            location.latitude = None
            location.longitude = None
            location.accuracy_meters = None
            changed = True
            continue
        active_locations.append(
            {
                "order_number": order.order_number,
                "customer_name": order.customer_name,
                "customer_phone": order.customer_phone,
                "status": order.status,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "accuracy_meters": location.accuracy_meters,
                "updated_at": location.updated_at.isoformat(),
            }
        )
    if changed:
        db.commit()
    return active_locations


# ---------------------------------------------------------------------------
# PRODUCT MANAGEMENT & IMAGE / CSV UPLOAD (RBAC ENFORCED)
# ---------------------------------------------------------------------------


@app.post("/api/v1/admin/products", response_model=ProductSchema, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreateUpdateSchema,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    existing = db.query(Product).filter(Product.barcode == payload.barcode.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{payload.barcode}' barkodlu ürün zaten mevcut.",
        )

    cat = db.query(Category).filter(Category.id == payload.category_id).first()
    if not cat:
        raise HTTPException(status_code=400, detail="Geçersiz kategori seçimi.")

    product = Product(
        barcode=payload.barcode.strip(),
        name=payload.name.strip(),
        slug=f"{slugify_tr(payload.name)}-{payload.barcode.strip()[-4:]}",
        category_id=payload.category_id,
        description=payload.description,
        image_url=payload.image_url,
        price=round(payload.price, 2),
        unit=payload.unit,
        stock_quantity=payload.stock_quantity,
        is_stock_verified=payload.is_stock_verified,
        is_sample_data=payload.is_sample_data,
        is_active=payload.is_active,
        is_featured=payload.is_featured,
        campaign_badge=payload.campaign_badge,
        primary_color=payload.primary_color,
        secondary_color=payload.secondary_color,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return _serialize_product(product)


@app.put("/api/v1/admin/products/{product_id}", response_model=ProductSchema)
def update_product(
    product_id: int,
    payload: ProductCreateUpdateSchema,
    current_user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı.")

    # Staff can update stock & active status; full price/catalog edits require ADMIN
    if current_user.role == "STAFF" and round(payload.price, 2) != round(product.price, 2):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mağaza personeli ürün stok bilgisini güncelleyebilir ancak ürün fiyatını değiştiremez (Yönetici yetkisi gerekir).",
        )

    duplicate = (
        db.query(Product)
        .filter(Product.barcode == payload.barcode.strip(), Product.id != product_id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Bu barkod başka bir üründe kullanılıyor.")

    product.barcode = payload.barcode.strip()
    product.name = payload.name.strip()
    product.slug = f"{slugify_tr(payload.name)}-{payload.barcode.strip()[-4:]}"
    product.category_id = payload.category_id
    product.description = payload.description
    product.image_url = payload.image_url
    product.price = round(payload.price, 2)
    product.unit = payload.unit
    product.stock_quantity = payload.stock_quantity
    product.is_stock_verified = payload.is_stock_verified
    product.is_sample_data = payload.is_sample_data
    product.is_active = payload.is_active
    product.is_featured = payload.is_featured
    product.campaign_badge = payload.campaign_badge
    product.primary_color = payload.primary_color
    product.secondary_color = payload.secondary_color
    product.last_synced_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(product)
    return _serialize_product(product)


@app.patch("/api/v1/admin/products/{product_id}/toggle-active", response_model=ProductSchema)
def toggle_product_active(
    product_id: int,
    current_user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı.")
    product.is_active = not product.is_active
    db.commit()
    db.refresh(product)
    return _serialize_product(product)


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def _validate_uploaded_image_url(image_url: str) -> None:
    filename = Path(image_url).name
    if not image_url.startswith("/uploads/") or filename != image_url.removeprefix("/uploads/"):
        raise HTTPException(status_code=400, detail="Önce yönetici panelinden bir görsel yükleyin.")
    image_path = UPLOAD_DIR / filename
    if not image_path.is_file() or image_path.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Yüklenen görsel bulunamadı veya formatı desteklenmiyor.")


@app.get("/api/v1/admin/store-media", response_model=List[StoreMediaSchema])
def list_admin_store_media(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return [
        _serialize_store_media(item)
        for item in db.query(StoreMedia).order_by(StoreMedia.placement.asc(), StoreMedia.sort_order.asc(), StoreMedia.id.asc()).all()
    ]


@app.post("/api/v1/admin/store-media", response_model=StoreMediaSchema, status_code=status.HTTP_201_CREATED)
def create_store_media(
    payload: StoreMediaCreateUpdateSchema,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _validate_uploaded_image_url(payload.image_url)
    item = StoreMedia(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_store_media(item)


@app.put("/api/v1/admin/store-media/{media_id}", response_model=StoreMediaSchema)
def update_store_media(
    media_id: int,
    payload: StoreMediaCreateUpdateSchema,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = db.query(StoreMedia).filter(StoreMedia.id == media_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Görsel kaydı bulunamadı.")
    _validate_uploaded_image_url(payload.image_url)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return _serialize_store_media(item)


@app.delete("/api/v1/admin/store-media/{media_id}")
def delete_store_media(
    media_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = db.query(StoreMedia).filter(StoreMedia.id == media_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Görsel kaydı bulunamadı.")
    db.delete(item)
    db.commit()
    return {"deleted": True}


@app.post("/api/v1/admin/upload-image")
async def upload_product_image(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Yalnızca .jpg, .jpeg, .png veya .webp formatında görsel yüklenebilir.",
        )

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Görsel boyutu en fazla 5 MB olabilir.")
    if len(content) < 32:
        raise HTTPException(status_code=400, detail="Geçersiz veya boş görsel dosyası.")

    safe_name = f"prod_{int(datetime.now(timezone.utc).timestamp())}_{secrets.token_hex(4)}{ext}"
    dest = UPLOAD_DIR / safe_name
    dest.write_bytes(content)

    return {"image_url": f"/uploads/{safe_name}", "filename": safe_name}


@app.post("/api/v1/admin/import/csv")
async def import_products_csv_endpoint(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext != ".csv":
        raise HTTPException(status_code=400, detail="Lütfen .csv uzantılı bir dosya yükleyin.")

    raw_bytes = await file.read()
    if len(raw_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="CSV dosyası 5 MB sınırını aşıyor.")

    try:
        csv_text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        csv_text = raw_bytes.decode("cp1254", errors="replace")

    try:
        result = POSIntegrationService.import_products_csv(db, csv_text)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/v1/admin/export/products.csv", response_class=PlainTextResponse)
def export_products_csv_endpoint(
    current_user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    csv_data = POSIntegrationService.export_products_csv(db)
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cesme_market_2_urunler.csv"'},
    )


@app.get("/api/v1/admin/export/orders.csv", response_class=PlainTextResponse)
def export_orders_csv_endpoint(
    current_user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    csv_data = POSIntegrationService.export_orders_csv(db)
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cesme_market_2_siparisler.csv"'},
    )


# Serve production build if `dist/` exists
DIST_DIR = BASE_DIR / "dist"
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="frontend")
