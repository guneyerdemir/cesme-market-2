from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


ORDER_STATUS_LIST = [
    "YENI_SIPARIS",
    "ONAY_BEKLIYOR",
    "ONAYLANDI",
    "HAZIRLANIYOR",
    "HAZIR",
    "TESLIM_EDILDI",
    "IPTAL_EDILDI",
]

ORDER_STATUS_LABELS = {
    "YENI_SIPARIS": "Yeni Sipariş",
    "ONAY_BEKLIYOR": "Onay Bekliyor",
    "ONAYLANDI": "Onaylandı",
    "HAZIRLANIYOR": "Hazırlanıyor",
    "HAZIR": "Hazır (Mağazadan Teslim Alabilirsiniz)",
    "TESLIM_EDILDI": "Teslim Edildi",
    "IPTAL_EDILDI": "İptal Edildi",
}


class CategorySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    icon: str
    sort_order: int
    is_active: bool


class ProductSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    barcode: str
    name: str
    slug: str
    category_id: int
    category_name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    price: float
    unit: str
    stock_quantity: int
    is_stock_verified: bool
    is_sample_data: bool
    is_active: bool
    is_featured: bool
    campaign_badge: Optional[str] = None
    primary_color: str
    secondary_color: str
    last_synced_at: datetime


class ProductCreateUpdateSchema(BaseModel):
    barcode: str = Field(..., min_length=3, max_length=64)
    name: str = Field(..., min_length=2, max_length=180)
    category_id: int
    description: Optional[str] = Field(default="", max_length=1000)
    image_url: Optional[str] = None
    price: float = Field(..., gt=0, le=500000)
    unit: str = Field(default="Adet", max_length=32)
    stock_quantity: int = Field(default=0, ge=0, le=100000)
    is_stock_verified: bool = False
    is_sample_data: bool = False
    is_active: bool = True
    is_featured: bool = False
    campaign_badge: Optional[str] = None
    primary_color: str = Field(default="#F5C518", max_length=32)
    secondary_color: str = Field(default="#1E293B", max_length=32)


class StoreMediaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    placement: Literal["gallery", "sponsor"]
    title: str
    image_url: str
    link_url: Optional[str] = None
    sort_order: int
    is_active: bool
    updated_at: datetime


class StoreMediaCreateUpdateSchema(BaseModel):
    placement: Literal["gallery", "sponsor"]
    title: str = Field(default="", max_length=180)
    image_url: str = Field(..., min_length=1, max_length=500)
    link_url: Optional[str] = Field(default=None, max_length=1000)
    sort_order: int = Field(default=0, ge=0, le=10000)
    is_active: bool = True


class CartItemInput(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0, le=200)


class CartValidationRequest(BaseModel):
    items: List[CartItemInput]


class OrderCreateRequest(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=140)
    customer_phone: str = Field(..., min_length=10, max_length=30)
    customer_email: Optional[str] = Field(default=None, max_length=140)
    order_note: Optional[str] = Field(default=None, max_length=600)
    idempotency_key: Optional[str] = Field(default=None, max_length=120)
    kvkk_approved: bool = Field(default=True)
    items: List[CartItemInput] = Field(..., min_length=1)

    @field_validator("customer_phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = "".join(ch for ch in v if ch.isdigit())
        if len(digits) < 10 or len(digits) > 15:
            raise ValueError("Geçerli bir telefon numarası giriniz (en az 10 rakam).")
        return v.strip()

    @field_validator("customer_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Müşteri adı en az 2 karakter olmalıdır.")
        return cleaned


class OrderItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    barcode_snapshot: str
    product_name_snapshot: str
    unit_price_snapshot: float
    unit_snapshot: str
    quantity: int
    line_total: float


class OrderStatusLogSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    previous_status: Optional[str] = None
    new_status: str
    changed_by_username: str
    note: Optional[str] = None
    created_at: datetime


class OrderResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_number: str
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    order_note: Optional[str] = None
    delivery_type: str
    payment_method: str
    status: str
    status_label: Optional[str] = None
    subtotal_amount: float
    total_amount: float
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemSchema] = []
    status_logs: List[OrderStatusLogSchema] = []


class OrderCreatedResponseSchema(OrderResponseSchema):
    location_session_token: str


class CustomerLocationUpdateRequest(BaseModel):
    order_number: str = Field(..., min_length=8, max_length=40)
    location_session_token: str = Field(..., min_length=20, max_length=2000)
    consent: bool = False
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_meters: Optional[float] = Field(default=None, ge=0, le=100000)


class CustomerLocationStopRequest(BaseModel):
    order_number: str = Field(..., min_length=8, max_length=40)
    location_session_token: str = Field(..., min_length=20, max_length=2000)


class OrderStatusUpdateRequest(BaseModel):
    status: str
    note: Optional[str] = Field(default=None, max_length=300)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ORDER_STATUS_LIST:
            raise ValueError(f"Geçersiz sipariş durumu: {v}")
        return v


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    full_name: str
    role: str
