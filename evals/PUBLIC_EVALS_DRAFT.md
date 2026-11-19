# Public repo guardrails: evals draft for review

**Status:** parked by the PM 2026-11-19 (repo stays private); revisit before any public release · **Date:** 2026-11-19 · **Source:** PRD §12 (G1–G9)
All of these are automated tests (no model needed), plus one manual check on a fresh copy of the repo.

| ID | Check | Should happen | Req |
|---|---|---|---|
| PUB-01 | `.env.example` | Exists, lists every setting the code reads (keys, limits, `INTENTGUARD_LLM`, `INTENTGUARD_TRACES`), and every value is empty | G1 |
| PUB-02 | A `.env` with `GEMINI_API_KEY=test` and nothing in the shell | The app sees the key (provider shows Gemini) | G1 |
| PUB-03 | Same key in the shell and in `.env` | The shell value wins | G1 |
| PUB-04 | `.env` is in `.gitignore` | Yes; `git check-ignore .env` succeeds | G1 |
| PUB-05 | No keys at all | Server starts, badge says Rules mode, a sofa search works | G2 |
| PUB-06 | Only `OPENROUTER_API_KEY` | Chain is OpenRouter only | G2 |
| PUB-07 | A key that gets HTTP 401 | Skipped for that provider's other models, not retried every message | G2 |
| PUB-08 | `check_setup.py` with a placeholder `YOUR_KEY` | Flags it as a placeholder; output never contains the key value or any part of it | G3 |
| PUB-09 | `check_setup.py` with no catalog built | Says how to build it | G3 |
| PUB-10 | Secret scan over tracked files | Finds nothing today | G4 |
| PUB-11 | Secret scan on a planted fake key (`AIza` + 35 characters) in a temp file | Catches it | G4 |
| PUB-12 | 41st message in one chat | The limit message, kind DEFER; no model call | G5 |
| PUB-13 | 9th model call in one minute (server-wide) | Answered in rules mode, badge "Rules (limit reached)"; no error | G5 |
| PUB-14 | Daily cap reached | Same as PUB-13 until the next day | G5 |
| PUB-15 | Limits changed in `.env` | New numbers used | G5 |
| PUB-16 | `INTENTGUARD_TRACES=off` | No trace file written; the inspector still works for the current chat (in memory) | G7 |
| PUB-17 | README | Has the 5 setup steps, the free-key links, "real vs simulated", the current test count, and no mention of a removed button | G8 |
| PUB-18 | `LICENSE` | Exists with the chosen licence; README names it and the data licence | G9 |
| PUB-19 | **Manual:** fresh clone into a new folder, follow the README only | Store runs in rules mode in under 10 minutes; then with my own key, AI mode | G1–G8 |
| PUB-20 | All earlier tests and evals | Still pass | — |
