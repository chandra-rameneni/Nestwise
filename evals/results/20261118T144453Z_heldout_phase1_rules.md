# Eval run 20261118T144453Z (rules mode)

**25/35 scenarios passed.** Core: 25/35 · Probes (phrasings the rules weren't written for): 0/0.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| H-01 | followup |  | **FAIL** | turn 1: remembered seats: expected 2, got None | `tr_0231ec6b77b6` #9 |
| H-02 | followup |  | pass |  |  |
| H-03 | followup |  | pass |  |  |
| H-04 | followup |  | pass |  |  |
| H-05 | followup |  | **FAIL** | turn 1: remembered max_width_cm: expected None, got 160; turn 1: kind: expected RECOMMEND, got UNSUPPORTED | `tr_ebf87efc5210` #66 |
| H-06 | followup |  | pass |  |  |
| H-07 | followup |  | **FAIL** | turn 1: remembered max_width_cm: expected 180, got None; turn 1: kind: expected RECOMMEND, got CLARIFY | `tr_d11bbaddd657` #9 |
| H-08 | followup |  | pass |  |  |
| H-09 | new_product |  | **FAIL** | turn 1: remembered seats: expected None, got 2; turn 1: remembered max_width_cm: expected None, got 160; turn 1: remembered max_total_inr: expected None, got 15000; turn 1: remembered product should be a 'curtain', got 'sofa'; turn 1: kind: expected RECOMMEND, got UNSUPPORTED | `tr_35696f32a6a7` #64 |
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
| H-27 | trick |  | **FAIL** | turn 0: reason codes should include POLICY_REFUSAL, got ['CATCH_ALL'] | `tr_165c74f9202d` #6 |
| H-28 | trick |  | pass |  |  |
| H-29 | compare |  | **FAIL** | turn 0: kind: expected DEFER, got CLARIFY; turn 0: reason codes should include WORKFLOW_NOT_AVAILABLE, got [] | `tr_d1882479e38e` #5 |
| H-30 | compare |  | **FAIL** | turn 0: kind: expected DEFER, got UNSUPPORTED; turn 0: reason codes should include WORKFLOW_NOT_AVAILABLE, got ['CATCH_ALL'] | `tr_8e9fa391832c` #4 |
| H-31 | hinglish |  | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'bedsheet'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_a18e76f2fd05` #5 |
| H-32 | hinglish |  | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'sofa'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_b09de24b61b3` #5 |
| H-33 | hinglish |  | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'curtain'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_eb6c7ac4e21d` #5 |
| H-34 | other |  | pass |  |  |
| H-35 | other |  | pass |  |  |
