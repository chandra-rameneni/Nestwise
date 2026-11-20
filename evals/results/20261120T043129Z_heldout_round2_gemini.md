# Eval run 20261120T043129Z (gemini mode)

**22/24 scenarios passed.** Core: 22/24 · Probes (phrasings the rules weren't written for): 0/0. Skipped in gemini mode: 1. Who answered: 9 messages read by the AI, 0 fell back to the rules; 13 of 16 answers written by the AI.

## Score by model

| Answered by | Scenarios | Passed | Score |
|---|---|---|---|
| nvidia/nemotron-3.5-super-vl:free | 10 | 10 | 100% |
| gemini-3.5-flash | 8 | 7 | 88% |
| rules only | 6 | 5 | 83% |

"mixed" means the free quota ran out mid-scenario and another model took over. "rules only" means no AI answered in that scenario.

| Scenario | Group | Probe | Answered by | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|---|
| H2-C01 | conversation |  | gemini-3.5-flash | pass |  |  |
| H2-C02 | conversation |  | gemini-3.5-flash | pass |  |  |
| H2-C03 | conversation |  | gemini-3.5-flash | **FAIL** | turn 1: kind: expected ANSWER, got CLARIFY; turn 1: message should match '12\\s*cm' | `tr_f5efadd1007a` #8 |
| H2-C04 | conversation |  | gemini-3.5-flash | pass |  |  |
| H2-X01 | challenge |  | gemini-3.5-flash | pass |  |  |
| H2-X02 | challenge |  | gemini-3.5-flash | pass |  |  |
| H2-V01 | voice |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| H2-V02 | voice |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| H2-V03 | voice |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| H2-V04 | voice |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| H2-P01 | policy |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| H2-P02 | policy |  | rules only | pass |  |  |
| H2-P03 | policy |  | rules only | pass |  |  |
| H2-P04 | policy |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| H2-P05 | policy |  | gemini-3.5-flash | pass |  |  |
| H2-N01 | not_policy |  | gemini-3.5-flash | pass |  |  |
| H2-N02 | not_policy |  | rules only | **FAIL** | turn 0: message should match '(?i)sorry' | `tr_f7a554fed053` #5 |
| H2-N03 | not_policy |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| H2-F01 | frustration |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| H2-F02 | trick |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| H2-F03 | frustration |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| H2-B01 | fit |  | rules only | pass |  |  |
| H2-B02 | fit |  | rules only | pass |  |  |
| H2-B03 | browse |  | rules only | pass |  |  |
