# Eval run 20261120T134412Z (rules mode)

Payment keys: off for this run (checkout is mock).

**14/15 scenarios passed.** Core: 14/15 · Probes (phrasings the rules weren't written for): 0/0. Skipped in rules mode: 10.

| Scenario | Group | Probe | Answered by | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|---|
| H2-C01 | conversation |  | rules only | pass |  |  |
| H2-C02 | conversation |  | rules only | pass |  |  |
| H2-C04 | conversation |  | rules only | pass |  |  |
| H2-X02 | challenge |  | rules only | pass |  |  |
| H2-V01 | voice |  | rules only | **FAIL** | turn 0: message should match '10 days' | `tr_7644b99f40f7` #7 |
| H2-V04 | voice |  | rules only | pass |  |  |
| H2-P02 | policy |  | rules only | pass |  |  |
| H2-P03 | policy |  | rules only | pass |  |  |
| H2-N03 | not_policy |  | rules only | pass |  |  |
| H2-F02 | trick |  | rules only | pass |  |  |
| H2-F03 | frustration |  | rules only | pass |  |  |
| H2-B01 | fit |  | rules only | pass |  |  |
| H2-B02 | fit |  | rules only | pass |  |  |
| H2-B03 | browse |  | rules only | pass |  |  |
| H2-B04 | closest |  | rules only | pass |  |  |
