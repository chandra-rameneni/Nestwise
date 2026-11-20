# Nestwise eval audit (2026-11-20)

**Question this answers:** can we trust Nestwise's eval numbers?
**Short answer:** the rules-mode numbers mostly hold up. The AI-mode numbers can't be trusted yet. And the scores change depending on the machine they run on.

Method: the `eval-audit` skill (ai-evals-course/evals-skills). It checks 6 areas against the real files, not a generic checklist.

---

## 1. Latest scores (re-run today on the current code)

All suites were re-run in rules mode on 2026-11-20, without payment keys set (see finding A).

| Suite | Kind | Score | What it means |
|---|---|---|---|
| Original (scenarios) | Written with the code | 39/39 | Passes by construction |
| Phase 1 | Written with the code | 36/36 | Passes by construction |
| Phase 2 | Written with the code | 40/40 | Passes by construction |
| Phase 3 | Written with the code | 14/14 | Passes by construction |
| Round 2 | Written with the code | 30/30 (18 skipped: AI only) | Passes by construction |
| **Held-out Phase 1** | Not used while coding | **26/35 (74%)** | Most honest rules number, but partly reused (finding D) |
| **Held-out Phase 2** | Not used while coding | **22/25 (88%)** | Honest |
| **Held-out Round 2** | Not used while coding | **14/15 (93%)** (10 skipped: AI only) | Honest, but small |
| **Model mode (MM-01 to MM-05)** | AI only | **5/5** (run 2026-11-20) | Valid AI run, but only 5 scenarios |
| **AI mode, held-out round 2** | AI on | **22/24 (92%)** (run 2026-11-20) | Valid AI run: 100% of readings by the AI. Per-model scores in EVALS.md |

**The number to quote today:** rules mode passes **62 of 75 held-out scenarios (83%)**. AI mode passes **22 of 24 held-out scenarios (92%)** (2026-11-20), mostly answered by Nemotron (OpenRouter) and Gemini 3.5 Flash.

Result files: `evals/results/20261120T0351*_rules.md`.

---

## 2. Findings, most important first

### A. Scores change depending on whether payment keys are set
**Status:** Fixed (2026-11-20). Tests now always remove the shell's Razorpay keys (the payment tests use fakes), and the eval runner switches them off for every run and writes "Payment keys: off" in each results file. Checked with keys set: 341 tests pass, and every eval set scores the same as without keys.
With the Razorpay test keys set in the shell, 17 unit tests and 4 eval scenarios fail (BT-01, BT-07, P3-W07, P3-W13): checkout now asks for payment. Without the keys, everything passes (338 tests). Nothing in the results file says which setup was used.
**Fix:** record "payment keys: on/off" in every results file, like the "valid AI run" label. Then either make the tests ignore the keys, or keep a separate set of evals for the paid checkout path.

### B. AI mode has no trustworthy score
**Status:** Mostly fixed (2026-11-20): held-out round 2 is a valid AI run, 22/24. The round 2 set was still only 68% AI, and the before/after on the old code isn't done. Original finding:
In the latest AI-mode held-out run, 0 of 9 messages were read by the AI and 2 of 16 answers were written by it. MM-01 to MM-05 have never run against a real model. The "invalid run" label exists (good), but no run has passed it yet.
**Fix:** do the paced before/after run (Option B) once the free quotas reset. Count only runs where the AI handled at least 80% of messages.

### C. Too few reviewed traces, and the reviews aren't confirmed
**Status:** Problem exists
`annotations.csv` has 6 rows, all labelled by the AI assistant with "needs human confirmation". Target: about 100 reviewed traces. The PM did review real chats (27 observations, plus a 14-row manual check). That's real error analysis, but it was never recorded trace by trace.
**Fix:** the PM confirms or corrects the 6 rows, then reviews about 50 to 100 AI-mode traces in a simple review screen (`build-review-interface` / `error-discovery`).

### D. The held-out sets were written by the same author as the code, and one was reused
**Status:** Problem exists
EVALS.md says the Phase 1 held-out set stopped being held out after fixes (21 → 25/35). It's still reported next to new scores. The held-out sets were written by the AI assistant that also wrote the code, so they share its blind spots.
**Fix:** retire Phase 1 held-out as a "regression" set. Write a fresh held-out set where the PM, or a second model that hasn't seen the code, writes the phrasings.

### E. Wording checks will misjudge AI-written replies
**Status:** Problem exists (AI mode only)
Many checks look for exact words: `'sorry'`, `'10 days'`, `'Heads up'`. They work for rules mode, where the wording is fixed. The AI words things differently. H2-N02 failed only because the AI didn't say "sorry".
**Fix:** keep exact-word checks for facts (prices, days, product names). For tone ("apologises", "sounds human"), have a human review the AI failures first. Only add an AI judge later, once there are human labels to check it against (`write-judge-prompt` → `validate-evaluator`).

### F. The failure list stops at F-024
**Status:** Problem exists
The failure taxonomy in EVALS.md is grounded in real failures (good), but it only covers F-001 to F-024. Observations O-25 to O-67 (long chats, policy questions, robotic wording, store info shown instead of "not sold") aren't grouped into categories.
**Fix:** add the newer observations to the taxonomy. New categories likely: "long-chat state", "AI confident guess", "robotic wording".

### G. Long chats are under-tested
**Status:** Partly fixed
The PM manual check found that scripted evals start every scenario fresh, but real shoppers have long chats (O-61, O-62). There's now one long-chat replay test.
**Fix:** add 3 to 5 long-chat scenarios (10+ turns, product switches, policy questions mid-chat) to the held-out set.

---

## 3. What's already good (keep doing it)

| Area | Status |
|---|---|
| Failures come from real use, not a generic list | OK: PM observations, trace reviews and manual checks |
| Every check is pass/fail | OK: no 1–5 scores |
| Code checks used where possible | OK: kind, reason codes, prices, remembered fields, cited fields |
| No AI judge without validation | OK: none exists, so there's nothing unvalidated |
| Every failure links to its trace and first bad event | OK: OBS-05 |
| Fixes come with regression and sabotage tests | OK: turning a fix off makes tests fail |
| Honest labelling | OK: "not a held-out score", "not a valid AI-mode run" |

---

## 4. Next steps, in order

1. **PM:** confirm or correct the 6 rows in `annotations.csv` (about 10 minutes).
2. **Fix A:** label payment keys on/off in results, so scores stop changing between machines.
3. **When quotas reset:** run the paced AI-mode before/after, including MM-01 to MM-05 (finding B).
4. **PM reviews about 50 AI-mode traces** from that run in a review screen. Group the failures (C, F).
5. **Fresh held-out set** written by the PM or a second model, including long chats (D, G).
6. **Only then** consider an AI judge for tone, checked against the PM's labels (E).

Re-run this audit after any big change (new model, new prompt, new feature).
