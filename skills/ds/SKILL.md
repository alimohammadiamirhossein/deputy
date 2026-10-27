---
name: ds
description: Hand every task in this session to Deputy (DeepSeek by default), in any mode, until the user says "/deputy:ds off". Deputy reads, writes and tests the code; you only write the brief, check the result and report. Use when the user types "/deputy:ds" or asks to let DeepSeek or Deputy do the work.
argument-hint: "[task | on | off]"
---

# Let Deputy do the whole task

The user wants Deputy to do the work, not you. This is their explicit request, so it applies in
every mode, accuracy included. Your job is to brief, check and report, not to write the code.

**This stays on for the rest of the session.** Handle every later coding task in this
conversation the same way, without the user typing the command again, until they say
`/deputy:ds off` or ask you to stop using Deputy. When it is switched off, go back to the mode's
normal rules and say so in one line. When it is switched on without a task, say in one line that
Deputy will now handle the tasks in this session, and wait for the first one.

1. **Brief, don't read.** Do not open or edit files yourself first. Turn the request into a brief
   for `delegate`: the goal, the files or folders in scope, constraints (what not to touch), and a
   command that verifies the result (tests or a build). Put facts Deputy cannot discover, such as
   decisions already made or error messages, in `context`. Never include secrets. If the request
   is too unclear to brief, ask the user one short question instead of guessing.
2. **Let Deputy find things.** If you need to know where something is before you can write the
   brief, ask `investigate` instead of reading files yourself.
3. **Delegate.** Call `delegate` with the brief. Split a large task into 2-4 self-contained steps
   and delegate them one after another.
4. **Check cheaply.** Run the verify command and look at `git diff --stat`. Read the diff only
   where it is risky: deleted code, security, data handling, files outside the scope.
5. **Send fixes back.** If a check fails, call `delegate` again with the failing output and what
   must change. Do not fix it yourself. After two failed attempts, stop and tell the user what is
   still wrong, and offer to finish it yourself.
6. **Report** in a few lines: what Deputy changed, whether the checks pass, anything you could not
   verify, and Deputy's cost from its result.

Skip `review` and `consult` here unless the change is risky. They use the same cheap model that
just wrote the code, and the user asked for speed.

## What the user typed after the command

$ARGUMENTS

If this is empty or "on", switch on and wait for a task. If it is "off", switch off. Otherwise it
is the first task: start on it now.
