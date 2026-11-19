// IntentGuard assistant panel, shared by the listing and product pages (PRD §5A).
// const ig = IGAgent.mount({ el, context, title, intro, suggestions, onState }) renders the chat, the cart and the
// demo controls into `el`, a slide-over panel. ig.open(), ig.close() and ig.send(text) let the page drive it.
// All decisions happen on the server; this file only displays them.
(function () {
  const inr = (n) => (n == null ? "price not listed" : "₹" + Number(n).toLocaleString("en-IN"));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  // Short status labels, shown only where the state matters to the shopper.
  // Only positive milestones get a label; the red "no match" and "blocked" labels read as errors (O-50).
  const KIND_LABEL = { CART_PROPOSED: "Cart ready", APPROVED: "Approved", ORDER_PLACED: "Order placed" };

  function format(text) {
    // Light formatting: **bold**, line breaks, and [PRODUCTID] -> link to its page.
    return esc(text)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([A-Z0-9]{16})\]/g, '[<a href="/product/$1">$1</a>]')
      .replace(/\n/g, "<br>");
  }

  function thumb(url, title, cls = "thumb") {
    const initials = esc((title || "?").slice(0, 2).toUpperCase());
    return `<span class="${cls}">${url ? `<img src="${esc(url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'ph',textContent:'${initials}'}))">` : `<span class="ph">${initials}</span>`}</span>`;
  }

  async function api(path, body) {
    const opts = body === undefined ? { method: "POST" } : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
    const r = await fetch(path, opts);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || `Request failed (${r.status})`);
    return data;
  }

  // One check -> a friendly chip, e.g. "✓ 3 seats", "✓ 198 cm wide", "✗ ₹36,000".
  function checkChip(c) {
    const mark = c.status === "pass" ? "✓" : c.status === "fail" ? "✗" : "?";
    const num = (v) => (typeof v === "number" ? Math.round(v) : v);
    const has = c.observed !== null && c.observed !== undefined && c.observed !== "listed";
    let text;
    if (c.constraint.startsWith("max_total_inr")) text = has ? inr(c.observed) : "price";
    else if (c.constraint === "seats") text = has ? `${num(c.observed)} seats` : "seats";
    else if (c.constraint === "max_width_cm") text = has ? `${num(c.observed)} cm wide` : "width";
    else if (c.constraint === "max_depth_cm") text = has ? `${num(c.observed)} cm deep` : "depth";
    else if (c.constraint === "max_height_cm") text = has ? `${num(c.observed)} cm high` : "height";
    else if (c.constraint === "max_delivery_days") text = has ? `${num(c.observed)} days` : "delivery";
    else if (c.constraint === "material") text = String(c.required);
    else text = c.constraint;
    const tip = `${c.constraint}: you asked for ${c.required}, the listing says ${c.observed ?? "nothing"}`;
    return `<span class="v ${esc(c.status)}" title="${esc(tip)}">${mark} ${esc(text)}</span>`;
  }

  let catalogSize = null;
  fetch("/api/meta").then((r) => r.json()).then((m) => {
    catalogSize = (m.categories || []).reduce((a, c) => a + c.count, 0);
  }).catch(() => {});

  // The steps the agent really takes, shown in order while waiting. Not live progress from the server.
  function stagesFor(kind, context) {
    if (kind === "approve") return ["Recording your approval"];
    if (kind === "checkout") return ["Checking the latest price and stock", "Placing your order"];
    if (kind === "decline") return ["Cancelling the cart"];
    if (kind === "select") return ["Building your cart", "Checking price and stock"];
    if (context.page === "product") return ["Reading your question", "Checking this product's listing", "Writing your answer"];
    const n = catalogSize ? catalogSize.toLocaleString("en-IN") + " products" : "the catalog";
    return ["Understanding your request", `Searching ${n}`, "Checking each requirement", "Writing your answer"];
  }

  function mount({ el, context, title, intro, suggestions = [], onState }) {
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-modal", "false");
    el.innerHTML = `
      <div class="dock-head">
        <div class="row"><h2>${esc(title)}</h2>
          <div class="right"><span class="mode" id="ig-mode">…</span>
            <button class="close" id="ig-close" type="button" aria-label="Close the assistant">×</button></div></div>
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
        <label for="ig-input" class="sr-only">Message</label>
        <input id="ig-input" autocomplete="off" maxlength="1000" placeholder="Ask or tell me what you need…">
        <button class="btn primary" type="submit">Send</button>
      </form>`;
    const $ = (id) => el.querySelector("#" + id);
    const msgs = $("ig-msgs");
    const fab = document.getElementById("ig-fab");
    let state = null;
    let lastFocus = null;

    function open() {
      if (el.classList.contains("open")) return;
      lastFocus = document.activeElement;
      el.classList.add("open");
      if (fab) fab.setAttribute("aria-expanded", "true");
      setTimeout(() => $("ig-input").focus({ preventScroll: true }), 50);
    }
    function close() {
      el.classList.remove("open");
      if (fab) fab.setAttribute("aria-expanded", "false");
      if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
    }

    function addUser(text) {
      msgs.insertAdjacentHTML("beforeend", `<div class="msg user">${esc(text)}</div>`);
    }
    function addBot(r) {
      const label = KIND_LABEL[r.kind];
      let html = `<div class="msg bot">${label ? `<span class="kind ${esc(r.kind)}">${esc(label)}</span><br>` : ""}${format(r.message)}`;
      if (r.cited_fields && r.cited_fields.length) {
        html += `<div class="cite">From the listing: ${r.cited_fields.map((f) => `<span>${esc(f)}</span>`).join("")}</div>`;
      }
      if (r.recommendations && r.recommendations.length) {
        html += `<div class="recs">` + r.recommendations.map((x) => `
          <div class="rec">
            <a href="/product/${esc(x.product_id)}" tabindex="-1" aria-hidden="true">${thumb(x.image_url, x.title)}</a>
            <div class="body">
              <a class="name" href="/product/${esc(x.product_id)}">${esc(x.title)}</a>
              <span class="meta"><strong>${inr(x.total_inr)}</strong> incl. delivery · ${esc(x.delivery_days)} days</span>
              <span class="checks">${(x.checks || []).filter((c) => c.constraint !== "in_stock").map(checkChip).join("")}</span>
              <button class="btn small" data-select="${esc(x.product_id)}" data-title="${esc(x.title)}" type="button">Add to cart</button>
            </div>
          </div>`).join("") + `</div>`;
      }
      if (r.rejected && r.rejected.length) {
        html += `<details class="ruled"><summary>Why others were left out (${r.rejected_count})</summary><ul>` +
          r.rejected.map((x) => `<li><a href="/product/${esc(x.product_id)}">${esc(x.title)}</a>: ${esc(x.why || "doesn't meet a requirement")}</li>`).join("") +
          (r.rejected_count > r.rejected.length ? `<li>…and ${r.rejected_count - r.rejected.length} more</li>` : "") + `</ul></details>`;
      }
      msgs.insertAdjacentHTML("beforeend", html + "</div>");
    }
    function scroll() { msgs.scrollTop = msgs.scrollHeight; }

    function renderState(s) {
      state = s;
      const mode = $("ig-mode");
      const ai = s.mode && s.mode !== "rules";
      const fellBack = ai && s.last_extractor && s.last_extractor.startsWith("rules");   // fast_path (O-31) is not a fallback
      mode.textContent = fellBack ? "Rules (AI busy)" : ai ? "AI mode" : "Rules mode";
      mode.className = "mode " + (ai && !fellBack ? "claude" : "rules");
      mode.title = fellBack ? "No AI model answered the last message (busy or out of free requests), so the rules handled it." :
        ai ? `Requests are understood by ${s.model || "a language model"} (${s.mode}). If it's unavailable, the rules take over.` :
        "No model API key is set, so a rule-based parser understands requests and product answers are read straight from the listing.";
      const c = s.cart, a = s.approval;
      const cartEl = $("ig-cart");
      if (c && c.status === "PROPOSED") {
        const approved = a && a.status === "APPROVED";
        cartEl.innerHTML = `<div class="cart">
          <div class="item">${thumb(c.image_url, c.title)}
            <div class="line">${esc(c.qty)} × <a href="/product/${esc(c.product_id)}">${esc(c.title)}</a></div></div>
          <div class="total">${inr(c.total_inr)}<small>incl. delivery</small></div>
          ${c.returnable === false ? `<div class="noreturn">No returns on this item. If it arrives broken, we'll replace it after a quick review.</div>` : ""}
          <div class="status">${approved ? "Approved. I'll check the price and stock again before ordering." : "Nothing is ordered until you approve this exact total."}</div>
          <div class="actions">
            ${approved ? `<button class="btn primary" data-act="checkout" type="button">Place order</button>`
                       : `<button class="btn primary" data-act="approve" type="button">Approve this exact cart</button>`}
            <button class="btn link" data-act="decline" type="button">Decline</button>
          </div></div>`;
        $("ig-demo").hidden = false;
        if (!$("ig-price").value) $("ig-price").value = (c.total_inr || 0) + 500;
      } else if (c && c.status === "ORDERED") {
        const o = s.orders[s.orders.length - 1];
        cartEl.innerHTML = `<div class="cart done"><span class="tick" aria-hidden="true">✓</span>
          <div class="total">${inr(o ? o.total_inr : c.total_inr)}</div>
          <div class="line">Order placed for ${esc(c.title)}.</div>
          <div class="status">Demo order ${esc(o ? o.order_id : "")}: no payment taken, nothing ships.</div>
          <button class="btn link" data-act="checkout" type="button">Try placing it again (no second order is made)</button></div>`;
        $("ig-demo").hidden = true;
      } else {
        cartEl.innerHTML = "";
        $("ig-demo").hidden = true;
      }
      if (onState) onState(s);
    }

    async function run(promise, userText, stages) {
      $("ig-suggest").hidden = true;              // suggestions only before the chat starts (O-10)
      if (userText) addUser(userText);
      const wait = document.createElement("div");
      wait.className = "working";
      wait.setAttribute("role", "status");
      wait.innerHTML = `<span class="dots" aria-hidden="true"><i></i><i></i><i></i></span><span class="stage"></span>`;
      const steps = stages && stages.length ? stages : ["Checking"];
      let i = 0;
      const show = () => { wait.querySelector(".stage").textContent = steps[i] + "…"; };
      show();
      const timer = setInterval(() => { if (i < steps.length - 1) { i++; show(); } }, 1100);
      msgs.appendChild(wait); scroll();
      try {
        const r = await promise;
        addBot(r);
        renderState(r.state);
      } catch (e) {
        msgs.insertAdjacentHTML("beforeend", `<div class="msg bot"><span class="kind BLOCKED">Something went wrong</span><br>${esc(e.message)}</div>`);
      } finally {
        clearInterval(timer);
        wait.remove();
      }
      scroll();
    }

    function send(text) {
      text = (text || "").trim();
      if (!text) return;
      open();
      run(api("/api/agent/message", { text, context }), text, stagesFor("message", context));
    }

    $("ig-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const input = $("ig-input"), text = input.value.trim();
      if (!text) return;
      input.value = "";
      send(text);
    });
    $("ig-suggest").innerHTML = suggestions.map((s) => `<button type="button" data-say="${esc(s)}">${esc(s)}</button>`).join("");
    $("ig-close").addEventListener("click", close);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && el.classList.contains("open")) close(); });
    el.addEventListener("click", (e) => {
      const t = e.target.closest("button");
      if (!t) return;
      if (t.dataset.say) send(t.dataset.say);
      else if (t.dataset.select) run(api("/api/agent/select", { product_id: t.dataset.select }), "Add to cart: " + t.dataset.title, stagesFor("select", context));
      else if (t.dataset.act) run(api("/api/agent/" + t.dataset.act), { approve: "Approve", checkout: "Place order", decline: "Decline" }[t.dataset.act], stagesFor(t.dataset.act, context));
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
      if (hist.length) $("ig-suggest").hidden = true;
      renderState(s); scroll();
    });

    if (fab) fab.addEventListener("click", open);

    return { open, close, send };
  }

  window.IGAgent = { mount, inr, esc, thumb };
})();
