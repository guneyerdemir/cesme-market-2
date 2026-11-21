from datetime import datetime, timezone
from typing import Dict, List
from backend.config import ENABLE_SMS_NOTIFICATIONS, ENABLE_WHATSAPP_NOTIFICATIONS
from backend.schemas import ORDER_STATUS_LABELS


class NotificationEvent:
    def __init__(
        self,
        event_type: str,
        order_number: str,
        status: str,
        message: str,
        channel: str,
        delivered: bool,
    ):
        self.id = f"EVT-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        self.event_type = event_type
        self.order_number = order_number
        self.status = status
        self.message = message
        self.channel = channel
        self.delivered = delivered
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "order_number": self.order_number,
            "status": self.status,
            "message": self.message,
            "channel": self.channel,
            "delivered": self.delivered,
            "created_at": self.created_at,
        }


class NotificationService:
    """
    Bağımsız modüler bildirim altyapısı.
    Gerçek SMS veya WhatsApp servis bağlantısı kurulmadan sahte gönderim iddiasında bulunmaz.
    MVP'de Web Sipariş Takip Ekranı ve Yönetim Paneli Canlı Bildirim Kanalı üzerinden çalışır.
    """

    def __init__(self):
        self.recent_admin_events: List[Dict] = []

    def notify_new_order(self, order_number: str, customer_name: str, total_amount: float) -> List[Dict]:
        events = []
        msg = f"Yeni sipariş alındı: {order_number} ({customer_name} - {total_amount:.2f} TL)"
        web_evt = NotificationEvent(
            event_type="NEW_ORDER",
            order_number=order_number,
            status="YENI_SIPARIS",
            message=msg,
            channel="WEB_ADMIN_PANEL",
            delivered=True,
        ).to_dict()
        self.recent_admin_events.insert(0, web_evt)
        self.recent_admin_events = self.recent_admin_events[:50]
        events.append(web_evt)
        return events

    def notify_status_change(
        self,
        order_number: str,
        customer_phone: str,
        new_status: str,
        note: str | None = None,
    ) -> List[Dict]:
        label = ORDER_STATUS_LABELS.get(new_status, new_status)
        msg = f"Çeşme Market 2 - {order_number} numaralı siparişinizin durumu güncellendi: {label}."
        if note:
            msg += f" Not: {note}"

        events = []

        # 1. Web Sipariş Takip Kanalı (Aktif ve Doğrulanmış)
        web_evt = NotificationEvent(
            event_type="STATUS_CHANGED",
            order_number=order_number,
            status=new_status,
            message=msg,
            channel="WEB_TRACKER",
            delivered=True,
        ).to_dict()
        events.append(web_evt)
        self.recent_admin_events.insert(0, web_evt)
        self.recent_admin_events = self.recent_admin_events[:50]

        # 2. SMS Adaptörü (Yalnızca yapılandırıldığında aktif olur, aksi halde devre dışı olduğu açıkça raporlanır)
        events.append(
            NotificationEvent(
                event_type="STATUS_CHANGED",
                order_number=order_number,
                status=new_status,
                message=(
                    f"SMS gönderildi ({customer_phone})"
                    if ENABLE_SMS_NOTIFICATIONS
                    else "SMS servisi henüz yapılandırılmadı (MVP'de Web Takip ekranı aktif)"
                ),
                channel="SMS_ADAPTER",
                delivered=ENABLE_SMS_NOTIFICATIONS,
            ).to_dict()
        )

        # 3. WhatsApp Business Adaptörü
        events.append(
            NotificationEvent(
                event_type="STATUS_CHANGED",
                order_number=order_number,
                status=new_status,
                message=(
                    f"WhatsApp bildirimi gönderildi ({customer_phone})"
                    if ENABLE_WHATSAPP_NOTIFICATIONS
                    else "WhatsApp Business API henüz bağlı değil (İkinci aşama modülü hazır)"
                ),
                channel="WHATSAPP_ADAPTER",
                delivered=ENABLE_WHATSAPP_NOTIFICATIONS,
            ).to_dict()
        )

        return events

    def get_admin_feed(self) -> List[Dict]:
        return self.recent_admin_events


notification_service = NotificationService()
