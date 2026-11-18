# Eval run 20261118T160226Z (rules mode)

**24/35 scenarios passed.** Core: 24/35 · Probes (phrasings the rules weren't written for): 0/0.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| H-01 | followup |  | **FAIL** | turn 1: remembered seats: expected 2, got None | `tr_47e5eb128b93` #64 |
| H-02 | followup |  | pass |  |  |
| H-03 | followup |  | pass |  |  |
| H-04 | followup |  | pass |  |  |
| H-05 | followup |  | **FAIL** | turn 1: remembered max_width_cm: expected None, got 160; turn 1: kind: expected RECOMMEND, got UNSUPPORTED | `tr_cca6869ef3dd` #66 |
| H-06 | followup |  | pass |  |  |
| H-07 | followup |  | **FAIL** | turn 1: remembered max_width_cm: expected 180, got None | `tr_e8f68f8c30cf` #121 |
| H-08 | followup |  | pass |  |  |
| H-09 | new_product |  | **FAIL** | turn 1: remembered seats: expected None, got 2; turn 1: remembered max_width_cm: expected None, got 160; turn 1: remembered max_total_inr: expected None, got 15000; turn 1: remembered product should be a 'curtain', got 'sofa'; turn 1: kind: expected RECOMMEND, got UNSUPPORTED | `tr_8939610344eb` #64 |
| H-10 | new_product |  | pass |  |  |
| H-11 | off_topic |  | pass |  |  |
| H-12 | off_topic |  | pass |  |  |
| H-13 | off_topic |  | pass |  |  |
| H-14 | off_topic |  | pass |  |  |
| H-15 | off_topic |  | pass |  |  |
| H-16 | lookalike |  | pass |  |  |
| H-17 | lookalike |  | pass |  |  |
| H-18 | lookalike |  | pass |  |  |
| H-19 | typo |  | pass |  |  |
| H-20 | typo |  | pass |  |  |
| H-21 | typo |  | pass |  |  |
| H-22 | nonsense |  | pass |  |  |
| H-23 | nonsense |  | pass |  |  |
| H-24 | nonsense |  | pass |  |  |
| H-25 | rude |  | pass |  |  |
| H-26 | rude |  | pass |  |  |
| H-27 | trick |  | **FAIL** | turn 0: reason codes should include POLICY_REFUSAL, got [] | `tr_50bf91203089` #5 |
| H-28 | trick |  | pass |  |  |
| H-29 | compare |  | **FAIL** | turn 0: kind: expected DEFER, got RECOMMEND; turn 0: reason codes should include WORKFLOW_NOT_AVAILABLE, got [] | `tr_f0c480f8d14d` #61 |
| H-30 | compare |  | **FAIL** | turn 0: kind: expected DEFER, got NOT_AVAILABLE; turn 0: reason codes should include WORKFLOW_NOT_AVAILABLE, got ['MULTIPLE_PRODUCTS'] | `tr_ef2b1ed06861` #6 |
| H-31 | hinglish |  | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'bedsheet'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_737321037471` #5 |
| H-32 | hinglish |  | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'sofa'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_1e70659070bc` #5 |
| H-33 | hinglish |  | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'curtain'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_deed9d5eab00` #5 |
| H-34 | other |  | **FAIL** | turn 0: reason codes should include CATCH_ALL, got ['STORE_INFO'] | `tr_e6e7a1bc2d5a` #4 |
| H-35 | other |  | pass |  |  |
