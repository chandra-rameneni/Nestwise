# Eval run 20261119T062522Z (gemini mode)

**11/43 scenarios passed.** Core: 11/43 · Probes (phrasings the rules weren't written for): 0/0. Skipped in gemini mode: 5.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| R2-C01 | conversation |  | **FAIL** | turn 1: message should not contain 'description'; turn 1: message should match '1\\.65\\s*m' | `tr_dc9adba20566` #11 |
| R2-C02 | conversation |  | **FAIL** | turn 2: message should match '1\\.65\\s*m'; turn 2: voice: robot wording matched "(?i)i'?d rather not guess"; turn 2: should start with an apology (Sorry) | `tr_8d65cd43c42c` #16 |
| R2-C03 | conversation |  | **FAIL** | turn 1: message should match '6\\.[89]\\d*\\s*(ft|feet)' | `tr_f7c1e34d69f5` #11 |
| R2-C04 | conversation |  | **FAIL** | turn 1: voice: robot wording matched '(?i)with mattress:'; turn 1: should start with an apology (Sorry) | `tr_c401228050d9` #11 |
| R2-C05 | conversation |  | **FAIL** | turn 1: kind: expected ANSWER, got RECOMMEND; turn 1: message should contain 'one' | `tr_bfaf03d1031f` #15 |
| R2-C06 | conversation |  | **FAIL** | turn 1: kind: expected ANSWER, got UNSUPPORTED; turn 1: message should contain 'temple'; turn 1: message should not contain 'not something I can help' | `tr_986a77370e77` #11 |
| R2-C07 | conversation |  | **FAIL** | turn 1: kind: expected CLARIFY, got RECOMMEND; turn 1: message should match '(?i)which' | `tr_d3472d36ce89` #121 |
| R2-C08 | conversation |  | pass |  |  |
| R2-X01 | challenge |  | **FAIL** | turn 1: kind: expected ANSWER, got RECOMMEND; turn 1: message should match '(?i)ply' | `tr_fc23039d9123` #15 |
| R2-X02 | challenge |  | **FAIL** | turn 1: message should match '(?i)sorry' | `tr_c3745f7b86b0` #65 |
| R2-X03 | challenge |  | **FAIL** | turn 1: message should match '(?i)only|care'; turn 1: voice: robot wording matched "(?i)i'?d rather not guess"; turn 1: should start with an apology (Sorry) | `tr_0e808b856f6a` #11 |
| R2-X04 | challenge |  | pass |  |  |
| R2-V01 | voice |  | **FAIL** | turn 0: voice: robot wording matched '(?i)with mattress:'; turn 0: should start with an apology (Sorry) | `tr_5c37c78989ed` #6 |
| R2-V02 | voice |  | **FAIL** | turn 0: voice: robot wording matched '(?i)\\(simulated\\)' | `tr_605c653637ab` #6 |
| R2-V03 | voice |  | pass |  |  |
| R2-V04 | voice |  | **FAIL** | turn 0: message should match '(?i)kids' | `tr_765640633e9e` #6 |
| R2-V05 | voice |  | **FAIL** | turn 0: message should match '(?i)spill|wipe' | `tr_d623fef3dc1a` #6 |
| R2-V06 | voice |  | **FAIL** | turn 0: voice: robot wording matched "(?i)i'?d rather not guess"; turn 0: should start with an apology (Sorry) | `tr_829dcb3e8ec5` #6 |
| R2-V08 | voice |  | **FAIL** | turn 0: message should match '(?i)sheesham' | `tr_5719d98a5a75` #6 |
| R2-P01 | policy |  | **FAIL** | turn 0: message should match '48'; turn 0: voice: robot wording matched '(?i)\\(simulated\\)'; turn 0: should cite a source matching '^P1\\b', got ['Delivery time', 'Delivery charge'] | `tr_2d7843a97fa4` #6 |
| R2-P02 | policy |  | **FAIL** | turn 0: message should match '(?i)repair|replace'; turn 0: should cite a source matching '^P2\\b', got ['Delivery Condition', 'Installation & Demo Details'] | `tr_354f8ff36e80` #6 |
| R2-P03 | policy |  | **FAIL** | turn 0: message should match '(?i)warranty'; turn 0: should cite a source matching '^P2\\b|^P8\\b', got ['Delivery Condition', 'Installation & Demo Details'] | `tr_b90047c756e2` #6 |
| R2-P04 | policy |  | **FAIL** | turn 0: message should match '10 days'; turn 0: should cite a source matching '^P3\\b', got [] | `tr_3434930c5048` #4 |
| R2-P05 | policy |  | **FAIL** | turn 0: kind: expected ANSWER, got DEFER; turn 0: message should match "(?i)no returns|can't be returned|cannot be returned" | `tr_215b3e297dc7` #5 |
| R2-P06 | policy |  | **FAIL** | turn 0: kind: expected ANSWER, got CART_PROPOSED; turn 0: message should match '\\b1\\b' | `tr_c3f173553645` #8 |
| R2-P07 | policy |  | **FAIL** | turn 0: message should match "(?i)not offered|don't offer|no cash"; turn 0: should cite a source matching '^P7\\b', got [] | `tr_9542ad5ed502` #4 |
| R2-P08 | policy |  | **FAIL** | turn 0: kind: expected ANSWER, got UNSUPPORTED; turn 0: message should match '5.7'; turn 0: should cite a source matching '^P4\\b', got [] | `tr_c31e1e9748ec` #4 |
| R2-N01 | not_policy |  | pass |  |  |
| R2-N02 | not_policy |  | pass |  |  |
| R2-N03 | not_policy |  | pass |  |  |
| R2-N04 | not_policy |  | pass |  |  |
| R2-N05 | not_policy |  | pass |  |  |
| R2-N06 | not_policy |  | pass |  |  |
| R2-F01 | frustration |  | pass |  |  |
| R2-F02 | frustration |  | **FAIL** | turn 1: reply should differ from turn 0 (same reply repeated); turn 1: message should match '(?i)size|material|deliver|care' | `tr_8e4bb053ac97` #11 |
| R2-F03 | frustration |  | **FAIL** | turn 0: message should match '(?i)this (bed|product)' | `tr_1fdb628e6d8a` #5 |
| R2-F04 | trick |  | **FAIL** | turn 0: message should match "(?i)can't help with that" | `tr_f8a2dff0995f` #4 |
| R2-F05 | trick |  | **FAIL** | turn 0: message should match "(?i)can't help with that" | `tr_16479938562e` #5 |
| R2-F06 | frustration |  | pass |  |  |
| R2-B01 | fit |  | **FAIL** | turn 0: kind: expected CLARIFY, got ANSWER; turn 0: message should match '165'; turn 0: message should match '210'; turn 0: message should match '(?i)space|room' | `tr_831ae5be45b3` #6 |
| R2-B02 | fit |  | **FAIL** | turn 1: message should match '(?i)\\bfits?\\b|will fit' | `tr_d1cf0a4edaea` #11 |
| R2-B03 | fit |  | **FAIL** | turn 1: message should match "(?i)won't fit|doesn't fit|too wide"; turn 1: message should match '15\\s*cm' | `tr_3c972b6675b5` #11 |
| R2-B04 | browse |  | **FAIL** | turn 0: message should not contain 'dining set'; turn 0: message should not contain 'bedsheet'; turn 0: message should match '(?i)showpiece'; turn 0: message should match '(?i)lamp|light' | `tr_9679f2406129` #5 |
