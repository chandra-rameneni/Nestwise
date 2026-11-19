# Eval run 20261119T065225Z (gemini mode)

**20/24 scenarios passed.** Core: 20/24 · Probes (phrasings the rules weren't written for): 0/0. Skipped in gemini mode: 1.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| H2-C01 | conversation |  | pass |  |  |
| H2-C02 | conversation |  | pass |  |  |
| H2-C03 | conversation |  | **FAIL** | turn 1: kind: expected ANSWER, got UNSUPPORTED; turn 1: message should match '12\\s*cm' | `tr_e5490aa20805` #8 |
| H2-C04 | conversation |  | pass |  |  |
| H2-X01 | challenge |  | **FAIL** | turn 1: message should match '(?i)ply' | `tr_0d00c33a9dc9` #13 |
| H2-X02 | challenge |  | pass |  |  |
| H2-V01 | voice |  | **FAIL** | turn 0: message should match '10 days' | `tr_b2a4f9c52a5a` #6 |
| H2-V02 | voice |  | pass |  |  |
| H2-V03 | voice |  | pass |  |  |
| H2-V04 | voice |  | pass |  |  |
| H2-P01 | policy |  | pass |  |  |
| H2-P02 | policy |  | pass |  |  |
| H2-P03 | policy |  | pass |  |  |
| H2-P04 | policy |  | pass |  |  |
| H2-P05 | policy |  | pass |  |  |
| H2-N01 | not_policy |  | pass |  |  |
| H2-N02 | not_policy |  | **FAIL** | turn 0: message should match '(?i)sorry' | `tr_3dd10a827b62` #5 |
| H2-N03 | not_policy |  | pass |  |  |
| H2-F01 | frustration |  | pass |  |  |
| H2-F02 | trick |  | pass |  |  |
| H2-F03 | frustration |  | pass |  |  |
| H2-B01 | fit |  | pass |  |  |
| H2-B02 | fit |  | pass |  |  |
| H2-B03 | browse |  | pass |  |  |
