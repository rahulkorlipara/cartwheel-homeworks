"""Cartwheel Studio: a local web UI for chatting with the agent and reviewing traces.

Run with:  uv run python -m studio      (then open http://127.0.0.1:8765)

Each session is saved as JSON in studio/traces/ with every turn's assistant
text, tool calls, tool results, final reply, and the database changes the turn
made. The review fields mirror the hw1-session.jsonl schema, and a session can
be exported there as one record.

This is a course helper, not part of the graded agent: it reuses build_agent,
the auth context, and the db layer exactly as the CLI does, and never changes
agent behavior.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from agents import RunConfig, Runner, SQLiteSession
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent import db
from agent.agent import build_agent, prompt_version
from agent.auth import ROLES, AuthContext
from agent.cli import MAX_TURNS
from agent.config import REPO_ROOT
from observability.instrument import load_env

STUDIO_DIR = Path(__file__).resolve().parent
TRACES_DIR = STUDIO_DIR / "traces"
HISTORY_DB = TRACES_DIR / "history.db"
SESSION_FILE = REPO_ROOT / "hw1-session.jsonl"

PROBLEM_SOURCES = {None, "prompt", "tool", "specification"}
TITLE_CHARS = 40  # sessions are titled with the start of their first message

load_env()
TRACES_DIR.mkdir(exist_ok=True)
app = FastAPI(title="Cartwheel Studio")


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _path(session_id: str) -> Path:
    if not session_id.replace("-", "").isalnum():
        raise HTTPException(400, "bad session id")
    return TRACES_DIR / f"{session_id}.json"


def _load(session_id: str) -> dict[str, Any]:
    path = _path(session_id)
    if not path.exists():
        raise HTTPException(404, f"no session {session_id}")
    return json.loads(path.read_text())


def _save(session: dict[str, Any]) -> None:
    session["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _path(session["id"]).write_text(json.dumps(session, indent=1, ensure_ascii=False, default=str))


def _ctx(session: dict[str, Any]) -> AuthContext:
    return AuthContext(
        user_id=session["user_id"], role=session["role"], store_id=session["store_id"]
    )


# ---------------------------------------------------------------------------
# Database change tracking (refunds, escalations, order statuses)
# ---------------------------------------------------------------------------


def _snapshot() -> dict[str, Any]:
    with db.connection() as conn:
        return {
            "refund_max": conn.execute("SELECT COALESCE(MAX(id), 0) FROM refunds").fetchone()[0],
            "escalation_max": conn.execute(
                "SELECT COALESCE(MAX(id), 0) FROM escalations"
            ).fetchone()[0],
            "statuses": dict(conn.execute("SELECT id, status FROM orders").fetchall()),
        }


def _db_changes(before: dict[str, Any]) -> dict[str, Any]:
    with db.connection() as conn:
        refunds = [
            dict(r)
            for r in conn.execute("SELECT * FROM refunds WHERE id > ?", (before["refund_max"],))
        ]
        escalations = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM escalations WHERE id > ?", (before["escalation_max"],)
            )
        ]
        after = dict(conn.execute("SELECT id, status FROM orders").fetchall())
    orders = [
        {"order_id": oid, "from": before["statuses"].get(oid), "to": status}
        for oid, status in after.items()
        if before["statuses"].get(oid) != status
    ]
    return {"refunds": refunds, "escalations": escalations, "orders": orders}


# ---------------------------------------------------------------------------
# Running one turn
# ---------------------------------------------------------------------------


def _message_text(raw: Any) -> str:
    content = raw.get("content") if isinstance(raw, dict) else getattr(raw, "content", None)
    parts = []
    for part in content or []:
        text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


def _maybe_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _steps(new_items: list[Any]) -> list[dict[str, Any]]:
    """Ordered steps: assistant text, tool calls, and tool results."""
    steps: list[dict[str, Any]] = []
    calls: dict[str, dict[str, Any]] = {}
    for item in new_items:
        if item.type == "message_output_item":
            steps.append({"type": "text", "text": _message_text(item.raw_item)})
        elif item.type == "tool_call_item":
            raw = item.raw_item
            args = raw.get("arguments") if isinstance(raw, dict) else getattr(raw, "arguments", None)
            step = {"type": "tool", "name": item.tool_name, "arguments": _maybe_json(args), "result": None}
            calls[item.call_id] = step
            steps.append(step)
        elif item.type == "tool_call_output_item" and item.call_id in calls:
            calls[item.call_id]["result"] = _maybe_json(item.output)
    return steps


async def _run_turn(session: dict[str, Any], message: str) -> dict[str, Any]:
    ctx = _ctx(session)
    agent = build_agent(ctx, model=session.get("model") or None)
    history = SQLiteSession(session["id"], str(HISTORY_DB))
    before = _snapshot()
    started = time.perf_counter()
    try:
        result = await Runner.run(
            agent,
            message,
            session=history,
            context=ctx,
            max_turns=MAX_TURNS,
            run_config=RunConfig(tracing_disabled=True),
        )
    except Exception as exc:  # surface model/provider errors in the UI
        return {
            "request": message,
            "steps": [],
            "response": None,
            "error": f"{type(exc).__name__}: {exc}",
            "latency_s": round(time.perf_counter() - started, 2),
            "db_changes": _db_changes(before),
            "at": datetime.now().isoformat(timespec="seconds"),
        }
    return {
        "request": message,
        "steps": _steps(result.new_items),
        "response": result.final_output,
        "error": None,
        "latency_s": round(time.perf_counter() - started, 2),
        "db_changes": _db_changes(before),
        "at": datetime.now().isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


class NewSession(BaseModel):
    role: str
    user_id: int
    model: str = ""


class Message(BaseModel):
    text: str


class Rename(BaseModel):
    title: str


class Review(BaseModel):
    expected: str = ""
    requirement: str = ""
    met_requirement: bool | None = None
    problem_source: str | None = None
    notes: str = ""


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STUDIO_DIR / "static" / "index.html")


@app.get("/api/info")
def info() -> dict[str, Any]:
    return {
        "model": os.environ.get("CARTWHEEL_MODEL") or "gpt-4o-mini",
        "prompt_version": prompt_version(),
        "roles": sorted(ROLES),
        "presets": {"shopper": 1, "merchant": 9002, "support": 9501},
        "session_file": SESSION_FILE.name,
        "session_file_records": _count_records(),
    }


def _count_records() -> int:
    if not SESSION_FILE.exists():
        return 0
    return sum(1 for line in SESSION_FILE.read_text().splitlines() if line.strip())


@app.get("/api/sessions")
def list_sessions() -> list[dict[str, Any]]:
    sessions = []
    for path in TRACES_DIR.glob("*.json"):
        s = json.loads(path.read_text())
        first = s["turns"][0]["request"] if s["turns"] else ""
        sessions.append(
            {
                "id": s["id"],
                "title": s.get("title") or first[:60] or "(empty session)",
                "role": s["role"],
                "user_id": s["user_id"],
                "created_at": s["created_at"],
                "updated_at": s.get("updated_at", s["created_at"]),
                "turns": len(s["turns"]),
                "met_requirement": s["review"].get("met_requirement"),
                "exported": bool(s.get("exported_at")),
            }
        )
    return sorted(sessions, key=lambda s: s["updated_at"], reverse=True)


@app.post("/api/sessions")
def create_session(body: NewSession) -> dict[str, Any]:
    if body.role not in ROLES:
        raise HTTPException(400, f"unknown role {body.role!r}")
    with db.connection() as conn:
        user = db.get_user(conn, body.user_id)
    if user is None:
        raise HTTPException(400, f"no user {body.user_id}")
    if user.role != body.role:
        raise HTTPException(400, f"user {user.id} has role '{user.role}', not '{body.role}'")
    session = {
        "id": uuid.uuid4().hex[:12],
        "title": "",
        "role": user.role,
        "user_id": user.id,
        "store_id": user.store_id,
        "model": body.model or os.environ.get("CARTWHEEL_MODEL") or "gpt-4o-mini",
        "prompt_version": prompt_version(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "turns": [],
        "review": Review().model_dump(),
        "exported_at": None,
    }
    _save(session)
    return session


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    return _load(session_id)


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, Any]:
    _path(session_id).unlink(missing_ok=True)
    return {"ok": True}


@app.post("/api/sessions/{session_id}/messages")
async def post_message(session_id: str, body: Message) -> dict[str, Any]:
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "empty message")
    session = _load(session_id)
    if not session.get("title"):
        session["title"] = text if len(text) <= TITLE_CHARS else text[:TITLE_CHARS].rstrip() + "…"
    turn = await _run_turn(session, text)
    session["turns"].append(turn)
    _save(session)
    return session


@app.patch("/api/sessions/{session_id}")
def rename_session(session_id: str, body: Rename) -> dict[str, Any]:
    title = body.title.strip()
    if not title:
        raise HTTPException(400, "title cannot be empty")
    session = _load(session_id)
    session["title"] = title
    _save(session)
    return session


@app.put("/api/sessions/{session_id}/review")
def save_review(session_id: str, body: Review) -> dict[str, Any]:
    if body.problem_source not in PROBLEM_SOURCES:
        raise HTTPException(400, f"problem_source must be one of {sorted(map(str, PROBLEM_SOURCES))}")
    session = _load(session_id)
    session["review"] = body.model_dump()
    _save(session)
    return session


def _record(session: dict[str, Any]) -> dict[str, Any]:
    """One hw1-session.jsonl record; multi-turn sessions keep every turn."""
    turns = [
        {
            "request": t["request"],
            "tool_calls": [
                {"name": s["name"], "arguments": s["arguments"], "result": s["result"]}
                for s in t["steps"]
                if s["type"] == "tool"
            ],
            "response": t["response"],
        }
        for t in session["turns"]
    ]
    review = session["review"]
    record = {
        "role": session["role"],
        "user_id": session["user_id"],
        "store_id": session["store_id"],
        "request": turns[0]["request"],
        "tool_calls": [c for t in turns for c in t["tool_calls"]],
        "response": turns[0]["response"],
        "expected": review["expected"],
        "requirement": review["requirement"] or None,
        "met_requirement": review["met_requirement"],
        "problem_source": None if review["met_requirement"] else review["problem_source"],
        "notes": review["notes"],
    }
    if len(turns) > 1:
        record["turns"] = turns
    return record


@app.get("/api/sessions/{session_id}/record")
def preview_record(session_id: str) -> dict[str, Any]:
    session = _load(session_id)
    if not session["turns"]:
        raise HTTPException(400, "session has no turns")
    return _record(session)


@app.post("/api/sessions/{session_id}/export")
def export_session(session_id: str) -> dict[str, Any]:
    session = _load(session_id)
    if not session["turns"]:
        raise HTTPException(400, "session has no turns")
    if session.get("exported_at"):
        raise HTTPException(409, f"already exported at {session['exported_at']}")
    review = session["review"]
    if review["met_requirement"] is None or not review["expected"].strip():
        raise HTTPException(400, "fill in 'expected' and 'met requirement' before exporting")
    if review["met_requirement"] is False and not review["problem_source"]:
        raise HTTPException(400, "a not-met record needs a problem source")
    with SESSION_FILE.open("a") as f:
        f.write(json.dumps(_record(session), ensure_ascii=False, default=str) + "\n")
    session["exported_at"] = datetime.now().isoformat(timespec="seconds")
    _save(session)
    return {"ok": True, "records": _count_records(), "session": session}


@app.post("/api/reset-data")
def reset_data() -> dict[str, Any]:
    """Regenerate data/cartwheel.db from the deterministic seed (sessions are kept)."""
    proc = subprocess.run(
        [sys.executable, "-m", "seed.generate"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise HTTPException(500, proc.stderr[-2000:])
    return {"ok": True, "output": proc.stdout.strip().splitlines()[-1:]}
