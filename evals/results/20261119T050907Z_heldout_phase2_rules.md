# Eval run 20261119T050907Z (rules mode)

**22/25 scenarios passed.** Core: 22/25 · Probes (phrasings the rules weren't written for): 0/0.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| H2-01 | search_first |  | pass |  |  |
| H2-02 | search_first |  | pass |  |  |
| H2-03 | reply |  | pass |  |  |
| H2-04 | reply |  | pass |  |  |
| H2-05 | reply |  | pass |  |  |
| H2-06 | show |  | pass |  |  |
| H2-07 | show |  | **FAIL** | turn 1: kind: expected RECOMMEND, got NOT_AVAILABLE; turn 1: message should not contain "We don't sell" | `tr_f66e0be15783` #13 |
| H2-08 | store |  | pass |  |  |
| H2-09 | help |  | pass |  |  |
| H2-10 | store |  | pass |  |  |
| H2-11 | store |  | **FAIL** | turn 0: reason codes should include STORE_INFO, got ['OFF_TOPIC'] | `tr_f5ff1f64eac5` #4 |
| H2-12 | brand |  | **FAIL** | turn 0: kind: expected RECOMMEND, got NOT_AVAILABLE; turn 0: every recommendation should be a lal | `tr_0eda9308837c` #5 |
| H2-13 | brand |  | pass |  |  |
| H2-14 | material |  | pass |  |  |
| H2-15 | material |  | pass |  |  |
| H2-16 | shown |  | pass |  |  |
| H2-17 | shown |  | pass |  |  |
| H2-18 | shown |  | pass |  |  |
| H2-19 | several |  | pass |  |  |
| H2-20 | closest |  | pass |  |  |
| H2-21 | vague |  | pass |  |  |
| H2-22 | quantity |  | pass |  |  |
| H2-23 | stuck |  | pass |  |  |
| H2-24 | stuck |  | pass |  |  |
| H2-25 | lookalike |  | pass |  |  |
