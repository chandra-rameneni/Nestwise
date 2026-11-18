# Eval run 20261118T133515Z (rules mode)

**5/36 scenarios passed.** Core: 5/36 · Probes (phrasings the rules weren't written for): 0/0.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| P1-T01 | followup |  | **FAIL** | turn 1: reason codes should include REQUIREMENT_ADDED, got [] | `tr_1c5423ac8346` #121 |
| P1-T02 | followup |  | **FAIL** | turn 1: kind should not be NOT_AVAILABLE; turn 1: remembered product should be a 'sofa', got 'seater'; turn 1: message should not contain "We don't sell" | `tr_3740ee3acb2a` #9 |
| P1-T03 | followup |  | **FAIL** | turn 1: remembered seats: expected 2, got None; turn 1: message should not contain 'seats' | `tr_1a3c368211e6` #9 |
| P1-T04 | followup |  | **FAIL** | turn 1: remembered seats: expected 2, got None; turn 1: message should not contain 'seats' | `tr_8ecbca7a7465` #9 |
| P1-T05 | followup |  | **FAIL** | turn 1: remembered max_width_cm: expected 160, got None; turn 1: remembered product should be a 'sofa', got 'make seater'; turn 1: kind: expected RECOMMEND, got NOT_AVAILABLE; turn 1: message should not contain "We don't sell"; turn 1: reason codes should include REQUIREMENT_CHANGED, got ['NOT_SOLD_HERE'] | `tr_b14ecbb60c3b` #65 |
| P1-T06 | followup |  | **FAIL** | turn 1: remembered seats: expected 2, got None; turn 1: remembered product should be a 'sofa', got 'forget width'; turn 1: kind: expected RECOMMEND, got NOT_AVAILABLE; turn 1: message should not contain "We don't sell"; turn 1: reason codes should include REQUIREMENT_REMOVED, got ['NOT_SOLD_HERE'] | `tr_9b113d725e16` #65 |
| P1-T07 | followup |  | **FAIL** | turn 1: remembered max_total_inr: expected None, got 30000; turn 1: kind: expected RECOMMEND, got UNSUPPORTED; turn 1: reason codes should include REQUIREMENT_REMOVED, got [] | `tr_984075f12725` #64 |
| P1-R01 | new_product |  | **FAIL** | turn 1: remembered max_total_inr: expected None, got 30000 | `tr_3dfce73b3c81` #84 |
| P1-R02 | new_product |  | **FAIL** | turn 1: remembered seats: expected 3, got None; turn 1: remembered max_width_cm: expected 200, got None; turn 1: remembered product should be a 'sofa', got 'write song'; turn 1: kind: expected UNSUPPORTED, got NOT_AVAILABLE; turn 1: message should not contain "We don't sell"; turn 1: reason codes should include OFF_TOPIC, got ['NOT_SOLD_HERE'] | `tr_9b5402655373` #65 |
| P1-O01 | off_topic |  | **FAIL** | turn 0: kind: expected UNSUPPORTED, got NOT_AVAILABLE; turn 0: message should not contain "We don't sell"; turn 0: reason codes should include OFF_TOPIC, got ['NOT_SOLD_HERE'] | `tr_7ff8fe5d3d2d` #5 |
| P1-O02 | off_topic |  | **FAIL** | turn 0: kind: expected UNSUPPORTED, got NOT_AVAILABLE; turn 0: message should not contain "We don't sell"; turn 0: reason codes should include OFF_TOPIC, got ['NOT_SOLD_HERE'] | `tr_004dd7420229` #5 |
| P1-O03 | off_topic |  | **FAIL** | turn 0: kind: expected UNSUPPORTED, got NOT_AVAILABLE; turn 0: message should not contain "We don't sell"; turn 0: reason codes should include OFF_TOPIC, got ['NOT_SOLD_HERE'] | `tr_27b8e11dd565` #5 |
| P1-O04 | off_topic |  | **FAIL** | turn 0: reason codes should include OFF_TOPIC, got [] | `tr_480670036cf9` #4 |
| P1-G01 | off_topic |  | **FAIL** | turn 0: reason codes should include GREETING, got [] | `tr_f9e0a91c5788` #4 |
| P1-G02 | off_topic |  | **FAIL** | turn 0: message should contain 'welcome'; turn 0: message should not contain 'I can help'; turn 0: reason codes should include GREETING, got [] | `tr_97740c117169` #4 |
| P1-O05 | lookalike |  | pass |  |  |
| P1-O06 | lookalike |  | pass |  |  |
| P1-O07 | lookalike |  | pass |  |  |
| P1-Y01 | typo |  | **FAIL** | turn 0: message should contain 'Check the spelling'; turn 0: message should not contain "We don't sell"; turn 0: reason codes should include POSSIBLE_TYPO, got ['NOT_SOLD_HERE'] | `tr_3d89f31c1d86` #5 |
| P1-Y02 | typo |  | **FAIL** | turn 0: message should contain 'Check the spelling'; turn 0: message should not contain "We don't sell"; turn 0: reason codes should include POSSIBLE_TYPO, got ['NOT_SOLD_HERE'] | `tr_fed86434eb0a` #5 |
| P1-Y03 | typo |  | **FAIL** | turn 0: message should contain 'Check the spelling'; turn 0: message should not contain "We don't sell"; turn 0: reason codes should include POSSIBLE_TYPO, got ['NOT_SOLD_HERE'] | `tr_bbbc01a32e98` #5 |
| P1-Y04 | lookalike |  | pass |  |  |
| P1-N01 | nonsense |  | **FAIL** | turn 0: kind: expected UNSUPPORTED, got NOT_AVAILABLE; turn 0: message should not contain "We don't sell"; turn 0: reason codes should include UNCLEAR, got ['NOT_SOLD_HERE'] | `tr_9ba2514e7655` #5 |
| P1-N02 | nonsense |  | **FAIL** | turn 0: kind: expected UNSUPPORTED, got NOT_AVAILABLE; turn 0: message should not contain "We don't sell"; turn 0: reason codes should include UNCLEAR, got ['NOT_SOLD_HERE'] | `tr_b46fc23d2cd1` #5 |
| P1-A01 | rude |  | **FAIL** | turn 0: kind: expected UNSUPPORTED, got NOT_AVAILABLE; turn 0: message should contain 'Apologies for the inconvenience'; turn 0: message should not contain "We don't sell"; turn 0: reason codes should include ABUSIVE, got ['NOT_SOLD_HERE'] | `tr_894aee5b61a5` #5 |
| P1-A02 | rude |  | **FAIL** | turn 0: message should contain 'Apologies for the inconvenience'; turn 0: reason codes should include ABUSIVE, got [] | `tr_5b1976acbba3` #4 |
| P1-A03 | rude |  | pass |  |  |
| P1-K01 | trick |  | **FAIL** | turn 0: kind: expected UNSUPPORTED, got CLARIFY; turn 0: reason codes should include POLICY_REFUSAL, got [] | `tr_e63234273007` #5 |
| P1-K02 | trick |  | **FAIL** | turn 0: kind: expected UNSUPPORTED, got NOT_AVAILABLE; turn 0: message should not contain "We don't sell"; turn 0: reason codes should include POLICY_REFUSAL, got ['NOT_SOLD_HERE'] | `tr_f2ee460b7279` #5 |
| P1-K03 | trick |  | **FAIL** | turn 0: kind: expected UNSUPPORTED, got NOT_AVAILABLE; turn 0: message should not contain "We don't sell"; turn 0: reason codes should include POLICY_REFUSAL, got ['NOT_SOLD_HERE'] | `tr_8532b708b7bd` #5 |
| P1-C01 | compare |  | **FAIL** | turn 0: kind: expected DEFER, got NOT_AVAILABLE; turn 0: message should not contain "We don't sell"; turn 0: reason codes should include WORKFLOW_NOT_AVAILABLE, got ['NOT_SOLD_HERE'] | `tr_4c0d5f65166f` #5 |
| P1-C02 | compare |  | **FAIL** | turn 0: kind: expected DEFER, got CLARIFY; turn 0: reason codes should include WORKFLOW_NOT_AVAILABLE, got [] | `tr_a0e10ab54728` #5 |
| P1-X01 | catch_all |  | **FAIL** | turn 0: kind: expected UNSUPPORTED, got NOT_AVAILABLE; turn 0: message should not contain "We don't sell"; turn 0: reason codes should include CATCH_ALL, got ['NOT_SOLD_HERE'] | `tr_1ac59654ba78` #5 |
| P1-L01 | hinglish |  | **FAIL** | turn 0: message should contain 'sofa'; turn 0: message should contain 'Only English is supported'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got [] | `tr_734eba0f46ad` #5 |
| P1-L02 | hinglish |  | **FAIL** | turn 0: kind: expected CLARIFY, got NOT_AVAILABLE; turn 0: message should contain 'Only English is supported'; turn 0: reason codes should include LANGUAGE_NOT_SUPPORTED, got ['NOT_SOLD_HERE'] | `tr_0a339bba6af4` #5 |
| P1-L03 | hinglish |  | **FAIL** | turn 0: kind: expected UNSUPPORTED, got NOT_AVAILABLE; turn 0: message should not contain "We don't sell"; turn 0: reason codes should include CATCH_ALL, got ['NOT_SOLD_HERE'] | `tr_4f1c9354e5ee` #5 |
