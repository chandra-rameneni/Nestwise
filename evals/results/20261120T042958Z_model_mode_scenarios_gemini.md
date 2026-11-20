# Eval run 20261120T042958Z (gemini mode)

**5/5 scenarios passed.** Core: 5/5 · Probes (phrasings the rules weren't written for): 0/0. Who answered: 3 messages read by the AI, 0 fell back to the rules; 1 of 2 answers written by the AI.

## Score by model

| Answered by | Scenarios | Passed | Score |
|---|---|---|---|
| gemini-3.5-flash | 3 | 3 | 100% |
| rules only | 1 | 1 | 100% |
| gemini-2.5-flash | 1 | 1 | 100% |

"mixed" means the free quota ran out mid-scenario and another model took over. "rules only" means no AI answered in that scenario.

| Scenario | Group | Probe | Answered by | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|---|
| MM-01 | no_guess |  | rules only | pass |  |  |
| MM-02 | no_guess |  | gemini-2.5-flash | pass |  |  |
| MM-03 | not_sold |  | gemini-3.5-flash | pass |  |  |
| MM-04 | not_sold |  | gemini-3.5-flash | pass |  |  |
| MM-05 | guard |  | gemini-3.5-flash | pass |  |  |
