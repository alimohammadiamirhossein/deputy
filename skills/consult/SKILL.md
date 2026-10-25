---
name: consult
description: Get diverse second opinions from Deputy (DeepSeek V4.1 Flash) with ideas, risks and alternatives, then make the final call yourself. Use when unsure between approaches on a non-trivial decision, when stuck on a recurring problem, or when the user says "consult" or "/deputy:consult".
argument-hint: "<question or plan>"
---

# Consult Deputy

A different model thinks differently from you, so it can surface ideas and risks you missed. It is
also weaker than you. Use it for breadth, then apply your own judgment.

1. **Ask a sharp question** and include your current plan, so Deputy can challenge it.
2. **Use 2-3 lenses** for independent passes in parallel, for example "simplest approach",
   "edge cases and failure modes", "performance", "security", "what could break existing behavior".
3. **Give context** Deputy cannot discover: constraints, and what you ruled out and why.
4. **Weigh answers below your own analysis.** Check each idea against the code before adopting
   it. Discard generic or wrong ones. Do not switch plans just because Deputy disagrees; switch
   only if its argument holds up when you check it.

## If the user typed a question after the command

Consult Deputy on this now: $ARGUMENTS
