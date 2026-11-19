# Eval run 20261119T062509Z (rules mode)

**1/15 scenarios passed.** Core: 1/15 · Probes (phrasings the rules weren't written for): 0/0. Skipped in rules mode: 10.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| H2-C01 | conversation |  | **FAIL** | turn 1: message should match '0\\.7\\s*m' | `tr_187f95219c3c` #11 |
| H2-C02 | conversation |  | **FAIL** | turn 1: message should match '29\\.\\d\\s*(in|inch)' | `tr_1a31fa600c6f` #11 |
| H2-C04 | conversation |  | **FAIL** | turn 1: kind: expected ANSWER, got UNSUPPORTED; turn 1: message should match '(?i)alumin|wood|ply' | `tr_03145d5df463` #11 |
| H2-X02 | challenge |  | **FAIL** | turn 1: should start with an apology (Sorry) | `tr_12c976e6db99` #11 |
| H2-V01 | voice |  | **FAIL** | turn 0: message should match '10 days'; turn 0: voice: robot wording matched "(?i)i'?d rather not guess" | `tr_e6a46e9aa9f8` #6 |
| H2-V04 | voice |  | **FAIL** | turn 0: voice: robot wording matched "(?i)i'?d rather not guess"; turn 0: should start with an apology (Sorry) | `tr_761f53dcea58` #6 |
| H2-P02 | policy |  | **FAIL** | turn 0: message should match "(?i)no returns|can't be returned|cannot be returned" | `tr_446dbdf3395a` #6 |
| H2-P03 | policy |  | **FAIL** | turn 0: message should match '\\b5\\b' | `tr_e3475c336608` #6 |
| H2-N03 | not_policy |  | pass |  |  |
| H2-F02 | trick |  | **FAIL** | turn 0: message should match "(?i)can't help with that" | `tr_9122ef8fc35b` #4 |
| H2-F03 | frustration |  | **FAIL** | turn 0: message should match '(?i)size|material|deliver|care' | `tr_1e3801287aa8` #6 |
| H2-B01 | fit |  | **FAIL** | turn 0: kind: expected CLARIFY, got ANSWER; turn 0: message should match '(?i)space' | `tr_c598f7b6cd50` #6 |
| H2-B02 | fit |  | **FAIL** | turn 1: message should match '(?i)\\bfits?\\b|will fit' | `tr_9dd6deb13305` #11 |
| H2-B03 | browse |  | **FAIL** | turn 0: message should not contain 'sofa'; turn 0: message should match '(?i)mug' | `tr_c532ac587779` #5 |
| H2-B04 | closest |  | **FAIL** | turn 0: message should not contain 'these are the closest'; turn 0: message should match '(?i)only home temple' | `tr_e4f012a0f1c3` #8 |
