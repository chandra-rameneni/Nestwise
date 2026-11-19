# Eval run 20261119T103344Z (gemini mode)

**21/24 scenarios passed.** Core: 21/24 · Probes (phrasings the rules weren't written for): 0/0. Skipped in gemini mode: 1. Who answered: 0 messages read by the AI, 9 fell back to the rules; 2 of 16 answers written by the AI.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| H2-C01 | conversation |  | pass |  |  |
| H2-C02 | conversation |  | pass |  |  |
| H2-C03 | conversation |  | **FAIL** | turn 1: kind: expected ANSWER, got UNSUPPORTED; turn 1: message should match '12\\s*cm' | `tr_d0530604e850` #8 |
| H2-C04 | conversation |  | pass |  |  |
| H2-X01 | challenge |  | pass |  |  |
| H2-X02 | challenge |  | pass |  |  |
| H2-V01 | voice |  | **FAIL** | turn 0: message should match '10 days' | `tr_fe6884375f34` #7 |
| H2-V02 | voice |  | pass |  |  |
| H2-V03 | voice |  | pass |  |  |
| H2-V04 | voice |  | pass |  |  |
| H2-P01 | policy |  | pass |  |  |
| H2-P02 | policy |  | pass |  |  |
| H2-P03 | policy |  | pass |  |  |
| H2-P04 | policy |  | pass |  |  |
| H2-P05 | policy |  | pass |  |  |
| H2-N01 | not_policy |  | pass |  |  |
| H2-N02 | not_policy |  | **FAIL** | turn 0: message should match '(?i)sorry' | `tr_022351a7ccba` #5 |
| H2-N03 | not_policy |  | pass |  |  |
| H2-F01 | frustration |  | pass |  |  |
| H2-F02 | trick |  | pass |  |  |
| H2-F03 | frustration |  | pass |  |  |
| H2-B01 | fit |  | pass |  |  |
| H2-B02 | fit |  | pass |  |  |
| H2-B03 | browse |  | pass |  |  |
