# Eval run 20261120T035125Z (rules mode)

**12/14 scenarios passed.** Core: 12/14 · Probes (phrasings the rules weren't written for): 0/0.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| P3-W01 | wording |  | pass |  |  |
| P3-W02 | wording |  | pass |  |  |
| P3-W03 | wording |  | pass |  |  |
| P3-W04 | wording |  | pass |  |  |
| P3-W05 | wording |  | pass |  |  |
| P3-W06 | wording |  | pass |  |  |
| P3-W07 | wording |  | **FAIL** | turn 3: kind: expected ORDER_PLACED, got BLOCKED; turn 3: message should contain 'Done'; turn 3: message should contain 'no payment' | `tr_3cb864f706a4` #71 |
| P3-W08 | wording |  | pass |  |  |
| P3-W09 | wording |  | pass |  |  |
| P3-W10 | wording |  | pass |  |  |
| P3-W11 | wording |  | pass |  |  |
| P3-W12 | wording |  | pass |  |  |
| P3-W13 | wording |  | **FAIL** | turn 3: message should contain 'Heads up'; turn 3: message should contain "haven't ordered"; turn 3: message should match '₹15,400'; turn 3: message should match '₹14,900' | `tr_42e157a18c59` #14 |
| P3-W14 | wording |  | pass |  |  |
