import io
import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_and_store_layout(client: TestClient):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    layout_res = client.get("/api/v1/store/layout")
    assert layout_res.status_code == 200
    data = layout_res.json()
    assert data["store_name"] == "ÇEŞME MARKET 2"
    assert set(data["contact"]) == {"address", "phone", "whatsapp", "maps_url"}
    assert len(data["categories"]) == 10
    assert "aisles" not in data
    assert "has_exterior_photo" not in data


def test_product_catalog_search(client: TestClient):
    prods_res = client.get("/api/v1/products")
    assert prods_res.status_code == 200
    products = prods_res.json()
    assert len(products) >= 40

    first = products[0]
    assert "aisle_code" not in first
    assert "shelf_row" not in first
    assert "shelf_slot" not in first
    assert first["price"] > 0

    # Search by keyword
    search_res = client.get("/api/v1/products?q=Zeytinyağı")
    assert search_res.status_code == 200
    found = search_res.json()
    assert len(found) >= 1
    assert "Zeytinyağı" in found[0]["name"]


def test_server_side_price_calculation_and_idempotency(client: TestClient):
    products = client.get("/api/v1/products").json()
    target_prod = products[0]
    expected_unit_price = target_prod["price"]
    qty = 2

    # Even if a malicious client attempts to send custom fake price fields in JSON,
    # the backend schema and order service only use server DB prices.
    order_payload = {
        "customer_name": "Test Müşteri Çeşme",
        "customer_phone": "0532 999 88 77",
        "customer_email": "test@cesmemarket2.local",
        "order_note": "Mağazadan saat 16:00'da teslim alacağım",
        "idempotency_key": "pytest-idemp-key-001",
        "kvkk_approved": True,
        "items": [
            {
                "product_id": target_prod["id"],
                "quantity": qty,
                "price": 0.01,  # Attempted client price manipulation (ignored by backend)
            }
        ],
    }

    res1 = client.post("/api/v1/orders", json=order_payload)
    assert res1.status_code == 201
    order_data = res1.json()
    assert order_data["order_number"].startswith("CM2-")
    assert order_data["total_amount"] == round(expected_unit_price * qty, 2)
    assert order_data["status"] == "YENI_SIPARIS"
    assert order_data["location_session_token"]

    location_payload = {
        "order_number": order_data["order_number"],
        "location_session_token": order_data["location_session_token"],
        "consent": True,
        "latitude": 38.323,
        "longitude": 26.305,
        "accuracy_meters": 18.0,
    }
    location_res = client.post("/api/v1/orders/location/share", json=location_payload)
    assert location_res.status_code == 200
    assert location_res.json()["active"] is True
    assert client.get("/api/v1/admin/live-locations").status_code == 401

    admin_login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "CesmeAdmin2026!"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    live_locations = client.get("/api/v1/admin/live-locations", headers=admin_headers)
    assert live_locations.status_code == 200
    assert any(item["order_number"] == order_data["order_number"] for item in live_locations.json())

    stop_res = client.post(
        "/api/v1/orders/location/stop",
        json={
            "order_number": order_data["order_number"],
            "location_session_token": order_data["location_session_token"],
        },
    )
    assert stop_res.status_code == 200
    assert client.get("/api/v1/admin/live-locations", headers=admin_headers).json() == []

    # Setting an order to ready must end location sharing and clear the last coordinate.
    restarted_location = client.post("/api/v1/orders/location/share", json=location_payload)
    assert restarted_location.status_code == 200
    ready_res = client.patch(
        f"/api/v1/admin/orders/{order_data['id']}/status",
        json={"status": "HAZIR"},
        headers=admin_headers,
    )
    assert ready_res.status_code == 200
    assert client.get("/api/v1/admin/live-locations", headers=admin_headers).json() == []

    # Sending the exact same idempotency_key a second time must NOT create a duplicate order
    res2 = client.post("/api/v1/orders", json=order_payload)
    assert res2.status_code == 201
    assert res2.json()["id"] == order_data["id"]
    assert res2.json()["order_number"] == order_data["order_number"]

    # Customer can track the order status
    track_res = client.get(f"/api/v1/orders/track/{order_data['order_number']}")
    assert track_res.status_code == 200
    assert track_res.json()["order_number"] == order_data["order_number"]


def test_unauthorized_admin_access_blocked(client: TestClient):
    res = client.get("/api/v1/admin/dashboard")
    assert res.status_code == 401

    res_orders = client.get("/api/v1/admin/orders")
    assert res_orders.status_code == 401


def test_rbac_staff_vs_admin_and_order_workflow(client: TestClient):
    # 1. Login as STAFF (Mağaza Personeli)
    staff_login = client.post(
        "/api/v1/auth/login",
        json={"username": "personel", "password": "CesmePersonel2026!"},
    )
    assert staff_login.status_code == 200
    staff_token = staff_login.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}
    assert client.get("/api/v1/admin/live-locations", headers=staff_headers).status_code == 403

    # Staff can view orders and update order status through the workflow
    orders = client.get("/api/v1/admin/orders", headers=staff_headers).json()
    assert len(orders) >= 1
    target_order_id = orders[0]["id"]

    for next_status in ["ONAYLANDI", "HAZIRLANIYOR", "HAZIR"]:
        st_res = client.patch(
            f"/api/v1/admin/orders/{target_order_id}/status",
            json={"status": next_status, "note": f"Test geçişi: {next_status}"},
            headers=staff_headers,
        )
        assert st_res.status_code == 200
        assert st_res.json()["status"] == next_status

    # Staff CANNOT create a new product or import CSV (requires ADMIN)
    prods = client.get("/api/v1/products").json()
    p0 = prods[0]
    forbidden_price_change = client.put(
        f"/api/v1/admin/products/{p0['id']}",
        json={
            "barcode": p0["barcode"],
            "name": p0["name"],
            "category_id": p0["category_id"],
            "price": p0["price"] + 50.0,  # Staff attempting price modification
            "unit": p0["unit"],
            "stock_quantity": p0["stock_quantity"],
            "primary_color": p0["primary_color"],
            "secondary_color": p0["secondary_color"],
        },
        headers=staff_headers,
    )
    assert forbidden_price_change.status_code == 403

    # 2. Login as ADMIN (Mağaza Yöneticisi)
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "CesmeAdmin2026!"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin can import CSV to update/create verified POS products
    csv_content = (
        "barcode,name,category,price,unit,stock_quantity,primary_color\n"
        "8699999000111,Çeşme Sakızlı Kurabiye 250 g,Atıştırmalıklar,125.50,Paket,30,#F5C518\n"
    )
    files = {"file": ("urunler.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    csv_res = client.post("/api/v1/admin/import/csv", files=files, headers=admin_headers)
    assert csv_res.status_code == 200
    assert csv_res.json()["created_count"] == 1

    # Dangerous file upload extension (.exe / .php) must be rejected
    bad_files = {"file": ("exploit.php", io.BytesIO(b"<?php echo 1; ?>"), "application/octet-stream")}
    bad_upload = client.post("/api/v1/admin/upload-image", files=bad_files, headers=admin_headers)
    assert bad_upload.status_code == 400
