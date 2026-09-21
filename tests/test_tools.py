from app.tools import query_account_quota, query_error_code, query_service_status


def test_query_error_code():
    result = query_error_code("429")
    assert result.environment == "demo"
    assert "限" in result.result["meaning"] or "配额" in result.result["meaning"]
    assert result.result["demo"] is True


def test_query_account_quota():
    result = query_account_quota("demo-account")
    assert result.result["status"] == "rate_limited"


def test_query_service_status():
    result = query_service_status("chat")
    assert result.result["status"] == "operational"

