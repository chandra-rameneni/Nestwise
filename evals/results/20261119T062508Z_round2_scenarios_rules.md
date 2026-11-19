# Eval run 20261119T062508Z (rules mode)

**6/30 scenarios passed.** Core: 6/30 · Probes (phrasings the rules weren't written for): 0/0. Skipped in rules mode: 18.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| R2-C01 | conversation |  | **FAIL** | turn 1: message should not contain 'description'; turn 1: message should match '1\\.65\\s*m' | `tr_63d1d51d65a6` #11 |
| R2-C02 | conversation |  | **FAIL** | turn 2: message should match '1\\.65\\s*m'; turn 2: voice: robot wording matched "(?i)i'?d rather not guess"; turn 2: should start with an apology (Sorry) | `tr_6271426131f6` #16 |
| R2-C03 | conversation |  | **FAIL** | turn 1: message should match '6\\.[89]\\d*\\s*(ft|feet)' | `tr_a40d303d5bfb` #11 |
| R2-C05 | conversation |  | **FAIL** | turn 1: kind: expected ANSWER, got RECOMMEND; turn 1: message should contain 'one' | `tr_29f4c5f4889a` #15 |
| R2-C06 | conversation |  | **FAIL** | turn 1: kind: expected ANSWER, got UNSUPPORTED; turn 1: message should contain 'temple'; turn 1: message should not contain 'not something I can help' | `tr_448768bcd384` #11 |
| R2-C07 | conversation |  | **FAIL** | turn 1: kind: expected CLARIFY, got RECOMMEND; turn 1: message should match '(?i)which' | `tr_db14ed80602a` #121 |
| R2-X03 | challenge |  | **FAIL** | turn 1: message should match '(?i)only|care'; turn 1: voice: robot wording matched "(?i)i'?d rather not guess"; turn 1: should start with an apology (Sorry) | `tr_6486e0e15772` #11 |
| R2-X04 | challenge |  | pass |  |  |
| R2-V02 | voice |  | **FAIL** | turn 0: voice: robot wording matched '(?i)\\(simulated\\)' | `tr_eac9e36e4c62` #6 |
| R2-V06 | voice |  | **FAIL** | turn 0: voice: robot wording matched "(?i)i'?d rather not guess"; turn 0: should start with an apology (Sorry) | `tr_67395fe42097` #6 |
| R2-V07 | voice |  | **FAIL** | turn 0: voice: robot wording matched "(?i)i'?d rather not guess"; turn 0: should start with an apology (Sorry) | `tr_3a2f50f7674d` #6 |
| R2-V08 | voice |  | **FAIL** | turn 0: message should match '(?i)sheesham' | `tr_0247389618cf` #6 |
| R2-P05 | policy |  | **FAIL** | turn 0: kind: expected ANSWER, got DEFER; turn 0: message should match "(?i)no returns|can't be returned|cannot be returned" | `tr_e6447a679075` #5 |
| R2-P06 | policy |  | **FAIL** | turn 0: kind: expected ANSWER, got CART_PROPOSED; turn 0: message should match '\\b1\\b' | `tr_24801a40e2c8` #8 |
| R2-N02 | not_policy |  | pass |  |  |
| R2-N05 | not_policy |  | pass |  |  |
| R2-N06 | not_policy |  | pass |  |  |
| R2-F02 | frustration |  | **FAIL** | turn 1: reply should differ from turn 0 (same reply repeated); turn 1: message should match '(?i)size|material|deliver|care' | `tr_193d78cb6b06` #11 |
| R2-F03 | frustration |  | **FAIL** | turn 0: message should match '(?i)this (bed|product)' | `tr_cff6028d8cbe` #5 |
| R2-F04 | trick |  | **FAIL** | turn 0: message should match "(?i)can't help with that" | `tr_543f71405aac` #4 |
| R2-F05 | trick |  | **FAIL** | turn 0: message should match "(?i)can't help with that" | `tr_b553d39d7bf8` #5 |
| R2-F06 | frustration |  | pass |  |  |
| R2-B01 | fit |  | **FAIL** | turn 0: kind: expected CLARIFY, got ANSWER; turn 0: message should match '165'; turn 0: message should match '210'; turn 0: message should match '(?i)space|room' | `tr_0c18ca0ff433` #6 |
| R2-B02 | fit |  | **FAIL** | turn 1: message should match '(?i)\\bfits?\\b|will fit' | `tr_c06ed5e63399` #11 |
| R2-B03 | fit |  | **FAIL** | turn 1: message should match "(?i)won't fit|doesn't fit|too wide"; turn 1: message should match '15\\s*cm' | `tr_5e730779a731` #11 |
| R2-B04 | browse |  | **FAIL** | turn 0: message should not contain 'dining set'; turn 0: message should not contain 'bedsheet'; turn 0: message should match '(?i)showpiece'; turn 0: message should match '(?i)lamp|light' | `tr_237fa7ca732d` #5 |
| R2-B05 | closest |  | **FAIL** | turn 1: message should not contain 'these are the closest'; turn 1: message should not contain 'size'; turn 1: message should match '(?i)only home temple' | `tr_cc451e7d1278` #15 |
| R2-B06 | closest |  | **FAIL** | turn 1: 'left out' list repeats a product that was shown | `tr_466ff4b15bdc` #15 |
| R2-B07 | closest |  | **FAIL** | turn 2: message should match '298'; turn 2: message should match '(?i)anyway'; turn 3: remembered cart: expected 'PROPOSED', got None; turn 3: kind: expected CART_PROPOSED, got UNSUPPORTED | `tr_9483bedce8c1` #18 |
| R2-B08 | closest |  | pass |  |  |
