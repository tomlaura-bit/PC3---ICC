from decimal import Decimal

from app.aws_services import _json_value


def test_json_value_converts_decimals():
    value = {"integer": Decimal("3"), "price": Decimal("19.90")}
    assert _json_value(value) == {"integer": 3, "price": 19.9}
