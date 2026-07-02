from app.safety.regex_detector import RegexDetector
from app.safety.sanitizer import sanitize_text, sanitize_value


def test_regex_detector_finds_high_risk_id_card():
    findings = RegexDetector().detect("我的身份证号是110101199001011234", scope="input")

    assert findings
    assert findings[0].risk_type == "privacy_leak"
    assert findings[0].risk_level.value == "HIGH"
    assert "110101199001011234" not in findings[0].evidence_masked


def test_sanitizer_masks_tool_payload_privacy_fields():
    payload = {
        "user_id": "u1002",
        "phone_number": "13812345678",
        "description": "邮箱 demo@example.com，身份证110101199001011234",
    }

    sanitized = sanitize_value(payload)

    assert sanitized["user_id"] == "u***2"
    assert sanitized["phone_number"] == "13***78"
    assert "demo@example.com" not in sanitized["description"]
    assert "110101199001011234" not in sanitized["description"]


def test_sanitize_text_masks_common_privacy_patterns():
    text = sanitize_text("手机号13812345678，银行卡6222021234567890123")

    assert "13812345678" not in text
    assert "6222021234567890123" not in text
    assert "138****5678" in text
