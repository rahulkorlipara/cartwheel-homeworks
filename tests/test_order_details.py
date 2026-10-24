"""The student-added get_order_details tool (HW1 Part A extra tool), tested
offline through its function (no LLM, no API keys)."""

from __future__ import annotations

from agent.agent import TOOLS_BY_ROLE
from agent.auth import AuthContext
from agent.tools import get_order_details

SHOPPER_1 = AuthContext(user_id=1, role="shopper")
SHOPPER_2 = AuthContext(user_id=2, role="shopper")
MERCHANT_STORE_1 = AuthContext(user_id=9001, role="merchant", store_id=1)
MERCHANT_STORE_2 = AuthContext(user_id=9002, role="merchant", store_id=2)
SUPPORT = AuthContext(user_id=9501, role="support")


def test_owner_sees_the_item(world: dict) -> None:
    result = get_order_details(SHOPPER_1, 301)
    assert result == {
        "ok": True,
        "order_id": 301,
        "store_name": "Bright Socket Electronics",
        "product_name": "Signature Bluetooth Speaker",
        "description": result["description"],
        "unit_price_usd": 251.75,
        "quantity": 2,
    }
    assert "Signature Bluetooth Speaker" in result["description"]


def test_unit_price_is_what_was_paid_not_the_catalog_price(world: dict) -> None:
    # Demo order 4127 cost $84 for one vase whose catalog price differs.
    result = get_order_details(SHOPPER_1, 4127)
    assert result["unit_price_usd"] == 84.0
    assert result["quantity"] == 1


def test_merchant_sees_own_store_and_support_sees_any(world: dict) -> None:
    assert get_order_details(MERCHANT_STORE_1, 4127)["ok"] is True
    assert get_order_details(SUPPORT, 4127)["ok"] is True


def test_out_of_scope_callers_learn_nothing(world: dict) -> None:
    for ctx in (SHOPPER_2, MERCHANT_STORE_2):
        result = get_order_details(ctx, 4127)
        assert result["ok"] is False
        assert result["error"] == "permission_denied"
        assert set(result) == {"ok", "error", "reason"}
        for leak in ("Vase", "Blue Heron", "84"):
            assert leak not in result["reason"]


def test_unknown_order(world: dict) -> None:
    result = get_order_details(SHOPPER_1, 999999)
    assert result["ok"] is False
    assert result["error"] == "not_found"


def test_missing_catalog_title_is_not_invented(world: dict) -> None:
    # dq-product-missing-title: product 3 has an empty title.
    from agent import db

    with db.connection() as conn:
        row = conn.execute("SELECT id FROM orders WHERE product_id = 3 LIMIT 1").fetchone()
    assert row is not None
    result = get_order_details(SUPPORT, row["id"])
    assert result["product_name"] is None


def test_registered_for_every_role() -> None:
    for role, tools in TOOLS_BY_ROLE.items():
        assert "get_order_details" in [t.name for t in tools], role
