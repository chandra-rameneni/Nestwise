# Eval run 20261121T064939Z (rules mode)

Payment keys: off for this run (checkout is mock).

**22/25 scenarios passed.** Core: 22/25 · Probes (phrasings the rules weren't written for): 0/0.

| Scenario | Group | Probe | Answered by | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|---|
| H2-01 | search_first |  | rules only | pass |  |  |
| H2-02 | search_first |  | rules only | pass |  |  |
| H2-03 | reply |  | rules only | pass |  |  |
| H2-04 | reply |  | rules only | pass |  |  |
| H2-05 | reply |  | rules only | pass |  |  |
| H2-06 | show |  | rules only | pass |  |  |
| H2-07 | show |  | rules only | **FAIL** | turn 1: kind: expected RECOMMEND, got CLARIFY | `tr_3442abee46c7` #11 |
| H2-08 | store |  | rules only | pass |  |  |
| H2-09 | help |  | rules only | pass |  |  |
| H2-10 | store |  | rules only | pass |  |  |
| H2-11 | store |  | rules only | **FAIL** | turn 0: reason codes should include STORE_INFO, got ['STORE_POLICY'] | `tr_f60d858b2e14` #5 |
| H2-12 | brand |  | rules only | **FAIL** | turn 0: kind: expected RECOMMEND, got NOT_AVAILABLE; turn 0: every recommendation should be a lal | `tr_268b73af72f3` #5 |
| H2-13 | brand |  | rules only | pass |  |  |
| H2-14 | material |  | rules only | pass |  |  |
| H2-15 | material |  | rules only | pass |  |  |
| H2-16 | shown |  | rules only | pass |  |  |
| H2-17 | shown |  | rules only | pass |  |  |
| H2-18 | shown |  | rules only | pass |  |  |
| H2-19 | several |  | rules only | pass |  |  |
| H2-20 | closest |  | rules only | pass |  |  |
| H2-21 | vague |  | rules only | pass |  |  |
| H2-22 | quantity |  | rules only | pass |  |  |
| H2-23 | stuck |  | rules only | pass |  |  |
| H2-24 | stuck |  | rules only | pass |  |  |
| H2-25 | lookalike |  | rules only | pass |  |  |
