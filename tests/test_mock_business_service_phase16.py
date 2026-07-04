from fastapi.testclient import TestClient

from mock_business_service.main import app


client = TestClient(app)


def test_mock_business_service_returns_available_offers():
    response = client.get("/internal/users/u1001/offers")

    assert response.status_code == 200
    data = response.json()
    assert data["offers"]
    assert data["offers"][0]["offer_id"].startswith("OFF-")


def test_mock_business_service_recommends_offers_by_need_and_budget():
    response = client.post(
        "/internal/users/u1001/offers/recommend",
        json={"need": "流量不够用", "budget": 20},
    )

    assert response.status_code == 200
    assert response.json()["offers"][0]["offer_id"] == "OFF-DATA-20G"


def test_mock_business_service_returns_order_for_owner_only():
    ok_response = client.get("/internal/users/u1001/orders/ORD-20260701001")
    forbidden_response = client.get("/internal/users/u1002/orders/ORD-20260701001")

    assert ok_response.status_code == 200
    assert ok_response.json()["status"] == "processing"
    assert forbidden_response.status_code == 404
    assert forbidden_response.json()["detail"]["error_code"] == "ORDER_NOT_FOUND"
