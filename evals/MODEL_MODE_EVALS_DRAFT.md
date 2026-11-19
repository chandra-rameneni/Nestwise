# Model-mode evals draft: O-59 and O-60 (for PM approval)

These run only when the AI is on (mode "M"). Rules mode already gets both right.

| ID | Page | Shopper says | Pass if the reply… | Fail if the reply… |
|---|---|---|---|---|
| MM-01 (O-59) | Bed page | "is it waterproof?" | says it doesn't have that detail (may add the care tip) | says "not waterproof" or "waterproof" as a fact |
| MM-02 (O-59, held out) | Bean bag page | "is it fireproof?" | says it doesn't have that detail | gives a yes or no the listing doesn't state |
| MM-03 (O-60) | Listing | "do you sell mobiles?" | says we don't sell mobiles, and names what we do sell | gives store info like "We have 2,043 products" |
| MM-04 (O-60, held out) | Listing | "do you have laptops?" | says we don't sell laptops | gives store info, or shows furniture as if it were laptops |
| MM-05 (guard) | Listing | "do you sell sofas?" | shows sofas | says we don't sell sofas |

MM-02 and MM-04 are held out: I won't look at them while fixing, so they show whether the fix works on new wording.
MM-05 makes sure the O-60 fix doesn't break real product questions.
