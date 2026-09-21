import pytest

from app.schemas import IntentType, Priority
from app.triage import classify_intent, extract_slots, missing_fields, priority_for


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("请转人工", IntentType.HUMAN_REQUEST),
        ("生产环境大面积服务不可用", IntentType.SERVICE_INCIDENT),
        ("账户额度不足", IntentType.QUOTA_BILLING),
        ("接口返回 401", IntentType.API_ERROR),
        ("如何配置流式输出", IntentType.OPERATION_GUIDE),
        ("这个产品支持什么模型", IntentType.PRODUCT_CONSULTATION),
    ],
)
def test_classify_intent(text, expected):
    assert classify_intent(text) == expected


def test_extract_slots():
    slots = extract_slots("生产环境刚刚所有请求返回 503，Request ID: req-12345")
    assert slots["environment"] == "production"
    assert slots["impact_scope"] == "大面积或全部请求失败"
    assert slots["error_code"] == "503"
    assert slots["request_id"] == "req-12345"
    assert slots["occurred_at"] == "刚刚"


def test_missing_fields_for_vague_error():
    assert set(missing_fields(IntentType.API_ERROR, {})) == {"error_code", "impact_scope"}


def test_priority_for_broad_production_incident():
    priority = priority_for(
        IntentType.SERVICE_INCIDENT,
        {"environment": "production", "impact_scope": "大面积或全部请求失败"},
    )
    assert priority == Priority.P1

