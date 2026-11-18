"""IntentGuard storefront: FastAPI backend + static pages in web/.

Run:  .venv/bin/uvicorn server:app --port 8000      (needs data/catalog.sqlite: python build_catalog.py)

Each browser gets its own agent Session (cookie `ig_session`), with its own copy of the catalog's
demo overrides, so a simulated price change in one browser never affects another. Sessions live in
memory and disappear when the server restarts.
"""
from __future__ import annotations

import secrets
from pathlib import Path
from typing import Optional

from fastapi import Cookie, FastAPI, HTTPException, Response as HTTPResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import intent as intent_mod
import llm
from agent import Response as AgentResponse
from agent import Session
from catalog import STORE_DB_PATH, ProductView, SqliteCatalog

WEB = Path(__file__).parent / "web"
COOKIE = "ig_session"
MAX_SESSIONS = 500

app = FastAPI(title="IntentGuard storefront")
app.mount("/static", StaticFiles(directory=WEB), name="static")
_sessions: dict[str, Session] = {}
_browse = SqliteCatalog(STORE_DB_PATH) if STORE_DB_PATH.exists() else None


# ----------------------------------------------------------------------------- sessions
def _session(sid: Optional[str], response: HTTPResponse) -> Session:
    if sid and sid in _sessions:
        return _sessions[sid]
    if len(_sessions) >= MAX_SESSIONS:
        _sessions.pop(next(iter(_sessions)))
    sid = secrets.token_urlsafe(16)
    _sessions[sid] = Session(catalog=SqliteCatalog(STORE_DB_PATH))
    response.set_cookie(COOKIE, sid, httponly=True, samesite="lax")
    return _sessions[sid]


def _catalog(sid: Optional[str]) -> SqliteCatalog:
    """Browsing uses the shopper's own session catalog when there is one, so simulated price or stock
    changes show on the pages they're looking at."""
    if sid and sid in _sessions:
        return _sessions[sid].catalog
    if _browse is None:
        raise HTTPException(503, "Catalog not built. Run: .venv/bin/python build_catalog.py")
    return _browse


# ----------------------------------------------------------------------------- serialisers
def card(p: ProductView) -> dict:
    return {"product_id": p.product_id, "title": p.title, "brand": p.brand, "category": p.category,
            "category_label": p.category_label, "price_inr": p.list_price_inr, "mrp_inr": p.mrp_inr,
            "shipping_inr": p.shipping_inr, "total_inr": p.total_for(), "stock": p.stock,
            "delivery_days": p.delivery_days, "image_url": p.image_url, "url": f"/product/{p.product_id}"}


def detail(p: ProductView) -> dict:
    return card(p) | {"description": p.description, "category_path": p.category_path, "specs": p.raw_specs,
                      "attributes": p.specs, "data_notes": p.data_notes, "source_flags": p.source_flags,
                      "source_url": p.url, "version": p.version}


def agent_json(s: Session, r: AgentResponse) -> dict:
    payload = _agent_payload(r)
    s.last_reply = payload                  # lets the panel restore the latest reply with its buttons
    return payload | {"state": state(s)}


def _agent_payload(r: AgentResponse) -> dict:
    return {"kind": r.kind, "message": r.message, "recommendations": r.recommendations,
            "rejected": r.rejected[:30], "rejected_count": len(r.rejected), "reason_codes": r.reason_codes,
            "cited_fields": r.cited_fields, "product_id": r.product_id,
            "order": None if r.order is None else {"order_id": r.order.order_id, "total_inr": r.order.total_inr}}


def state(s: Session) -> dict:
    cart = s.cart
    return {
        "cart": None if cart is None else {"cart_id": cart.cart_id, "product_id": cart.product_id, "title": cart.title,
                                           "qty": cart.qty, "total_inr": cart.total_inr, "status": cart.status},
        "approval": None if s.approval is None else {"approval_id": s.approval.approval_id,
                                                     "status": s.approval.status,
                                                     "approved_total_inr": s.approval.approved_total_inr},
        "orders": [{"order_id": o.order_id, "title": cart.title if cart and cart.cart_id == o.cart_id else o.product_id,
                    "total_inr": o.total_inr} for o in s.orders.orders.values()],
        "constraints": s.intent.constraint_fields() if s.intent else None,
        "trace_id": s.tracer.trace_id,
        "mode": llm.provider() or "rules", "model": llm.model_name(),
        "last_extractor": next((e["attrs"].get("extractor") for e in reversed(s.tracer.events)
                                if e["name"] == "intent.extracted"), None),
    }


# ----------------------------------------------------------------------------- pages
@app.get("/", include_in_schema=False)
def index_page():
    return FileResponse(WEB / "index.html")


