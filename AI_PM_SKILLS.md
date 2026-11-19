# AI PM skills used in IntentGuard

Every AI product management skill this project uses, where it lives, and whether it has been taught.
**Rule:** a skill is added here the moment a step builds or uses it, and taught in the same reply.

| # | Skill | Where it is in IntentGuard | Taught? |
|---|---|---|---|
| 1 | Business case and PRD first | `BUSINESS_CASE.md`, `PRD.md` | Yes |
| 2 | Writing evals before code | `evals/PHASE*_EVALS_DRAFT.md` | Yes |
| 3 | Baselines and held-out sets | `EVALS.md`, `evals/heldout_*.json` | Yes |
| 4 | Agent (eval) harness | `evals/run_evals.py`, `tests/` | Yes (2026-11-19) |
| 5 | Observability (traces, reason labels) | `tracing.py`, `web/inspector.html`, PRD §6A.4 | Yes (2026-11-19) |
| 6 | Error analysis | `evals/OBSERVATIONS.md` (O-1 to O-29) | No |
| 7 | Guardrails | `policy.py`, `checkout.py` (approval gate, price recheck, one order) | No |
| 8 | Grounding with citation checks | `qa.py` | No |
| 9 | Prompt-injection defence | `catalog.py`, `agent.py`, `tests/test_checkout.py` | No |
| 10 | Structured outputs | `intent.py` (pydantic schema), `llm.py` | No |
| 11 | Prompt versioning | `prompts/intent_v1–v4.txt`, `PROMPT_VERSION` | No |
| 12 | Model routing and fallbacks | `llm.py` (Gemini → OpenRouter → rules, 8 s budget, cool-down) | No |
| 13 | Human-in-the-loop | Cart approval (`checkout.py`); PM review of evals | Partly |
| 14 | Precision and recall | Not built yet | No |
| 15 | AI UX for trust (showing the agent's work, waiting states, approval) | PRD §5A, `web/` | Yes (2026-11-19) |
| 16 | Regression testing after a change (old tests + a failing-first test per new bug) | `tests/test_concurrency.py`, PRD §5A UI-08 | Yes (2026-11-19) |
| 17 | Latency and cost: use the model only where it adds value (measure first, then cut calls) | `intent.py` fast path (O-31), traces | Yes (2026-11-19) |
| 18 | Grounding in a knowledge base (RAG): approved store policy, cited sections | `STORE_POLICY.md`, `store_policy.py` (B41) | Yes (2026-11-19) |
| 19 | Conversation memory (context management): current product, last answer, recent turns | `agent.py` (R11, B38–B40), `qa.py` history | Yes (2026-11-19) |
| 20 | Routing: deciding which source or tool answers (listing, policy, code, refusal) | `store_policy.topic_of`, `intent.extract` (B41 routing) | Yes (2026-11-19) |
| 21 | Rate limits and fair eval runs (pacing, cool-downs, checking what actually ran) | `llm.py`, `evals/run_evals.py` (INTENTGUARD_EVAL_PACE_S) | Yes (2026-11-19) |
| 22 | Separating permissions around money (agent prepares, code sets the amount, human clicks, signature confirms) | `payments.py`, PRD §13 (RZ1–RZ10) | Yes (2026-11-19) |
| 23 | Observability across all chats (a dashboard: health, failures, safety, funnel; labelled traffic; the loop to evals) | `dashboard.py`, `web/dashboard.html`, PRD §14 | Yes (2026-11-19) |
