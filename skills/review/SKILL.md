---
name: review
description: Have Deputy's cheap reviewers hunt for bugs in your uncommitted change (git diff), then verify each finding yourself. Use before finishing a risky or large change (tricky logic, security or untrusted input, data handling, concurrency, money, many files), or when the user says "review" or "/deputy:review". Skip it for routine changes whose tests pass.
argument-hint: "[what the change should do]"
---

# Review with Deputy

A second set of eyes catches mistakes the author misses. Deputy runs independent reviewers in
parallel, one per lens, over your change. They are cheaper and weaker than you, so their findings
are hints, not verdicts.

1. Call `review` with `focus` set to what the change is meant to do. By default it reviews
   uncommitted changes against HEAD; pass `base` (for example "main") for a whole branch, or
   `paths` to narrow it down.
2. Optionally choose `lenses`. The default is correctness plus edge cases and missing tests. Add
   "security and input handling" or "concurrency" when relevant.
3. **Verify every finding yourself** by reading the code it points to. Expect some false positives.
4. Fix only what you confirm. Tell the user briefly which findings you fixed and which you
   rejected, and why.

## If the user typed something after the command

Review the current change now, with this as the focus: $ARGUMENTS
