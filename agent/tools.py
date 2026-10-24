"""Homework 1: the remaining commerce-agent tools.

The three lecture tools (`search_help_center`, `get_order`, `issue_refund`)
are implemented in agent/agent.py and are worked examples of the pattern:
check permissions first, go through agent/db.py for data, and return a
structured dict, never a prose error. The homework tools follow the same
pattern. agent/agent.py already wraps each function below as an SDK tool, so
once a function works here it works in chat with no further wiring.

Result convention (see agent/auth.py):
  - Success: a dict with "ok": True plus the payload fields named in each
    docstring.
  - Failure: {"ok": False, "error": <code>, "reason": <human-readable str>}.

Run the contract tests with: uv run pytest tests/test_hw_holes.py -k hw1
They are marked xfail and flip to passing as you implement each function.
"""

from __future__ import annotations

import re
from typing import Any

from agent import db
from agent.auth import AuthContext, can_cancel_order, can_view_order, permission_denied
from agent.helpcenter import load_policy_docs
from agent.killswitch import kill_switch

MAX_SEARCH_LIMIT = 25
DEFAULT_ORDER_LIMIT = 20


def get_policy(ctx: AuthContext, policy_id: str) -> dict[str, Any]:
    """Fetch one policy doc by its exact id. Risk tier: read.

    Every role may read every policy doc (the corpus is public help-center
    content), so this tool needs no permission check.

    Args:
        ctx: The caller's auth context. Unused here, but every tool takes it.
        policy_id: An exact policy id, e.g. "cw-returns" or
            "store-juniper-home-goods-policy". Matching is exact and
            case-sensitive; ids are the `policy_id` front-matter field of the
            files in data/policies/.

    Returns:
        On success: {"ok": True, "policy_id": str, "title": str,
        "audience": str, "body": str} where body is the markdown body of the
        doc without the front matter.
        If no doc has that id: {"ok": False, "error": "not_found",
        "reason": ...} naming the id that was requested.

    Implementation notes:
        agent.helpcenter.load_policy_docs() returns every parsed doc.
    """
    for doc in load_policy_docs():
        if doc.policy_id == policy_id:
            return {
                "ok": True,
                "policy_id": doc.policy_id,
                "title": doc.title,
                "audience": doc.audience,
                "body": doc.body,
            }
    return {"ok": False, "error": "not_found", "reason": f"no policy doc with id {policy_id!r}"}


