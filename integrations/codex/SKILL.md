---
name: deputy
description: Use the Deputy MCP tools for second opinions before decisions (consult), bug reviews of your changes (review) and wide code searches (investigate). Do not use for trivial edits.
---

You can call Deputy, an MCP server that runs a cheaper model (DeepSeek V4.1 Flash) as
a helper in this project. You are the lead: you plan, decide, write the important code and verify.
Deputy's output is never proof; check it against the code before relying on it.

Tools:
- `consult`: second opinions from 2-3 independent `lenses` when you are unsure between
  approaches. Write your own conclusion first and pass it as `my_view` (Deputy does not see it).
- `review`: independent reviewers hunt for bugs in your uncommitted change (git diff). Call it
  only before you finish a risky or large change (tricky logic, security, data, concurrency,
  many files), not for routine changes whose tests pass. Verify every finding; fix only what
  you confirm.
- `investigate`: read-only search across many files; returns file:line leads to check yourself.
- `delegate`: Deputy edits files and runs commands itself. Use it only when the user explicitly asks; otherwise write the code yourself.
- `stats`: rough tokens and money saved. `status`: settings and the workspace Deputy uses.

If `status` shows the wrong workspace, pass `project_dir` with the project's absolute path.
Never put secrets in tool arguments: they are sent to the model provider.
Change your plan only when Deputy's argument survives your own check, not because it disagrees.
