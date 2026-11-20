# Eval run 20261120T044036Z (gemini mode)

**42/43 scenarios passed.** Core: 42/43 · Probes (phrasings the rules weren't written for): 0/0. Skipped in gemini mode: 5. Who answered: 13 messages read by the AI, 6 fell back to the rules; 23 of 29 answers written by the AI.

**NOT A VALID AI-MODE RUN:** only 13 of 19 message readings came from the AI (needs 80%). Most answers came from the rules, so this measures the rules, not the AI.

## Score by model

| Answered by | Scenarios | Passed | Score |
|---|---|---|---|
| nvidia/nemotron-3.5-super-vl:free | 28 | 27 | 96% |
| rules only | 15 | 15 | 100% |

"mixed" means the free quota ran out mid-scenario and another model took over. "rules only" means no AI answered in that scenario.

| Scenario | Group | Probe | Answered by | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|---|
| R2-C01 | conversation |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-C02 | conversation |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-C03 | conversation |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-C04 | conversation |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-C05 | conversation |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-C06 | conversation |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-C07 | conversation |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-C08 | conversation |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-X01 | challenge |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-X02 | challenge |  | rules only | pass |  |  |
| R2-X03 | challenge |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-X04 | challenge |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-V01 | voice |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-V02 | voice |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-V03 | voice |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-V04 | voice |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-V05 | voice |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-V06 | voice |  | rules only | pass |  |  |
| R2-V08 | voice |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-P01 | policy |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-P02 | policy |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-P03 | policy |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-P04 | policy |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-P05 | policy |  | rules only | pass |  |  |
| R2-P06 | policy |  | rules only | pass |  |  |
| R2-P07 | policy |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-P08 | policy |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-N01 | not_policy |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-N02 | not_policy |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-N03 | not_policy |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-N04 | not_policy |  | nvidia/nemotron-3.5-super-vl:free | **FAIL** | turn 0: message should match '(?i)sorry' | `tr_d75854bd80d2` #4 |
| R2-N05 | not_policy |  | nvidia/nemotron-3.5-super-vl:free | pass |  |  |
| R2-N06 | not_policy |  | rules only | pass |  |  |
| R2-F01 | frustration |  | rules only | pass |  |  |
| R2-F02 | frustration |  | rules only | pass |  |  |
| R2-F03 | frustration |  | rules only | pass |  |  |
| R2-F04 | trick |  | rules only | pass |  |  |
| R2-F05 | trick |  | rules only | pass |  |  |
| R2-F06 | frustration |  | rules only | pass |  |  |
| R2-B01 | fit |  | rules only | pass |  |  |
| R2-B02 | fit |  | rules only | pass |  |  |
| R2-B03 | fit |  | rules only | pass |  |  |
| R2-B04 | browse |  | rules only | pass |  |  |
