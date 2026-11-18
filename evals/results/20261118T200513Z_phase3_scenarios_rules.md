# Eval run 20261118T200513Z (rules mode)

**2/14 scenarios passed.** Core: 2/14 · Probes (phrasings the rules weren't written for): 0/0.

| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|
| P3-W01 | wording |  | **FAIL** | turn 0: message should not contain 'I left out'; turn 0: message should not match '\\[[A-Z0-9]{16}\\]'; turn 0: message should not match '\\(s\\)'; turn 0: message should match '^(Good news|Sure|Here)' | `tr_ce3cbf49de24` #61 |
| P3-W02 | wording |  | **FAIL** | turn 0: message should not contain '1 seats'; turn 0: message should match '\\d+ sofas' | `tr_44cbc881fe59` #61 |
| P3-W03 | wording |  | **FAIL** | turn 0: message should contain 'Sorry'; turn 0: message should contain 'mobiles' | `tr_5d060c7a9f3b` #5 |
| P3-W04 | wording |  | pass |  |  |
| P3-W05 | wording |  | **FAIL** | turn 1: message should contain 'Nothing is ordered without your approval'; turn 1: message should not match '\\[[A-Z0-9]{16}\\]' | `tr_41cd9bd311e8` #67 |
| P3-W06 | wording |  | **FAIL** | turn 2: message should not contain 'mock order' | `tr_6a74e02710da` #70 |
| P3-W07 | wording |  | **FAIL** | turn 3: message should contain 'Done'; turn 3: message should not match 'MOCK-[0-9A-F]+' | `tr_e4049aed400e` #74 |
| P3-W08 | wording |  | **FAIL** | turn 2: message should contain 'nothing was ordered'; turn 2: message should contain 'change your mind' | `tr_ce1110ed3a18` #69 |
| P3-W09 | wording |  | **FAIL** | turn 1: reply should be shorter than turn 0 | `tr_eb107bd8fe02` #7 |
| P3-W10 | wording |  | **FAIL** | turn 0: message should contain 'Happy to help'; turn 0: message should contain 'dining set' | `tr_3034e0e002d1` #5 |
| P3-W11 | wording |  | **FAIL** | turn 0: message should contain 'Sorry'; turn 0: reply should have at most 2 sentences | `tr_4d9c602da7d7` #4 |
| P3-W12 | wording |  | pass |  |  |
| P3-W13 | wording |  | **FAIL** | turn 3: message should contain 'Heads up'; turn 3: message should contain "haven't ordered"; turn 3: message should not match '\\b[A-Z]{3,}_[A-Z_]{3,}\\b' | `tr_e94311fb1d9c` #22 |
| P3-W14 | wording |  | **FAIL** | turn 1: message should contain 'out of stock'; turn 1: message should not match '\\b[A-Z]{3,}_[A-Z_]{3,}\\b' | `tr_f5af7f43ffde` #15 |
