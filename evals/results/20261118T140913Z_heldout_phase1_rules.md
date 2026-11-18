# Eval run 20261118T140913Z (rules mode)

**21/35 scenarios passed.** Core: 21/35 · Probes (phrasings the rules weren't written for): 0/0.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| H-01 | followup |  | **FAIL** | turn 1: remembered seats: expected 2, got None | `tr_e89d841bb63b` #9 |
| H-02 | followup |  | pass |  |  |
| H-03 | followup |  | pass |  |  |
| H-04 | followup |  | pass |  |  |
| H-05 | followup |  | **FAIL** | turn 1: remembered seats: expected 2, got None; turn 1: remembered product should be a 'sofa', got 'doesn t'; turn 1: kind: expected RECOMMEND, got NOT_AVAILABLE | `tr_652d719de0b3` #65 |
| H-06 | followup |  | pass |  |  |
| H-07 | followup |  | **FAIL** | turn 1: remembered max_width_cm: expected 180, got None; turn 1: kind: expected RECOMMEND, got CLARIFY | `tr_71d77cd13768` #9 |
| H-08 | followup |  | **FAIL** | turn 1: kind should not be NOT_AVAILABLE; turn 1: remembered seats: expected 2, got None; turn 1: remembered max_width_cm: expected 160, got None; turn 1: remembered product should be a 'sofa', got 'ones'; turn 1: message should not contain "We don't sell" | `tr_ec1bb4aea6fb` #65 |
| H-09 | new_product |  | **FAIL** | turn 1: remembered seats: expected None, got 2; turn 1: remembered max_width_cm: expected None, got 160; turn 1: remembered max_total_inr: expected None, got 15000; turn 1: remembered product should be a 'curtain', got 'sofa'; turn 1: kind: expected RECOMMEND, got UNSUPPORTED | `tr_75d4d3eb6973` #64 |
| H-10 | new_product |  | pass |  |  |
| H-11 | off_topic |  | **FAIL** | turn 0: kind: expected UNSUPPORTED, got NOT_AVAILABLE; turn 0: message should not contain "We don't sell"; turn 0: reason codes should include OFF_TOPIC, got ['NOT_SOLD_HERE'] | `tr_cc1de1d59fec` #5 |
| H-12 | off_topic |  | pass |  |  |
| H-13 | off_topic |  | pass |  |  |
| H-14 | off_topic |  | pass |  |  |
| H-15 | off_topic |  | **FAIL** | turn 0: kind: expected UNSUPPORTED, got NOT_AVAILABLE; turn 0: message should not contain "We don't sell" | `tr_262f6fd7a04e` #5 |
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
| H-27 | trick |  | **FAIL** | turn 0: reason codes should include POLICY_REFUSAL, got ['NOT_SOLD_HERE'] | `tr_7c5eb3645786` #5 |
| H-28 | trick |  | **FAIL** | turn 0: message should not contain "We don't sell" | `tr_c5d5c4adf791` #5 |
| H-29 | compare |  | **FAIL** | turn 0: kind: expected DEFER, got CLARIFY; turn 0: reason codes should include WORKFLOW_NOT_AVAILABLE, got [] | `tr_6e6ccaa7dbe2` #5 |
| H-30 | compare |  | **FAIL** | turn 0: kind: expected DEFER, got UNSUPPORTED; turn 0: reason codes should include WORKFLOW_NOT_AVAILABLE, got ['CATCH_ALL'] | `tr_ee0516e58c24` #4 |
| H-31 | hinglish |  | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'bedsheet'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_bb70bce3d718` #5 |
| H-32 | hinglish |  | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'sofa'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_42e8012d1c18` #5 |
| H-33 | hinglish |  | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'curtain'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_3c97439daa46` #5 |
| H-34 | other |  | pass |  |  |
| H-35 | other |  | pass |  |  |
