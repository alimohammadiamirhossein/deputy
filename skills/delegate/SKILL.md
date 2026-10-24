---
name: delegate
description: Hand a coding task to the Deputy sub-agent (DeepSeek V4.1 Flash), which edits files and runs commands itself, then verify its work. Use when the user says "deputy do X", "delegate", or "/deputy:delegate". In accuracy mode, only when the user explicitly asks.
argument-hint: "<task>"
---

# Delegate to Deputy

Current Deputy mode: **${user_config.mode}** (if this shows a placeholder, call the `status` tool).

- **accuracy:** write the code yourself. Delegate only because the user asked for it.
- **lean:** delegate well-specified work big enough to pay off (multi-file or repetitive edits,
  tests, boilerplate); write changes of a few lines yourself.
- **balanced:** delegate only low-risk mechanical work (boilerplate, renames, formatting, test
  scaffolding, repetitive edits). Keep logic and tricky code yourself.
- **partner:** delegate every low-level job, even small ones; keep design and judgment calls
  yourself, and read every diff Deputy produces.
- **savings:** delegate well-specified coding work; keep design and risky changes yourself.

## Writing the brief

Put in `task`: the goal, the files or folders in scope, constraints (what not to touch), and how
to verify (a test or build command). Put in `context` facts Deputy cannot discover: decisions
already made, error messages, project conventions. Never include secrets.

## After Deputy finishes

Deputy's "done" is a claim, not proof. Read every changed file it lists, check `git diff`, and run
the tests. Fix small problems yourself. If the result is poor twice in a row, stop delegating and
do the work yourself.

## If the user typed a task after the command

Delegate this task now, following the steps above: $ARGUMENTS