@app.get("/product/{pid}", include_in_schema=False)
def product_page(pid: str):
    return FileResponse(WEB / "product.html")


@app.get("/inspector", include_in_schema=False)
def inspector_page():
    return FileResponse(WEB / "inspector.html")


# ----------------------------------------------------------------------------- catalog API
@app.get("/api/meta")
def meta(ig_session: Optional[str] = Cookie(None)):
    c = _catalog(ig_session)
    return {"categories": c.categories(), "source": {k: c.meta.get(k) for k in ("dataset", "licence", "price_note",
                                                                              "simulated", "version")},
            "mode": llm.provider() or "rules", "model": llm.model_name()}


@app.get("/api/products")
def products(q: str = "", category: Optional[str] = None, min_price: Optional[int] = None,
             max_price: Optional[int] = None, page: int = 1, page_size: int = 24,
             ig_session: Optional[str] = Cookie(None)):
    c = _catalog(ig_session)
    page, page_size = max(page, 1), min(max(page_size, 1), 60)
    ids, total = c.search_text(q, category=category or None, min_price=min_price, max_price=max_price,
                               limit=page_size, offset=(page - 1) * page_size)
    return {"total": total, "page": page, "page_size": page_size, "items": [card(c.get(i)) for i in ids]}


@app.get("/api/products/{pid}")
def product(pid: str, ig_session: Optional[str] = Cookie(None)):
    p = _catalog(ig_session).get(pid)
    if p is None:
        raise HTTPException(404, "Product not found")
    return detail(p)


# ----------------------------------------------------------------------------- agent API
class Message(BaseModel):
    text: str
    context: dict = {"page": "listing"}


class Pick(BaseModel):
    product_id: str


class PriceChange(BaseModel):
    product_id: str
    price_inr: int


@app.get("/api/agent/state")
def agent_state(response: HTTPResponse, ig_session: Optional[str] = Cookie(None)):
    s = _session(ig_session, response)
    return state(s) | {"history": [{"role": r, "text": t} for r, t in s.history],
                       "last_reply": getattr(s, "last_reply", None)}


@app.post("/api/agent/message")
def agent_message(body: Message, response: HTTPResponse, ig_session: Optional[str] = Cookie(None)):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Empty message")
    if len(text) > 1000:
        raise HTTPException(400, "Message too long (1,000 characters max)")
    s = _session(ig_session, response)
    ctx = {"page": "product", "product_id": body.context.get("product_id")} \
        if body.context.get("page") == "product" and body.context.get("product_id") else {"page": "listing"}
    return agent_json(s, s.handle_message(text, ctx))


@app.post("/api/agent/select")
def agent_select(body: Pick, response: HTTPResponse, ig_session: Optional[str] = Cookie(None)):
    s = _session(ig_session, response)
    return agent_json(s, s.select_product(body.product_id))


@app.post("/api/agent/{action}")
def agent_action(action: str, response: HTTPResponse, ig_session: Optional[str] = Cookie(None)):
    s = _session(ig_session, response)
    handler = {"approve": s.approve, "decline": s.decline, "checkout": s.checkout}.get(action)
    if handler is None:
        raise HTTPException(404, "Unknown action")
    return agent_json(s, handler())


@app.post("/api/session/reset")
def reset(response: HTTPResponse, ig_session: Optional[str] = Cookie(None)):
    _sessions.pop(ig_session or "", None)
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/trace")
def trace(response: HTTPResponse, ig_session: Optional[str] = Cookie(None)):
    s = _session(ig_session, response)
    return {"trace_id": s.tracer.trace_id, "events": s.tracer.events}


# ----------------------------------------------------------------------------- demo simulation
@app.post("/api/sim/price")
def sim_price(body: PriceChange, response: HTTPResponse, ig_session: Optional[str] = Cookie(None)):
    s = _session(ig_session, response)
    if s.catalog.get(body.product_id) is None or body.price_inr < 1:
        raise HTTPException(400, "Unknown product or invalid price")
    s.simulate_price_change(body.product_id, body.price_inr)
    return {"ok": True, "product": detail(s.catalog.get(body.product_id)), "state": state(s)}


@app.post("/api/sim/stock")
def sim_stock(body: Pick, response: HTTPResponse, ig_session: Optional[str] = Cookie(None)):
    s = _session(ig_session, response)
    if s.catalog.get(body.product_id) is None:
        raise HTTPException(400, "Unknown product")
    s.simulate_out_of_stock(body.product_id)
    return {"ok": True, "product": detail(s.catalog.get(body.product_id)), "state": state(s)}
