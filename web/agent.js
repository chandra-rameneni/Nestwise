// IntentGuard assistant panel, shared by the listing and product pages.
// IGAgent.mount({ el, context, title, intro, suggestions, onState }) renders the chat, the cart and
// the demo controls into `el`. All decisions happen on the server; this file only displays them.
(function () {
  const inr = (n) => (n == null ? "price not listed" : "₹" + Number(n).toLocaleString("en-IN"));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const KIND_LABEL = {
    RECOMMEND: "RECOMMENDATIONS", ANSWER: "ANSWER", CLARIFY: "QUESTION", NOT_AVAILABLE: "NOT SOLD HERE",
    NO_ELIGIBLE: "NOTHING ELIGIBLE", CART_PROPOSED: "CART READY", APPROVED: "APPROVED", DECLINED: "DECLINED",
    ORDER_PLACED: "MOCK ORDER PLACED", BLOCKED: "STOPPED", DEFER: "NOT AVAILABLE YET", UNSUPPORTED: "",
  };

  function format(text) {
    // Light formatting: **bold**, line breaks, and [PRODUCTID] -> link to its page.
    return esc(text)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([A-Z0-9]{16})\]/g, '[<a href="/product/$1">$1</a>]')
      .replace(/\n/g, "<br>");
  }

  async function api(path, body) {
    const opts = body === undefined ? { method: "POST" } : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
    const r = await fetch(path, opts);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || `Request failed (${r.status})`);
    return data;
  }

  function mount({ el, context, title, intro, suggestions = [], onState }) {
    el.innerHTML = `
      <div class="dock-head">
        <div class="row"><h2>${esc(title)}</h2><span class="mode" id="ig-mode">…</span></div>
        <p>${esc(intro)}</p>
      </div>
      <div class="msgs" id="ig-msgs" aria-live="polite"></div>
      <div id="ig-cart"></div>
      <details class="demo" id="ig-demo" hidden>
        <summary>Demo: simulate a change to the cart item</summary>
        <div class="row">
          <label for="ig-price">New price ₹</label><input id="ig-price" type="number" min="1" step="50" inputmode="numeric">
          <button class="btn small" id="ig-setprice" type="button">Change price</button>
          <button class="btn small" id="ig-oos" type="button">Make out of stock</button>
        </div>
      </details>
      <div class="suggest" id="ig-suggest"></div>
      <form class="composer" id="ig-form">
        <label for="ig-input" class="sr-only" hidden>Message</label>
        <input id="ig-input" autocomplete="off" maxlength="1000" placeholder="Ask or tell me what you need…">
        <button class="btn primary" type="submit">Send</button>
      </form>`;
    const $ = (id) => el.querySelector("#" + id);
    const msgs = $("ig-msgs");
    let state = null;

    function addUser(text) {
      msgs.insertAdjacentHTML("beforeend", `<div class="msg user">${esc(text)}</div>`);
    }
    function checksHtml(checks) {
      return (checks || []).filter((c) => c.constraint !== "in_stock").map((c) =>
        `<span class="v ${c.status}" title="${esc(c.constraint)}: required ${esc(c.required)}, listing ${esc(c.observed)}">${esc(c.constraint.replace("max_", "").replace("_inr (incl. shipping)", " price").replace("_cm", ""))} ${c.status === "pass" ? "✓" : c.status === "fail" ? "✗" : "?"}</span>`).join("");
    }
    function addBot(r) {
      const label = KIND_LABEL[r.kind] ?? r.kind;
      let html = `<div class="msg bot">${label ? `<span class="kind ${esc(r.kind)}">${esc(label)}</span><br>` : ""}${format(r.message)}`;
      if (r.cited_fields && r.cited_fields.length) {
        html += `<div class="cite">Source: ${r.cited_fields.map((f) => `<span>${esc(f)}</span>`).join("")}</div>`;
      }
      if (r.recommendations && r.recommendations.length) {
        html += `<div class="recs">` + r.recommendations.map((x) => `
          <div class="rec">
            <a href="/product/${esc(x.product_id)}">${esc(x.title)}</a>
            <span class="meta">${inr(x.total_inr)} total · arrives in ${esc(x.delivery_days)} days (simulated)</span>
            <span class="checks">${checksHtml(x.checks)}</span>
            <div><button class="btn small" data-select="${esc(x.product_id)}" type="button">Add to cart</button></div>
          </div>`).join("") + `</div>`;
      }
      if (r.rejected && r.rejected.length) {
        html += `<details class="ruled"><summary>Ruled out (${r.rejected_count})</summary><ul>` +
          r.rejected.map((x) => `<li><a href="/product/${esc(x.product_id)}">${esc(x.title)}</a>: ${esc(x.reason_codes.join(", "))}</li>`).join("") +
          (r.rejected_count > r.rejected.length ? `<li>…and ${r.rejected_count - r.rejected.length} more</li>` : "") + `</ul></details>`;
      }
      msgs.insertAdjacentHTML("beforeend", html + "</div>");
    }
    function scroll() { msgs.scrollTop = msgs.scrollHeight; }

    function renderState(s) {
      state = s;
      const mode = $("ig-mode");
      mode.textContent = s.mode === "claude" ? "Claude" : "Rules mode";
      mode.className = "mode " + s.mode;
      mode.title = s.mode === "claude" ? "Requests are understood by Claude." :
        "No Anthropic API key is set, so a rule-based parser understands requests and product answers are read straight from the listing.";
      const c = s.cart, a = s.approval;
      const cartEl = $("ig-cart");
      if (c && c.status === "PROPOSED") {
        const approved = a && a.status === "APPROVED";
        cartEl.innerHTML = `<div class="cart">
          <div class="line">${esc(c.qty)} × <a href="/product/${esc(c.product_id)}">${esc(c.title)}</a></div>
          <div class="total">${inr(c.total_inr)}</div>
          <div class="status">${approved ? `Approved (${esc(a.approval_id)}). Price and stock are checked again before ordering.` : "Waiting for your approval. Nothing is ordered until you approve."}</div>
          <div class="actions">
            ${approved ? "" : `<button class="btn primary small" data-act="approve" type="button">Approve this exact cart</button>`}
            <button class="btn small ${approved ? "primary" : ""}" data-act="checkout" type="button">Place mock order</button>
            <button class="btn small" data-act="decline" type="button">Decline</button>
          </div></div>`;
        $("ig-demo").hidden = false;
        if (!$("ig-price").value) $("ig-price").value = (c.total_inr || 0) + 500;
      } else if (c && c.status === "ORDERED") {
        const o = s.orders[s.orders.length - 1];
        cartEl.innerHTML = `<div class="cart"><div class="line">Mock order <strong>${esc(o ? o.order_id : "")}</strong> placed for ${esc(c.title)}.</div>
          <div class="status">Simulation only: no payment taken, nothing ships.</div>
          <div class="actions"><button class="btn small" data-act="checkout" type="button">Retry checkout (should not create a second order)</button></div></div>`;
        $("ig-demo").hidden = true;
      } else {
        cartEl.innerHTML = "";
        $("ig-demo").hidden = true;
      }
      if (onState) onState(s);
    }

    async function run(promise, userText) {
      if (userText) addUser(userText);
      const wait = document.createElement("div");
      wait.className = "typing"; wait.textContent = "Checking…";
      msgs.appendChild(wait); scroll();
      try {
        const r = await promise;
        wait.remove();
        addBot(r);
        renderState(r.state);
      } catch (e) {
        wait.remove();
        msgs.insertAdjacentHTML("beforeend", `<div class="msg bot"><span class="kind BLOCKED">ERROR</span><br>${esc(e.message)}</div>`);
      }
      scroll();
    }

    $("ig-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const input = $("ig-input"), text = input.value.trim();
      if (!text) return;
      input.value = "";
      run(api("/api/agent/message", { text, context }), text);
    });
    $("ig-suggest").innerHTML = suggestions.map((s) => `<button type="button" data-say="${esc(s)}">${esc(s)}</button>`).join("");
    el.addEventListener("click", (e) => {
      const t = e.target.closest("button");
      if (!t) return;
      if (t.dataset.say) run(api("/api/agent/message", { text: t.dataset.say, context }), t.dataset.say);
      else if (t.dataset.select) run(api("/api/agent/select", { product_id: t.dataset.select }), "Add to cart: " + t.closest(".rec").querySelector("a").textContent);
      else if (t.dataset.act) run(api("/api/agent/" + t.dataset.act), { approve: "Approve", checkout: "Place mock order", decline: "Decline" }[t.dataset.act]);
    });
    $("ig-setprice").addEventListener("click", async () => {
      if (!state || !state.cart) return;
      const price = parseInt($("ig-price").value, 10);
      if (!(price > 0)) return;
      const r = await api("/api/sim/price", { product_id: state.cart.product_id, price_inr: price });
      msgs.insertAdjacentHTML("beforeend", `<div class="typing">Simulated: ${esc(state.cart.title)} now costs ${inr(price)} (before delivery).</div>`);
      renderState(r.state); scroll();
      document.dispatchEvent(new CustomEvent("ig:product-changed", { detail: r.product }));
    });
    $("ig-oos").addEventListener("click", async () => {
      if (!state || !state.cart) return;
      const r = await api("/api/sim/stock", { product_id: state.cart.product_id });
      msgs.insertAdjacentHTML("beforeend", `<div class="typing">Simulated: ${esc(state.cart.title)} is now out of stock.</div>`);
      renderState(r.state); scroll();
      document.dispatchEvent(new CustomEvent("ig:product-changed", { detail: r.product }));
    });

    // Restore the conversation (it lives on the server, so it follows the shopper across pages).
    fetch("/api/agent/state").then((r) => r.json()).then((s) => {
      const hist = s.history.slice(-30);
      const lastBot = hist.map((h) => h.role).lastIndexOf("assistant");
      hist.forEach((h, i) => {
        if (h.role === "user") addUser(h.text);
        else if (i === lastBot && s.last_reply && s.last_reply.message === h.text) addBot(s.last_reply);
        else msgs.insertAdjacentHTML("beforeend", `<div class="msg bot">${format(h.text)}</div>`);
      });
      renderState(s); scroll();
    });

    // Narrow screens: floating button opens the panel as a bottom sheet.
    const fab = document.getElementById("ig-fab");
    if (fab) fab.addEventListener("click", () => {
      const open = el.classList.toggle("open");
      fab.setAttribute("aria-expanded", String(open));
      fab.textContent = open ? "Close assistant" : "Ask the assistant";
      if (open) $("ig-input").focus();
    });
  }

  window.IGAgent = { mount, inr, esc };
})();
