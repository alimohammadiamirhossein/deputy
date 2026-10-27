---
name: deputy
description: Playbook for working with Deputy, a cheaper helper model (DeepSeek V4.1 Flash) exposed as MCP tools (consult, review, investigate, delegate). Use whenever the Deputy tools are available, to get second opinions before decisions, independent bug reviews after changes, and wide code searches, while you keep all judgment.
---

# Working with Deputy

You are the lead. Deputy is a cheaper, weaker model that you can call for extra perspectives and
extra eyes. Use it to be **more accurate**, never to skip your own judgment.

> Using the Claude Code plugin? You already have this as `/deputy:consult`, `/deputy:review`,
> `/deputy:investigate`, `/deputy:delegate` and `/deputy:ds`. Without the plugin, copy this file to
> `~/.claude/skills/deputy/SKILL.md`. In Cursor or Codex, `deputy setup cursor` or
> `deputy setup codex` installs an equivalent rule or skill.

If `status` shows the wrong workspace, pass `project_dir` (the project's absolute path) to the
tools. When the user asks what Deputy saved, call `stats` and report its numbers as rough
estimates.

## The mode decides who writes code

Call `status` once to see the mode.

| Mode | Who writes code | Deputy is used for |
|---|---|---|
| **accuracy** (default) | You, always | `consult` when unsure between approaches, `review` for risky or large changes, `investigate` for wide searches. `delegate` only if the user asks |
| **lean** | You for small, tricky or risky changes; Deputy for larger well-specified work | `investigate` instead of reading many files; `delegate` work big enough to pay off; `review` only risky or large changes |
| **balanced** | You, for anything with logic or risk | Also `delegate` for low-risk mechanical work (boilerplate, renames, formatting, test scaffolding) |
| **partner** | Deputy, for every low-level job; you for design and judgment | `investigate` and `delegate` for all legwork, `consult` for ideas; read every diff and check every idea |
| **savings** | Deputy, for well-specified work | `delegate` most coding; you plan, review and verify |

## The accuracy loop

1. **Understand** the task yourself. Read the code that matters.
2. **Consult** when you are unsure between approaches. Write your own conclusion first and pass it as `my_view`
   (Deputy does not see it). Ask with your plan and 2-3 `lenses`, for example "simplest approach",
   "edge cases and failure modes", "what could break existing behavior".
3. **Decide** yourself. Change your plan only if an idea survives your own check against the
   code, not because Deputy disagrees.
4. **Implement** the change yourself.
5. **Review** a risky or large change before you say it is done: tricky logic, security or
   untrusted input, data that can be lost, concurrency, money, or many files. Call `review` with
   `focus` = what the change should do. It reviews your uncommitted git diff with independent
   reviewers.
6. **Adjudicate** every finding: accept, dismiss with a reason, or defer. Run a finding's `REPRO`
   when it has one. Findings raised by more than one lens are more likely real. Fix what you
   confirm; tell the user briefly what you dismissed and why.

Skip steps 2 and 5 for routine changes whose tests pass. Each call makes the user wait, often a
minute or more.

## Using each tool well

- **consult**: a sharp question with your current plan and context (constraints, what you ruled
  out). Lenses run in parallel and do not see each other.
- **review**: by default reviews uncommitted changes against HEAD. Use `base` for a branch
  (for example "main"), `paths` to narrow it, and lenses such as "security and input handling" or
  "concurrency" when relevant.
- **investigate**: for questions that need wide reading. Treat answers as leads and read the cited
  lines yourself before acting.
- **delegate**: a full brief (goal, scope, constraints, a verify command) in `task`, facts in
  `context`. Then read every changed file, check `git diff` and run the tests. After two poor
  results, stop delegating.

## Rules

- Deputy's output is never proof. Verify against the code before relying on it.
- Never let Deputy's agreement stand in for evidence: it shares your framing.
- Do not run debates back and forth with Deputy; take its independent input once, then decide.
- Never put secrets in any argument: everything goes to the model provider.
- If the user says "do it yourself", do not use Deputy for that task.
