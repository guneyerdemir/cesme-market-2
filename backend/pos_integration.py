import csv
import io
import re
from datetime import datetime, timezone
from typing import Dict, List
from sqlalchemy.orm import Session

from backend.models import Category, Order, Product, SystemMetadata


def slugify_tr(text: str) -> str:
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    cleaned = text.translate(tr_map).lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned).strip("-")
    return cleaned or "urun"


class POSIntegrationService:
    """
    Çeşme Market 2 POS / ERP ve Excel/CSV Ürün-Fiyat-Stok Aktarım Katmanı.
    Gerçek POS yazılımı doğrulanana kadar güvenli CSV içe/dışa aktarma ve
    son senkronizasyon zamanı takibi sağlar.
    """

    REQUIRED_CSV_COLUMNS = {"barcode", "name", "price"}

    @staticmethod
    def get_integration_status(db: Session) -> Dict:
        last_sync_meta = (
            db.query(SystemMetadata)
            .filter(SystemMetadata.key == "last_pos_csv_sync_at")
            .first()
        )
        sync_source_meta = (
            db.query(SystemMetadata)
            .filter(SystemMetadata.key == "last_pos_sync_source")
            .first()
        )
        total_products = db.query(Product).count()
        verified_products = (
            db.query(Product).filter(Product.is_stock_verified.is_(True)).count()
        )
        sample_products = (
            db.query(Product).filter(Product.is_sample_data.is_(True)).count()
        )

        return {
            "pos_connected": False,
            "pos_software_name": "Henüz Doğrulanmadı (CSV / Excel Aktarım Modu Aktif)",
            "last_synced_at": last_sync_meta.value if last_sync_meta else None,
            "last_sync_source": sync_source_meta.value if sync_source_meta else "Başlangıç Örnek Katalog Verisi",
            "total_products": total_products,
            "verified_products": verified_products,
            "sample_products": sample_products,
            "supported_methods": [
                "Excel / CSV Toplu Ürün, Barkod, Fiyat ve Stok İçe/Dışa Aktarma (Aktif)",
                "REST API Webhook / POS Adaptörü (Altyapı Hazır)",
            ],
            "stock_disclaimer": (
                "Stok ve fiyat bilgileri son senkronizasyon zamanına göredir. "
                "Kesin stok ve tartılı ürün tutarları mağaza hazırlık aşamasında teyit edilir."
            ),
        }

    @classmethod
    def import_products_csv(cls, db: Session, csv_text: str) -> Dict:
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        if not reader.fieldnames:
            raise ValueError("CSV dosyası boş veya başlık satırı okunamadı.")

        normalized_headers = {h.strip().lower() for h in reader.fieldnames if h}
        missing = cls.REQUIRED_CSV_COLUMNS - normalized_headers
        if missing:
            raise ValueError(
                f"CSV dosyasında zorunlu sütunlar eksik: {', '.join(sorted(missing))}. "
                "Gerekli sütunlar: barcode, name, price"
            )

        categories = {c.slug: c for c in db.query(Category).all()}
        default_category = db.query(Category).first()
        if not default_category:
            raise ValueError("Sistemde tanımlı kategori bulunamadı.")

        created_count = 0
        updated_count = 0
        errors: List[str] = []
        now = datetime.now(timezone.utc)

        for idx, raw_row in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items()}
            barcode = row.get("barcode", "")
            name = row.get("name", "")
            price_str = row.get("price", "").replace(",", ".")

            if not barcode or not name or not price_str:
                errors.append(f"Satır {idx}: Barkod, ürün adı veya fiyat boş.")
                continue

            try:
                price = round(float(price_str), 2)
                if price <= 0:
                    raise ValueError()
            except ValueError:
                errors.append(f"Satır {idx} ({barcode}): Geçersiz fiyat değeri '{price_str}'.")
                continue

            stock_str = row.get("stock_quantity", "20")
            try:
                stock_quantity = max(0, int(float(stock_str)))
            except ValueError:
                stock_quantity = 20

            unit = row.get("unit") or "Adet"
            cat_slug = slugify_tr(row.get("category") or "")
            category = categories.get(cat_slug, default_category)
            primary_color = row.get("primary_color") or "#F5C518"

            existing = db.query(Product).filter(Product.barcode == barcode).first()
            if existing:
                existing.name = name
                existing.slug = f"{slugify_tr(name)}-{barcode[-4:]}"
                existing.price = price
                existing.stock_quantity = stock_quantity
                existing.unit = unit
                existing.category_id = category.id
                existing.is_stock_verified = True
                existing.is_sample_data = False
                existing.last_synced_at = now
                updated_count += 1
            else:
                new_prod = Product(
                    barcode=barcode,
                    name=name,
                    slug=f"{slugify_tr(name)}-{barcode[-4:]}",
                    category_id=category.id,
                    description=row.get("description") or f"{name} ({unit})",
                    price=price,
                    unit=unit,
                    stock_quantity=stock_quantity,
                    is_stock_verified=True,
                    is_sample_data=False,
                    is_active=True,
                    primary_color=primary_color,
                    secondary_color="#1E293B",
                    last_synced_at=now,
                )
                db.add(new_prod)
                created_count += 1

        # Update metadata
        cls._set_meta(db, "last_pos_csv_sync_at", now.isoformat())
        cls._set_meta(
            db,
            "last_pos_sync_source",
            f"CSV İçe Aktarım ({created_count} yeni, {updated_count} güncellendi)",
        )
        db.commit()

        return {
            "created_count": created_count,
            "updated_count": updated_count,
            "error_count": len(errors),
            "errors": errors[:20],
            "synced_at": now.isoformat(),
        }

    @staticmethod
    def export_products_csv(db: Session) -> str:
        output = io.StringIO()
        fieldnames = [
            "barcode",
            "name",
            "category",
            "price",
            "unit",
            "stock_quantity",
            "is_stock_verified",
            "is_sample_data",
            "primary_color",
            "description",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        products = db.query(Product).order_by(Product.name, Product.id).all()
        for p in products:
            writer.writerow(
                {
                    "barcode": p.barcode,
                    "name": p.name,
                    "category": p.category.name if p.category else "",
                    "price": f"{p.price:.2f}",
                    "unit": p.unit,
                    "stock_quantity": p.stock_quantity,
                    "is_stock_verified": "EVET" if p.is_stock_verified else "HAYIR",
                    "is_sample_data": "ORNEK" if p.is_sample_data else "GERCEK",
                    "primary_color": p.primary_color,
                    "description": p.description or "",
                }
            )
        return output.getvalue()

    @staticmethod
    def export_orders_csv(db: Session) -> str:
        output = io.StringIO()
        fieldnames = [
            "order_number",
            "status",
            "customer_name",
            "customer_phone",
            "total_amount",
            "delivery_type",
            "payment_method",
            "created_at",
            "items_summary",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        orders = db.query(Order).order_by(Order.created_at.desc()).all()
        for o in orders:
            items_summary = " | ".join(
                f"{item.product_name_snapshot} x{item.quantity} ({item.line_total:.2f} TL)"
                for item in o.items
            )
            writer.writerow(
                {
                    "order_number": o.order_number,
                    "status": o.status,
                    "customer_name": o.customer_name,
                    "customer_phone": o.customer_phone,
                    "total_amount": f"{o.total_amount:.2f}",
                    "delivery_type": o.delivery_type,
                    "payment_method": o.payment_method,
                    "created_at": o.created_at.isoformat(),
                    "items_summary": items_summary,
                }
            )
        return output.getvalue()

    @staticmethod
    def _set_meta(db: Session, key: str, value: str) -> None:
        meta = db.query(SystemMetadata).filter(SystemMetadata.key == key).first()
        if meta:
            meta.value = value
        else:
            db.add(SystemMetadata(key=key, value=value))
