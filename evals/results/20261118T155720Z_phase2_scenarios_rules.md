# Eval run 20261118T155720Z (rules mode)

**4/40 scenarios passed.** Core: 4/40 · Probes (phrasings the rules weren't written for): 0/0.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| P2-S01 | search_first |  | **FAIL** | turn 0: kind: expected RECOMMEND, got CLARIFY; turn 0: message should not contain 'How many seats'; turn 0: all recommended totals should be <= 20000 (got []) | `tr_f5bf5c9112dd` #5 |
| P2-S02 | search_first |  | **FAIL** | turn 0: should show at least 1 products, showed 0; turn 0: kind: expected RECOMMEND, got CLARIFY; turn 0: message should not contain 'How many seats' | `tr_72034318ce0b` #5 |
| P2-S03 | search_first |  | pass |  |  |
| P2-S04 | search_first |  | pass |  |  |
| P2-R01 | show_results |  | **FAIL** | turn 1: remembered product should be a 'sofa', got 'results'; turn 1: kind: expected RECOMMEND, got NOT_AVAILABLE; turn 1: message should not contain "We don't sell" | `tr_11fc308592b0` #9 |
| P2-R02 | show_results |  | **FAIL** | turn 1: kind: expected RECOMMEND, got CLARIFY; turn 1: all recommended totals should be <= 20000 (got []) | `tr_174d5b4d7bcc` #9 |
| P2-R03 | show_results |  | **FAIL** | turn 1: kind: expected RECOMMEND, got UNSUPPORTED | `tr_0e9dd9efe424` #10 |
| P2-R04 | show_results |  | **FAIL** | turn 0: kind: expected CLARIFY, got NOT_AVAILABLE; turn 0: message should not contain "We don't sell" | `tr_2d30ec4002c8` #5 |
| P2-Q01 | reply_answer |  | **FAIL** | turn 1: remembered seats: expected 3, got None; turn 1: remembered max_width_cm: expected 200, got None; turn 1: kind: expected RECOMMEND, got NOT_AVAILABLE; turn 1: message should not contain "We don't sell" | `tr_18a4aac73c7b` #9 |
| P2-Q02 | reply_answer |  | **FAIL** | turn 1: remembered seats: expected 3, got None; turn 1: remembered max_width_cm: expected 200, got None; turn 1: kind: expected RECOMMEND, got NOT_AVAILABLE; turn 1: message should not contain "We don't sell" | `tr_85f4ee7dd28b` #9 |
| P2-Q03 | reply_answer |  | **FAIL** | turn 1: remembered seats: expected 3, got None; turn 1: remembered max_width_cm: expected 200, got None; turn 1: kind: expected RECOMMEND, got NOT_AVAILABLE; turn 1: message should not contain "We don't sell" | `tr_704b65491ef5` #9 |
| P2-Q04 | reply_answer |  | **FAIL** | turn 1: remembered seats: expected 3, got None; turn 1: kind: expected RECOMMEND, got NOT_AVAILABLE; turn 1: message should not contain "We don't sell" | `tr_57119a66e8ac` #65 |
| P2-Q05 | reply_answer |  | **FAIL** | turn 2: reply should differ from turn 1 (same reply repeated) | `tr_882d75e08986` #13 |
| P2-M01 | memory |  | **FAIL** | turn 1: remembered seats: expected 3, got None; turn 1: remembered max_width_cm: expected 200, got None; turn 1: remembered max_total_inr: expected 30000, got None; turn 1: remembered product should be a 'sofa', got 'mobile' | `tr_62f76038a5d9` #65 |
| P2-M02 | memory |  | **FAIL** | turn 1: message should not contain 'dumber' | `tr_2b4726730606` #9 |
| P2-H01 | help |  | **FAIL** | turn 0: message should not contain 'not something I can help'; turn 0: reason codes should include HELP, got ['OFF_TOPIC'] | `tr_6c04564bab59` #4 |
| P2-H02 | help |  | **FAIL** | turn 0: reason codes should include HELP, got ['OFF_TOPIC'] | `tr_532ecb9589c6` #4 |
| P2-H03 | help |  | **FAIL** | turn 0: reason codes should include HELP, got ['CATCH_ALL'] | `tr_9f84a2d475c5` #4 |
| P2-H04 | store_info |  | **FAIL** | turn 0: message should contain '2,043'; turn 0: reason codes should include STORE_INFO, got ['OFF_TOPIC'] | `tr_c139eeab6e21` #4 |
| P2-H05 | store_info |  | **FAIL** | turn 0: message should contain 'furniture'; turn 0: message should contain 'kitchen'; turn 0: reason codes should include STORE_INFO, got [] | `tr_8a395d6f008f` #5 |
| P2-H06 | store_info |  | **FAIL** | turn 0: message should contain "don't have"; turn 0: reason codes should include STORE_INFO, got ['CATCH_ALL'] | `tr_8ef5c6777e44` #4 |
| P2-H07 | lookalike |  | pass |  |  |
| P2-K01 | stuck |  | **FAIL** | turn 2: reason codes should include STUCK_RECOVERY, got ['CATCH_ALL'] | `tr_658b2f5a4dfd` #11 |
| P2-K02 | stuck |  | **FAIL** | turn 1: kind: expected RECOMMEND, got CLARIFY; turn 1: message should contain 'Sorry' | `tr_93fac3aa63bc` #9 |
| P2-B01 | brand |  | **FAIL** | turn 0: kind: expected RECOMMEND, got NOT_AVAILABLE; turn 0: every recommendation should be a jerry | `tr_75d664c62f17` #5 |
| P2-B02 | brand |  | **FAIL** | turn 0: kind: expected RECOMMEND, got UNSUPPORTED; turn 0: every recommendation should be a jerry | `tr_c3d20f48d7a7` #6 |
| P2-B03 | brand |  | **FAIL** | turn 0: kind: expected RECOMMEND, got NOT_AVAILABLE; turn 0: every recommendation should be a petshop7 | `tr_b661d9da291d` #5 |
| P2-B04 | material |  | **FAIL** | turn 0: kind: expected RECOMMEND, got NOT_AVAILABLE; turn 0: every recommendation should be a wood | `tr_521d5966a393` #5 |
| P2-B05 | name |  | **FAIL** | turn 0: kind: expected RECOMMEND, got UNSUPPORTED; turn 0: every recommendation should be a handiana | `tr_951c12abdedc` #4 |
| P2-B06 | material |  | **FAIL** | turn 1: remembered seats: expected 3, got None; turn 1: remembered material: expected 'leather', got None; turn 1: kind: expected RECOMMEND, got NOT_AVAILABLE; turn 1: every recommendation should be a leather | `tr_8d5e41b01780` #9 |
| P2-B07 | lookalike |  | pass |  |  |
| P2-P01 | shown |  | **FAIL** | turn 1: kind: expected ANSWER, got NOT_AVAILABLE; turn 1: message should contain 'HomeTown'; turn 1: message should contain '9 days' | `tr_ed9286bb69d1` #65 |
| P2-P02 | shown |  | **FAIL** | turn 1: kind: expected CART_PROPOSED, got NOT_AVAILABLE | `tr_857de15d9bdf` #65 |
| P2-P03 | shown |  | **FAIL** | turn 1: kind: expected ANSWER, got UNSUPPORTED; turn 1: message should contain '9 days' | `tr_409ba6f8d922` #64 |
| P2-P04 | shown |  | **FAIL** | turn 1: kind: expected CLARIFY, got RECOMMEND; turn 1: message should contain 'HomeTown'; turn 1: message should contain 'Durian' | `tr_bc7b62795c21` #83 |
| P2-N01 | nothing_matches |  | **FAIL** | turn 0: should show at least 1 products, showed 0; turn 0: kind: expected NO_ELIGIBLE, got CLARIFY; turn 0: message should contain 'over' | `tr_feaeff0a3e3d` #5 |
| P2-N02 | several |  | **FAIL** | turn 0: some shown product should be a bedsheet; turn 0: some shown product should be a curtain; turn 0: kind: expected RECOMMEND, got NOT_AVAILABLE | `tr_eac01b0672d1` #5 |
| P2-N03 | several |  | **FAIL** | turn 0: some shown product should be a sofa; turn 0: kind: expected RECOMMEND, got CLARIFY; turn 0: message should contain 'coffee table' | `tr_62a79756e804` #5 |
| P2-N04 | vague |  | **FAIL** | turn 0: reason codes should include VAGUE_REQUIREMENT, got [] | `tr_4a28aa353af1` #5 |
| P2-N05 | quantity |  | **FAIL** | turn 0: remembered cart_qty: expected 2, got 1 | `tr_c68a9249ec5e` #8 |
