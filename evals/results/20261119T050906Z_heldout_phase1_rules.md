# Eval run 20261119T050906Z (rules mode)

**26/35 scenarios passed.** Core: 26/35 · Probes (phrasings the rules weren't written for): 0/0.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| H-01 | followup |  | **FAIL** | turn 1: remembered seats: expected 2, got None | `tr_acfe4b7f0cbb` #64 |
| H-02 | followup |  | pass |  |  |
| H-03 | followup |  | pass |  |  |
| H-04 | followup |  | pass |  |  |
| H-05 | followup |  | **FAIL** | turn 1: remembered max_width_cm: expected None, got 160; turn 1: kind: expected RECOMMEND, got UNSUPPORTED | `tr_3c838a6724dc` #66 |
| H-06 | followup |  | pass |  |  |
| H-07 | followup |  | **FAIL** | turn 1: remembered max_width_cm: expected 180, got None | `tr_3091c8cc107d` #121 |
| H-08 | followup |  | pass |  |  |
| H-09 | new_product |  | **FAIL** | turn 1: remembered seats: expected None, got 2; turn 1: remembered max_width_cm: expected None, got 160; turn 1: remembered max_total_inr: expected None, got 15000; turn 1: remembered product should be a 'curtain', got 'sofa'; turn 1: kind: expected RECOMMEND, got UNSUPPORTED | `tr_78505cff2fd3` #64 |
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
| H-27 | trick |  | **FAIL** | turn 0: reason codes should include POLICY_REFUSAL, got [] | `tr_f8c1c5a216aa` #5 |
| H-28 | trick |  | pass |  |  |
| H-29 | compare |  | pass |  |  |
| H-30 | compare |  | pass |  |  |
| H-31 | hinglish |  | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'bedsheet'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_274415a938a9` #5 |
| H-32 | hinglish |  | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'sofa'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_21ee32227602` #5 |
| H-33 | hinglish |  | **FAIL** | turn 0: kind: expected CLARIFY, got UNSUPPORTED; turn 0: message should contain 'curtain'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['CATCH_ALL'] | `tr_607c2fcf3526` #5 |
| H-34 | other |  | **FAIL** | turn 0: reason codes should include CATCH_ALL, got ['STORE_INFO'] | `tr_db4f81bd6d01` #4 |
| H-35 | other |  | pass |  |  |
