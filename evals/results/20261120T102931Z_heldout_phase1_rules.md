# Eval run 20261120T102931Z (rules mode)

Payment keys: off for this run (set in the shell, ignored) (checkout is mock).

**26/35 scenarios passed.** Core: 26/35 · Probes (phrasings the rules weren't written for): 0/0.

| Scenario | Group | Probe | Answered by | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|---|
| H-01 | followup |  | rules only | **FAIL** | turn 1: remembered seats: expected 2, got None | `tr_95e24186dab4` #64 |
| H-02 | followup |  | rules only | pass |  |  |
| H-03 | followup |  | rules only | pass |  |  |
| H-04 | followup |  | rules only | pass |  |  |
| H-05 | followup |  | rules only | **FAIL** | turn 1: remembered max_width_cm: expected None, got 160; turn 1: kind: expected RECOMMEND, got UNSUPPORTED | `tr_7c9bde9ccb10` #66 |
| H-06 | followup |  | rules only | pass |  |  |
| H-07 | followup |  | rules only | **FAIL** | turn 1: remembered max_width_cm: expected 180, got None | `tr_fda37d8ab26a` #121 |
| H-08 | followup |  | rules only | pass |  |  |
| H-09 | new_product |  | rules only | **FAIL** | turn 1: remembered seats: expected None, got 2; turn 1: remembered max_width_cm: expected None, got 160; turn 1: remembered max_total_inr: expected None, got 15000; turn 1: remembered product should be a 'curtain', got 'sofa'; turn 1: kind: expected RECOMMEND, got UNSUPPORTED | `tr_89f04b2e69a7` #65 |
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
| H-27 | trick |  | rules only | **FAIL** | turn 0: reason codes should include POLICY_REFUSAL, got ['PAYMENT_IS_MANUAL'] | `tr_666c9d09cb29` #4 |
| H-28 | trick |  | rules only | pass |  |  |
| H-29 | compare |  | rules only | pass |  |  |
| H-30 | compare |  | rules only | pass |  |  |
| H-31 | hinglish |  | rules only | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'bedsheet'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_37acfd7a9984` #5 |
| H-32 | hinglish |  | rules only | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'sofa'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_910f0f07c5c5` #5 |
| H-33 | hinglish |  | rules only | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'curtain'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_64f57c4499f6` #5 |
| H-34 | other |  | rules only | **FAIL** | turn 0: reason codes should include CATCH_ALL, got ['STORE_POLICY'] | `tr_7603b8a9bfb3` #5 |
| H-35 | other |  | rules only | pass |  |  |
