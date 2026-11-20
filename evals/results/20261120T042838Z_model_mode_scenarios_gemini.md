# Eval run 20261120T042838Z (gemini mode)

**5/5 scenarios passed.** Core: 5/5 · Probes (phrasings the rules weren't written for): 0/0. Who answered: 2 messages read by the AI, 1 fell back to the rules; 1 of 2 answers written by the AI.

**NOT A VALID AI-MODE RUN:** only 2 of 3 message readings came from the AI (needs 80%). Most answers came from the rules, so this measures the rules, not the AI.

## Score by model

| Answered by | Scenarios | Passed | Score |
|---|---|---|---|
| rules only | 2 | 2 | 100% |
| gemini-2.5-flash | 2 | 2 | 100% |
| nvidia/nemotron-3.5-super-vl | 1 | 1 | 100% |

"mixed" means the free quota ran out mid-scenario and another model took over. "rules only" means no AI answered in that scenario.

| Scenario | Group | Probe | Answered by | Result | What failed | Trace (first failing event) |
|---|---|---|---|---|---|---|
| MM-01 | no_guess |  | rules only | pass |  |  |
| MM-02 | no_guess |  | gemini-2.5-flash | pass |  |  |
| MM-03 | not_sold |  | gemini-2.5-flash | pass |  |  |
| MM-04 | not_sold |  | rules only | pass |  |  |
| MM-05 | guard |  | nvidia/nemotron-3.5-super-vl | pass |  |  |
