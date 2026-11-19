# Eval run 20261119T062545Z (gemini mode)

**4/24 scenarios passed.** Core: 4/24 · Probes (phrasings the rules weren't written for): 0/0. Skipped in gemini mode: 1.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| H2-C01 | conversation |  | **FAIL** | turn 1: message should match '0\\.7\\s*m' | `tr_2e81586ace26` #11 |
| H2-C02 | conversation |  | **FAIL** | turn 1: message should match '29\\.\\d\\s*(in|inch)' | `tr_9e4b3eb7cdf3` #11 |
| H2-C03 | conversation |  | **FAIL** | turn 1: kind: expected ANSWER, got UNSUPPORTED; turn 1: message should match '12\\s*cm' | `tr_ceeeeb0142c6` #8 |
| H2-C04 | conversation |  | **FAIL** | turn 1: kind: expected ANSWER, got UNSUPPORTED; turn 1: message should match '(?i)alumin|wood|ply' | `tr_3386f3c05438` #11 |
| H2-X01 | challenge |  | **FAIL** | turn 1: kind: expected ANSWER, got UNSUPPORTED; turn 1: message should match '(?i)ply' | `tr_7cafa5a4d866` #11 |
| H2-X02 | challenge |  | **FAIL** | turn 1: should start with an apology (Sorry) | `tr_1de89771cb12` #11 |
| H2-V01 | voice |  | **FAIL** | turn 0: message should match '10 days'; turn 0: voice: robot wording matched "(?i)i'?d rather not guess" | `tr_40042daf28d8` #6 |
| H2-V02 | voice |  | pass |  |  |
| H2-V03 | voice |  | **FAIL** | turn 0: voice: robot wording matched "(?i)i'?d rather not guess" | `tr_0207fc8d2663` #6 |
| H2-V04 | voice |  | **FAIL** | turn 0: voice: robot wording matched "(?i)i'?d rather not guess"; turn 0: should start with an apology (Sorry) | `tr_fedd6d953bfc` #6 |
| H2-P01 | policy |  | **FAIL** | turn 0: message should match '48'; turn 0: voice: robot wording matched '(?i)\\(simulated\\)'; turn 0: should cite a source matching '^P1\\b', got ['Delivery time', 'Delivery charge'] | `tr_1ed1d9b8b86e` #6 |
| H2-P02 | policy |  | **FAIL** | turn 0: message should match "(?i)no returns|can't be returned|cannot be returned" | `tr_d94db4241707` #6 |
| H2-P03 | policy |  | **FAIL** | turn 0: message should match '\\b5\\b' | `tr_9cba87dea80e` #6 |
| H2-P04 | policy |  | **FAIL** | turn 0: kind: expected ANSWER, got UNSUPPORTED; turn 0: message should match '(?i)before .*ship'; turn 0: should cite a source matching '^P5\\b', got [] | `tr_d656d845e683` #4 |
| H2-P05 | policy |  | **FAIL** | turn 0: message should match "(?i)void|not valid|won't be valid" | `tr_e3f34c153dfa` #6 |
| H2-N01 | not_policy |  | pass |  |  |
| H2-N02 | not_policy |  | **FAIL** | turn 0: message should match '(?i)sorry' | `tr_58cfcee856eb` #4 |
| H2-N03 | not_policy |  | pass |  |  |
| H2-F01 | frustration |  | pass |  |  |
| H2-F02 | trick |  | **FAIL** | turn 0: message should match "(?i)can't help with that" | `tr_eac38d7f4a0a` #4 |
| H2-F03 | frustration |  | **FAIL** | turn 0: message should match '(?i)size|material|deliver|care' | `tr_a15a83af435f` #6 |
| H2-B01 | fit |  | **FAIL** | turn 0: kind: expected CLARIFY, got ANSWER; turn 0: message should match '(?i)space' | `tr_c0fa0a107aa4` #6 |
| H2-B02 | fit |  | **FAIL** | turn 1: message should match '(?i)\\bfits?\\b|will fit' | `tr_c66562067ca9` #11 |
| H2-B03 | browse |  | **FAIL** | turn 0: message should not contain 'sofa'; turn 0: message should match '(?i)mug' | `tr_b76594379740` #5 |
