"""IntentGuard Streamlit demo: shopping chat + Agent Inspector built from the session's real trace events."""
from __future__ import annotations

import json

import streamlit as st

import intent as intent_mod
from agent import Session

st.set_page_config(page_title="IntentGuard", page_icon="🛡️", layout="wide")

if "session" not in st.session_state:
    st.session_state.session = Session()
    st.session_state.last = None
s: Session = st.session_state.session


def run(fn, *args):
    st.session_state.last = fn(*args)


# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("IntentGuard")
    st.caption("P0 demo · synthetic catalog · simulated prices, stock and orders · no real payments")
    if intent_mod.llm_available():
        st.success(f"Intent extraction: Claude ({intent_mod.MODEL}, prompt {intent_mod.PROMPT_VERSION})")
    else:
        st.warning("Intent extraction: rule-based fallback (no Anthropic credentials set)")
    st.write(f"Trace ID: `{s.tracer.trace_id}`")
    if s.intent:
        st.subheader("Confirmed constraints")
        st.json(s.intent.constraint_fields() | {"intent_version": s.intent.version})

    st.subheader("Simulate a change")
    target = s.cart.product_id if s.cart and s.cart.status == "PROPOSED" else None
    if target:
        p = s.catalog.get(target)
        st.write(f"Cart item: {p.title} — now ₹{p.list_price_inr:,}")
        new_price = st.number_input("New item price (₹)", min_value=1, value=p.list_price_inr + 300, step=50)
        c1, c2 = st.columns(2)
        if c1.button("Change price"):
            s.simulate_price_change(target, int(new_price))
            st.rerun()
        if c2.button("Out of stock"):
            s.simulate_out_of_stock(target)
            st.rerun()
    else:
        st.caption("Put something in the cart to simulate a price or stock change.")

    if st.button("Reset session"):
        del st.session_state["session"]
        st.rerun()

shop, inspector = st.tabs(["🛒 Shop", "🔍 Agent Inspector"])

# ----------------------------------------------------------------------------- shop
with shop:
    st.caption("Try: *Find a Mac-compatible wireless keyboard and mouse combo within ₹4,000 including delivery, "
               "arriving in five days; prefer Logitech; ask before buying.*")
    for role, msg in s.history:
        with st.chat_message(role):
            st.markdown(msg.replace("\n", "  \n"))

    r = st.session_state.last
    if r is not None and r.recommendations and r.kind in ("RECOMMEND", "BLOCKED"):
        cols = st.columns(len(r.recommendations))
        for col, rec in zip(cols, r.recommendations):
            with col.container(border=True):
                st.markdown(f"**{rec['title']}**  \n`{rec['product_id']}` · {rec['brand']}")
                st.markdown(f"₹{rec['total_inr']:,} total · {rec['delivery_days']} days")
                if st.button("Select", key=f"sel_{rec['product_id']}_{len(s.history)}"):
                    run(s.select_product, rec["product_id"])
                    st.rerun()
    if r is not None and r.rejected:
        with st.expander(f"Excluded products ({len(r.rejected)}) and why"):
            st.table([{"product": x["title"], "id": x["product_id"], "total ₹": x["total_inr"],
                       "reasons": ", ".join(x["reason_codes"])} for x in r.rejected])

    if s.cart and s.cart.status == "PROPOSED":
        with st.container(border=True):
            st.markdown(f"**Cart** `{s.cart.cart_id}` · {s.cart.title} · **₹{s.cart.total_inr:,}**")
            approved = s.approval is not None and s.approval.status == "APPROVED"
            c1, c2, c3 = st.columns(3)
            if not approved and c1.button("Approve this exact cart"):
                run(s.approve)
                st.rerun()
            if c2.button("Place mock order"):
                run(s.checkout)
                st.rerun()
            if c3.button("Decline"):
                run(s.decline)
                st.rerun()
            if approved:
                st.caption(f"Approval `{s.approval.approval_id}` for ₹{s.approval.approved_total_inr:,}. "
                           "Price and stock are checked again at checkout.")
    if s.cart and s.cart.status == "ORDERED":
        if st.button("Retry checkout (idempotency check)"):
            run(s.checkout)
            st.rerun()

    if prompt := st.chat_input("What are you shopping for?"):
        run(s.handle_message, prompt)
        st.rerun()

# ----------------------------------------------------------------------------- inspector
with inspector:
    ev = s.tracer.events
    st.markdown(f"**Trace `{s.tracer.trace_id}`** · {len(ev)} events · "
                f"{len(s.tracer.find('tool'))} tool calls · "
                f"{sum(1 for e in ev if e['status'] in ('block', 'fail'))} blocks/failed checks · "
                f"orders created: {len(s.orders.orders)}")
    kinds = sorted({e["kind"] for e in ev})
    chosen = st.multiselect("Show event kinds", kinds, default=kinds)
    icon = {"ok": "✅", "pass": "✅", "fail": "❌", "block": "⛔", "warn": "⚠️", "error": "💥"}
    for e in ev:
        if e["kind"] not in chosen:
            continue
        dur = f" · {e['duration_ms']} ms" if e["duration_ms"] is not None else ""
        with st.expander(f"{e['seq']:>3}. {icon.get(e['status'], '•')} [{e['kind']}] {e['name']}{dur}"):
            st.caption(e["ts"])
            st.json(e["attrs"])
    st.download_button("Download trace (JSONL)", "\n".join(json.dumps(e, default=str) for e in ev),
                       file_name=f"{s.tracer.trace_id}.jsonl")
