# Eval run 20261121T064938Z (rules mode)

Payment keys: off for this run (checkout is mock).

**27/35 scenarios passed.** Core: 27/35 · Probes (phrasings the rules weren't written for): 0/0.

| Scenario | Group | Probe | Answered by | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|---|
| H-01 | followup |  | rules only | **FAIL** | turn 1: remembered seats: expected 2, got None | `tr_0487a41f1e03` #64 |
| H-02 | followup |  | rules only | pass |  |  |
| H-03 | followup |  | rules only | pass |  |  |
| H-04 | followup |  | rules only | pass |  |  |
| H-05 | followup |  | rules only | **FAIL** | turn 1: remembered max_width_cm: expected None, got 160; turn 1: kind: expected RECOMMEND, got UNSUPPORTED | `tr_534342c1320b` #66 |
| H-06 | followup |  | rules only | pass |  |  |
| H-07 | followup |  | rules only | **FAIL** | turn 1: remembered max_width_cm: expected 180, got None | `tr_cb92184ce5e0` #121 |
| H-08 | followup |  | rules only | pass |  |  |
| H-09 | new_product |  | rules only | pass |  |  |
| H-10 | new_product |  | rules only | pass |  |  |
| H-11 | off_topic |  | rules only | pass |  |  |
| H-12 | off_topic |  | rules only | pass |  |  |
| H-13 | off_topic |  | rules only | pass |  |  |
| H-14 | off_topic |  | rules only | pass |  |  |
| H-15 | off_topic |  | rules only | pass |  |  |
| H-16 | lookalike |  | rules only | pass |  |  |
| H-17 | lookalike |  | rules only | pass |  |  |
| H-18 | lookalike |  | rules only | pass |  |  |
| H-19 | typo |  | rules only | pass |  |  |
| H-20 | typo |  | rules only | pass |  |  |
| H-21 | typo |  | rules only | pass |  |  |
| H-22 | nonsense |  | rules only | pass |  |  |
| H-23 | nonsense |  | rules only | pass |  |  |
| H-24 | nonsense |  | rules only | pass |  |  |
| H-25 | rude |  | rules only | pass |  |  |
| H-26 | rude |  | rules only | pass |  |  |
| H-27 | trick |  | rules only | **FAIL** | turn 0: reason codes should include POLICY_REFUSAL, got ['PAYMENT_IS_MANUAL'] | `tr_a9f033156a50` #4 |
| H-28 | trick |  | rules only | pass |  |  |
| H-29 | compare |  | rules only | pass |  |  |
| H-30 | compare |  | rules only | pass |  |  |
| H-31 | hinglish |  | rules only | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'bedsheet'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_e17b678e14e6` #5 |
| H-32 | hinglish |  | rules only | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'sofa'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_3c3f152e6f3a` #5 |
| H-33 | hinglish |  | rules only | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'curtain'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_46ccfc0dbcd1` #5 |
| H-34 | other |  | rules only | **FAIL** | turn 0: reason codes should include CATCH_ALL, got ['STORE_POLICY'] | `tr_b4d02157b1bc` #5 |
| H-35 | other |  | rules only | pass |  |  |
