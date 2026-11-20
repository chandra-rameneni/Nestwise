# Eval run 20261120T035121Z (rules mode)

**37/39 scenarios passed.** Core: 28/30 · Probes (phrasings the rules weren't written for): 9/9.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| NA-01 | not_sold |  | pass |  |  |
| NA-02 | not_sold |  | pass |  |  |
| NA-03 | not_sold |  | pass |  |  |
| NA-04 | not_sold |  | pass |  |  |
| NA-05 | not_sold | yes | pass |  |  |
| GR-01 | greeting |  | pass |  |  |
| GR-02 | greeting |  | pass |  |  |
| GR-03 | greeting | yes | pass |  |  |
| CL-01 | clarify |  | pass |  |  |
| CL-02 | clarify |  | pass |  |  |
| CL-03 | clarify | yes | pass |  |  |
| LS-01 | listing |  | pass |  |  |
| LS-02 | listing |  | pass |  |  |
| LS-03 | listing |  | pass |  |  |
| LS-04 | listing |  | pass |  |  |
| LS-05 | listing | yes | pass |  |  |
| LS-06 | listing | yes | pass |  |  |
| LS-07 | listing |  | pass |  |  |
| PQ-01 | product_qa |  | pass |  |  |
| PQ-02 | product_qa |  | pass |  |  |
| PQ-03 | product_qa |  | pass |  |  |
| PQ-04 | product_qa |  | pass |  |  |
| PQ-05 | product_qa |  | pass |  |  |
| PQ-06 | product_qa |  | pass |  |  |
| PQ-07 | product_qa |  | pass |  |  |
| PQ-08 | product_qa |  | pass |  |  |
| PQ-09 | product_qa |  | pass |  |  |
| PQ-10 | product_qa |  | pass |  |  |
| BT-01 | buy_this |  | **FAIL** | turn 2: kind: expected ORDER_PLACED, got BLOCKED; turn 3: kind: expected ORDER_PLACED, got BLOCKED; turn None: orders: expected 1, got 0 | `tr_3ce991c8acba` #13 |
| BT-02 | buy_this |  | pass |  |  |
| BT-03 | buy_this |  | pass |  |  |
| BT-04 | buy_this | yes | pass |  |  |
| BT-05 | buy_this | yes | pass |  |  |
| BT-06 | buy_this | yes | pass |  |  |
| BT-07 | buy_this |  | **FAIL** | turn 3: reason codes should include PRICE_CHANGED_SINCE_APPROVAL, got ['PAYMENT_REQUIRED'] | `tr_564fd2e86ea8` #14 |
| SIM-01 | similar |  | pass |  |  |
| SIM-02 | similar | yes | pass |  |  |
| DF-01 | deferred |  | pass |  |  |
| DF-02 | deferred |  | pass |  |  |