def search_products(
    ctx: AuthContext,
    query: str,
    store: str | None = None,
    max_price_usd: float | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Search the product catalog. Risk tier: read.

    Every role may search products. Matching is deterministic keyword
    matching, not semantic search: a product matches when every whitespace
    token of `query` appears case-insensitively as a substring of the
    product's title or description.

    Args:
        ctx: The caller's auth context.
        query: Free-text query. Must be non-empty after stripping whitespace;
            otherwise return {"ok": False, "error": "invalid_argument",
            "reason": ...}.
        store: Optional store filter. Matched with
            agent.db.get_store_by_name (case-insensitive name or slug). If
            given and no store matches, return {"ok": False, "error":
            "not_found", "reason": ...} naming the store string.
        max_price_usd: Optional inclusive price ceiling. If given and not
            strictly positive, return an "invalid_argument" error.
        limit: Maximum products to return. Clamp to the range
            [1, MAX_SEARCH_LIMIT]; do not error on out-of-range values.

    Returns:
        {"ok": True, "products": [...], "count": <len(products)>} where each
        product is {"product_id": int, "store_id": int, "title": str,
        "price_usd": float}. Sort matches by price_usd ascending, then by
        product_id ascending, and truncate to `limit`. No matches is still a
        success: {"ok": True, "products": [], "count": 0}.

    Implementation notes:
        agent.db.list_products(conn, store_id) gives the candidate set.
        Use `with db.connection() as conn:` to close the database automatically.
    """
    tokens = query.lower().split()
    if not tokens:
        return {
            "ok": False,
            "error": "invalid_argument",
            "reason": "the search query is empty; ask the user what product they are looking for",
        }
    if max_price_usd is not None and max_price_usd <= 0:
        return {
            "ok": False,
            "error": "invalid_argument",
            "reason": f"max_price_usd must be greater than 0 (got {max_price_usd}); "
            "omit it to search without a price ceiling",
        }
    limit = max(1, min(limit, MAX_SEARCH_LIMIT))

    with db.connection() as conn:
        store_id = None
        if store is not None:
            found = db.get_store_by_name(conn, store)
            if found is None:
                return {
                    "ok": False,
                    "error": "not_found",
                    "reason": f"no store named {store!r}; check the store name or search all stores",
                }
            store_id = found.id
        candidates = db.list_products(conn, store_id)

    matches = []
    for product in candidates:
        text = f"{product.title} {product.description}".lower()
        if all(token in text for token in tokens):
            if max_price_usd is None or product.price_usd <= max_price_usd:
                matches.append(product)
    matches.sort(key=lambda p: (p.price_usd, p.id))

    products = [
        {
            "product_id": p.id,
            "store_id": p.store_id,
            "title": p.title,
            "price_usd": p.price_usd,
        }
        for p in matches[:limit]
    ]
    return {"ok": True, "products": products, "count": len(products)}


def list_my_orders(ctx: AuthContext) -> dict[str, Any]:
    """List recent orders in the caller's own scope. Risk tier: read.

    Role behavior, straight from the access matrix in SPEC.md:
        - shopper: the caller's own orders.
        - merchant: the caller's store's orders (ctx.store_id).
        - support: support staff have no orders of their own and look up
          specific orders with get_order instead, so return {"ok": False,
          "error": "invalid_argument", "reason": ...} saying exactly that.

    Returns:
        For shopper and merchant: {"ok": True, "orders": [...],
        "count": <len(orders)>} where each order is
        agent.db.Order.to_public_dict() and the list holds at most
        DEFAULT_ORDER_LIMIT orders, newest first (agent.db.list_orders_for_user
        and list_orders_for_store already sort and limit this way).

    Implementation notes:
        No permission check is needed beyond the role dispatch, because the
        scope is baked into which query you run. That is the point of the
        tool: the model cannot ask for someone else's orders through it.
    """
    if ctx.role == "support":
        return {
            "ok": False,
            "error": "invalid_argument",
            "reason": "support staff have no orders of their own, so there is nothing to list; "
            "look up a specific order by its order number with get_order instead",
        }
    with db.connection() as conn:
        if ctx.role == "shopper":
            orders = db.list_orders_for_user(conn, ctx.user_id, DEFAULT_ORDER_LIMIT)
        elif ctx.role == "merchant" and ctx.store_id is not None:
            orders = db.list_orders_for_store(conn, ctx.store_id, DEFAULT_ORDER_LIMIT)
        else:
            return permission_denied(f"role '{ctx.role}' (user {ctx.user_id}) has no order scope")
    public = [order.to_public_dict() for order in orders]
    return {"ok": True, "orders": public, "count": len(public)}


def cancel_order(ctx: AuthContext, order_id: int, reason: str) -> dict[str, Any]:
    """Cancel an order. Risk tier: write.

    This is the homework's write tool, and it must enforce two independent
    rules in this order:

    1. The access matrix (scope): use agent.auth.can_cancel_order. Shoppers
       may cancel only their own orders, merchants only their own store's
       orders, support any order. On failure return
       agent.auth.permission_denied(...) with a reason naming the role and
       the order id. Scope is checked before the status rule so that an
       out-of-scope caller learns nothing about the order's state.
    2. The pre-shipment rule (facts.yaml `cancel_cutoff`): only orders whose
       status is exactly "placed" can be cancelled, for every role. If the
       order is in scope but its status is not "placed", return
       {"ok": False, "error": "not_eligible", "reason": ...} that names the
       current status and states that orders can be cancelled only before
       shipment.

    Args:
        ctx: The caller's auth context.
        order_id: The order to cancel.
        reason: Free-text reason from the user; not validated.

    Returns:
        If no order has this id: {"ok": False, "error": "not_found",
        "reason": ...}.
        On success: {"ok": True, "order_id": order_id, "status": "cancelled"}
        after persisting the new status with agent.db.set_order_status.

    Implementation notes:
        Fetch with agent.db.get_order. Note the argument order of
        can_cancel_order(ctx, order_user_id, order_store_id).

    The Module 4 kill switch is checked first (before the scope and
    status rules and before your code), so that a paused write tool touches
    nothing. It is provided; the default ("off") returns None and falls
    through to your implementation.
    """
    paused = kill_switch("cancel_order")
    if paused is not None:
        return {"ok": False, "error": "paused", "reason": paused}
    with db.connection() as conn:
        order = db.get_order(conn, order_id)
        if order is None:
            return {"ok": False, "error": "not_found", "reason": f"no order #{order_id}"}
        # Scope first: an out-of-scope caller must learn nothing about the order.
        if not can_cancel_order(ctx, order.user_id, order.store_id):
            owner = "your store" if ctx.role == "merchant" else "your account"
            return permission_denied(
                f"role '{ctx.role}' (user {ctx.user_id}) is not authorized to cancel "
                f"order #{order_id} because it does not belong to {owner}"
            )
        if order.status != "placed":
            return {
                "ok": False,
                "error": "not_eligible",
                "reason": f"order #{order_id} is '{order.status}'; orders can be "
                "cancelled only before shipment, while their status is 'placed'",
            }
        db.set_order_status(conn, order_id, "cancelled")
    return {"ok": True, "order_id": order_id, "status": "cancelled"}


def find_order(ctx: AuthContext, query: str) -> dict[str, Any]:
    """Search the caller's orders by product name. Risk tier: read.

    Takes a natural-language query (e.g., "earmuffs I bought last week")
    and searches the authenticated user's orders for products whose name
    matches. Use fuzzy string matching (e.g., thefuzz.fuzz.partial_ratio
    or case-insensitive substring matching) to find orders whose product name is close to the
    query.

    Access rules: a shopper searches only the shopper's own orders, a
    merchant searches orders from the merchant's store, and support staff
    can search any orders. Use agent.db.list_order_search_candidates with
    user_id=ctx.user_id for shoppers, store_id=ctx.store_id for merchants,
    or all_orders=True only for support. Derive the scope from ctx, never
    from the query; reject unsupported roles or missing required identity.
    Use agent.db.list_products to map product IDs to product titles.

    The helper returns the complete authorised scope, newest first with
    order ID descending as the tie-breaker. Match product names first,
    preserve that order, then return at most five matches. Do not search
    only the 20 most recent orders. Convert matches with to_public_dict().

    Args:
        ctx: The caller's auth context.
        query: A natural-language description of the product.

    Returns:
        {"ok": True, "orders": [...]} with a list of matching orders
        (at most 5), each as the dict returned by agent.db. If no orders
        match, return {"ok": True, "orders": []}.
    """
    with db.connection() as conn:
        if ctx.role == "shopper" and ctx.user_id is not None:
            candidates = db.list_order_search_candidates(conn, user_id=ctx.user_id)
        elif ctx.role == "merchant" and ctx.store_id is not None:
            candidates = db.list_order_search_candidates(conn, store_id=ctx.store_id)
        elif ctx.role == "support":
            candidates = db.list_order_search_candidates(conn, all_orders=True)
        else:
            return permission_denied(f"role '{ctx.role}' (user {ctx.user_id}) has no order scope")
        titles = {p.id: p.title for p in db.list_products(conn)}

    # Score each order by how many query words appear in its product title, and
    # keep only the best-scoring orders, so filler words in a natural-language
    # query ("I bought last week") do not dilute a real product-name match.
    query_words = _words(query)
    scored = []
    for order in candidates:
        score = len(query_words & _words(titles.get(order.product_id, "")))
        if score:
            scored.append((score, order))
    if not scored:
        return {"ok": True, "orders": []}
    best = max(score for score, _ in scored)
    matches = [order for score, order in scored if score == best]
    return {"ok": True, "orders": [order.to_public_dict() for order in matches[:5]]}


def get_order_details(ctx: AuthContext, order_id: int) -> dict[str, Any]:
    """Show what was bought in one order. Risk tier: read.

    Added beyond the five HW1 holes: get_order and list_my_orders return only
    a product_id, so the agent could not tell a customer which item an order
    contains. Access follows get_order exactly (agent.auth.can_view_order):
    shoppers see their own orders, merchants their store's, support any.
    The scope check runs before any product lookup, so an out-of-scope caller
    learns nothing about the order.

    Returns:
        On success: {"ok": True, "order_id": int, "store_name": str | None,
        "product_name": str | None, "description": str | None,
        "unit_price_usd": float, "quantity": int}. unit_price_usd is what the
        customer paid per unit (order total / quantity), not today's catalog
        price. product_name is None when the catalog title is missing; never
        invent one.
        If no order has this id: {"ok": False, "error": "not_found", ...}.
        Out of scope: agent.auth.permission_denied(...).
    """
    with db.connection() as conn:
        order = db.get_order(conn, order_id)
        if order is None:
            return {"ok": False, "error": "not_found", "reason": f"no order #{order_id}"}
        if not can_view_order(ctx, order.user_id, order.store_id):
            return permission_denied(
                f"role '{ctx.role}' (user {ctx.user_id}) may not view order #{order_id}"
            )
        store = db.get_store(conn, order.store_id)
        product = next((p for p in db.list_products(conn) if p.id == order.product_id), None)
    return {
        "ok": True,
        "order_id": order.id,
        "store_name": store.name if store else None,
        "product_name": (product.title or None) if product else None,
        "description": product.description if product else None,
        "unit_price_usd": round(order.total_usd / order.quantity, 2),
        "quantity": order.quantity,
    }


def _words(text: str) -> set[str]:
    """Lowercase words with a trailing plural 's' dropped ("Earmuffs" -> "earmuff")."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words}
