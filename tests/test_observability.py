"""Authentication tests for the Homework 2 endpoints.

Offline: no Langfuse, Docker, or model key. Every request here is rejected
before the agent runs, so no model is called. Tracing is checked against the
recorded spans in Langfuse instead (Homework 2, Part E).
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from server import app as server_app


@pytest.fixture
def sessions(world: dict) -> None:
    server_app._SESSIONS.clear()


def _session(user_id: int, role: str) -> dict:
    return server_app.create_session(server_app.SessionCreate(user_id=user_id, role=role))


def _post(session_id: str, authorization: str | None) -> dict:
    return asyncio.run(
        server_app.post_message(
            session_id, server_app.MessageIn(message="Show my recent orders."), authorization
        )
    )


def test_create_session_rejects_role_that_differs_from_database(sessions: None) -> None:
    # User 1 is a shopper in the database; claiming support must not work.
    with pytest.raises(HTTPException) as exc:
        _session(1, "support")
    assert exc.value.status_code == 403
    assert server_app._SESSIONS == {}


def test_create_session_rejects_unknown_role_and_user(sessions: None) -> None:
    with pytest.raises(HTTPException) as exc:
        _session(1, "admin")
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException) as exc:
        _session(999_999, "shopper")
    assert exc.value.status_code == 404


def test_token_for_one_session_cannot_authorize_another(sessions: None) -> None:
    shopper = _session(1, "shopper")
    merchant = _session(9002, "merchant")
    with pytest.raises(HTTPException) as exc:
        _post(merchant["session_id"], f"Bearer {shopper['token']}")
    assert exc.value.status_code == 403


def test_missing_or_tampered_token_is_rejected(sessions: None) -> None:
    shopper = _session(1, "shopper")
    with pytest.raises(HTTPException) as exc:
        _post(shopper["session_id"], None)
    assert exc.value.status_code == 401
    # Swap in a payload that claims support but keep the shopper's signature.
    signature = shopper["token"].rsplit(".", 1)[1]
    forged_body = server_app.create_token(
        {"session_id": shopper["session_id"], "user_id": 1, "role": "support"}
    ).rsplit(".", 1)[0]
    with pytest.raises(HTTPException) as exc:
        _post(shopper["session_id"], f"Bearer {forged_body}.{signature}")
    assert exc.value.status_code == 401
