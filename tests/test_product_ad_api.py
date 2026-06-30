from app.db.init_db import initialize_database
from app.main import app
from fastapi.testclient import TestClient


def setup_module():
    initialize_database()


def test_product_ad_candidates_endpoint():
    client = TestClient(app)
    response = client.get("/api/product-ad/merchant/M001/candidates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["result"]["candidates"][0]["product_id"] == "P1001"


def test_product_ad_bid_range_endpoint():
    client = TestClient(app)
    response = client.get("/api/product-ad/product/P1001/bid-range?target_roi=4.5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["result"]["target_roi"] == 4.5
    assert "历史 ROI 低于目标 ROI" in " ".join(payload["result"]["risk_flags"])


def test_product_ad_bid_simulation_endpoint():
    client = TestClient(app)
    response = client.get(
        "/api/product-ad/product/P1001/bid-simulation?bid_multiplier=1.2&target_roi=4.5"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["result"]["product_id"] == "P1001"
    assert payload["result"]["target_roi"] == 4.5
    assert payload["result"]["roi_status"] == "risk"


def test_product_ad_bid_simulation_not_found_endpoint():
    client = TestClient(app)
    response = client.get(
        "/api/product-ad/product/P9999/bid-simulation?bid_multiplier=1.2&target_roi=4.5"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "product_not_found"


def test_product_ad_recall_endpoint():
    client = TestClient(app)
    response = client.get("/api/product-ad/recall?query=水光补水&merchant_id=M001")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["result"]["ranked_candidates"]["ranked_candidates"]


def test_product_ad_compare_endpoint():
    client = TestClient(app)
    response = client.get("/api/product-ad/compare/M001")

    assert response.status_code == 200
    assert response.json()["result"]["comparison"]


def test_product_ad_data_quality_endpoint():
    client = TestClient(app)
    response = client.get("/api/product-ad/data-quality")

    assert response.status_code == 200
    assert response.json()["ok"] is True
