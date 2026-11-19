# Eval run 20261119T064248Z (gemini mode)

**39/43 scenarios passed.** Core: 39/43 · Probes (phrasings the rules weren't written for): 0/0. Skipped in gemini mode: 5.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| R2-C01 | conversation |  | pass |  |  |
| R2-C02 | conversation |  | pass |  |  |
| R2-C03 | conversation |  | pass |  |  |
| R2-C04 | conversation |  | pass |  |  |
| R2-C05 | conversation |  | pass |  |  |
| R2-C06 | conversation |  | pass |  |  |
| R2-C07 | conversation |  | pass |  |  |
| R2-C08 | conversation |  | pass |  |  |
| R2-X01 | challenge |  | **FAIL** | turn 1: message should match '(?i)ply' | `tr_501e6540ced6` #13 |
| R2-X02 | challenge |  | pass |  |  |
| R2-X03 | challenge |  | pass |  |  |
| R2-X04 | challenge |  | pass |  |  |
| R2-V01 | voice |  | **FAIL** | turn 0: voice: robot wording matched '(?i)with mattress:'; turn 0: should start with an apology (Sorry) | `tr_cc482e4e5014` #6 |
| R2-V02 | voice |  | pass |  |  |
| R2-V03 | voice |  | pass |  |  |
| R2-V04 | voice |  | **FAIL** | turn 0: message should match '(?i)kids' | `tr_d90cb148e31d` #6 |
| R2-V05 | voice |  | pass |  |  |
| R2-V06 | voice |  | pass |  |  |
| R2-V08 | voice |  | pass |  |  |
| R2-P01 | policy |  | pass |  |  |
| R2-P02 | policy |  | **FAIL** | turn 0: message should match '(?i)repair|replace' | `tr_2857c2371991` #6 |
| R2-P03 | policy |  | pass |  |  |
| R2-P04 | policy |  | pass |  |  |
| R2-P05 | policy |  | pass |  |  |
| R2-P06 | policy |  | pass |  |  |
| R2-P07 | policy |  | pass |  |  |
| R2-P08 | policy |  | pass |  |  |
| R2-N01 | not_policy |  | pass |  |  |
| R2-N02 | not_policy |  | pass |  |  |
| R2-N03 | not_policy |  | pass |  |  |
| R2-N04 | not_policy |  | pass |  |  |
| R2-N05 | not_policy |  | pass |  |  |
| R2-N06 | not_policy |  | pass |  |  |
| R2-F01 | frustration |  | pass |  |  |
| R2-F02 | frustration |  | pass |  |  |
| R2-F03 | frustration |  | pass |  |  |
| R2-F04 | trick |  | pass |  |  |
| R2-F05 | trick |  | pass |  |  |
| R2-F06 | frustration |  | pass |  |  |
| R2-B01 | fit |  | pass |  |  |
| R2-B02 | fit |  | pass |  |  |
| R2-B03 | fit |  | pass |  |  |
| R2-B04 | browse |  | pass |  |  |
