# Changelog

All notable changes to Deputy. The format follows [Keep a Changelog](https://keepachangelog.com/),
and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- **Cancelling a call stops the run.** Before, pressing Esc left the run going, and a cancelled
  `delegate` released its lock while it kept editing files, so a second `delegate` could edit
  the same files at the same time. Runs now stop before their next model turn or tool call, and
  `delegate` takes a new task only after the old one has really stopped.
- **`project_dir` works with the Claude Code plugin.** The plugin pinned the workspace with
  `DEPUTY_WORKSPACE`, so Deputy ignored `project_dir` and MCP roots. It now passes the project
  folder as `CLAUDE_PROJECT_DIR`, which `project_dir` can override. Deputy also refuses to work
  inside Claude Code's plugin folder.

### Added

- Progress notifications during long calls: each turn and tool call (for example "bugs: turn 2,
  read_file"), so clients that show progress can tell a slow call from a stuck one.

## [0.3.0] - 2026-10-25

### Added

- **Grok (xAI) as a provider.** `DEPUTY_PROVIDER=xai` (or `grok`) with `XAI_API_KEY` uses
  `grok-4.3` by default; `grok-build-0.1` and `grok-4.7` are priced too. Deputy sends
  `max_completion_tokens`, maps thinking levels to xAI's (and leaves them out for models with
  fixed reasoning), and adds an `x-grok-conv-id` header per run for prompt caching.
  `deputy setup cursor|codex --provider xai` writes a config that forwards only `XAI_API_KEY`.
  **Experimental and not tested with a real xAI key yet**; feedback is welcome in an issue.
- **Two new modes.** `lean` spends as few Claude tokens as possible with little loss of
  accuracy: Deputy does the reading (`investigate`) and well-specified work big enough to pay
  off, and Claude writes small and tricky changes itself. `partner` hands Deputy every
  low-level job, even small ones, and asks it for ideas through `consult`; Claude treats its
  output as a draft and checks every diff and idea. Pick them in the plugin settings or with
  `DEPUTY_MODE`.
- **Review benchmark.** `bench/review_eval.py` runs Deputy's `review` without Claude on planted
  bugs and on clean diffs. Each planted bug has a clean twin, the same change done right. It
  reports the catch rate, the false-alarm rate on clean diffs (at any severity and at major or
  higher), and how often two lenses agree. `--check` proves each planted bug is real before any
  API call. Results are in `bench/results/2026-10-24-review` and
  `bench/results/2026-10-24-review-after-fix`, and in the README.
- A demo GIF at the top of the README, replaying one benchmark review (`docs/demo/make_gif.py`).
- `bench/run.py`: `review` and `delegate` configs, a Windows cleanup fix, and the first Opus results
  in `bench/results/2026-10-24-opus`.

### Changed

- **Reviews are much faster.** In the review benchmark the median review took 28 s on a change
  with a bug (was 45 s) and 80 s on a clean change (was 160 s), and the slowest took 230 s (was
  23 minutes). Every planted bug was still caught; false alarms stayed within run-to-run noise.
  Two changes do this:
  - `review` and `consult` think at `low` by default (`DEPUTY_LENS_THINKING`). The worker
    (`delegate`, `investigate`) keeps `DEPUTY_THINKING`, `high` by default. Claude can pass
    `thinking="high"` for an especially risky change.
  - Each lens is capped. It stops after `DEPUTY_LENS_TIMEOUT` seconds (default 180) or
    `DEPUTY_LENS_MAX_OUTPUT_TOKENS` output tokens, thinking included (default 32,000), then writes
    up what it already checked in one short call without tools and with light thinking. Its
    section says it stopped early and ends with `NOT CHECKED:`; a reviewer reports only problems
    it confirmed and lists open suspicions there.
- **Claude calls `review` and `consult` less often.** Every mode, the playbooks and the skill
  descriptions now say to review only risky or large changes (tricky logic, security or untrusted
  input, data, concurrency, money, many files) and to consult only when unsure between
  approaches. Before, accuracy mode asked for both on every non-trivial task, and each call makes
  the user wait, often a minute or more.

### Fixed

- A provider's own key variable is now only sent to that provider's host. Before, a custom
  `DEPUTY_BASE_URL` could receive `DEEPINFRA_API_KEY`; such endpoints now need `DEPUTY_API_KEY`.
  `XAI_*` variables are also hidden from shell commands Deputy runs.
- The MCP `initialize` handshake now reports Deputy's version instead of the MCP SDK's
  ([#4](https://github.com/alimohammadiamirhossein/deputy/pull/4), fixes
  [#1](https://github.com/alimohammadiamirhossein/deputy/issues/1)).
- `review` now shows new files the way `git diff` shows an added file. The old "(untracked)" label
  made reviewers report that a new file would be left out of the change (6 of 72 findings on clean
  diffs in the review benchmark, and none after the fix).

## [0.2.0] - 2026-10-24

### Added

- **Accuracy mode, now the default.** Claude writes all code itself and uses the cheap model only
  as extra eyes. Delegation happens only on request, or in the new `balanced` and `savings` modes.
  Set it with the plugin option or `DEPUTY_MODE`.
- **`review` tool.** Independent reviewers, one per lens, check the uncommitted git diff (or a
  given `base`, `paths` or `diff`) with an adversarial prompt. Findings ask for impact, a repro and
  a fix.
- **`consult` `my_view`.** Records Claude's conclusion before it sees the helper's ideas; it is
  never sent to the model.
- `/deputy:review` skill, a mode-aware delegate skill, the `SKILL.md` playbook and
  `docs/REFERENCE.md`.
- PyPI package [`deputy-cc`](https://pypi.org/project/deputy-cc/): run `uvx deputy-cc serve` in
  any MCP client.
- Official MCP Registry entry (`io.github.alimohammadiamirhossein/deputy`), `llms.txt`, and a
  benchmark harness in `bench/`.
- **Savings estimate.** Each result ends with a rough "this work would cost $X on your lead model;
  Deputy did it for $Y" line. The new `stats` tool and `deputy stats` command show totals for the
  session, today, the last 7 days and all time; reviews and second opinions are listed as extra
  checks, never as savings. Set the lead model with `DEPUTY_LEAD_MODEL` or the plugin option. The
  log stores numbers only.
- **Cursor and Codex support.** `deputy setup cursor` and `deputy setup codex` add Deputy to the
  editor's MCP config (with a backup) and install the playbook as a Cursor rule or Codex skill;
  Codex gets a 30-minute tool timeout. Copy-paste files are in `integrations/`.
- **Workspace detection for any client.** Deputy asks the client for its project folder (MCP
  roots), and every tool accepts `project_dir`, so it works when an editor starts it outside the
  project.

### Changed

- Server instructions now depend on the mode.
- Prompts include today's date, and APIs the model doesn't know are marked `[unverified]`.
- Shorter README with measured costs and a "when to use, and when not to" section.

## [0.1.0] - 2026-10-23

### Added

- First release: an MCP server and Claude Code plugin that runs DeepSeek V4.1 Flash on DeepInfra
  (thinking `high`) as a helper.
- `delegate` (coding sub-agent with its own tool loop), `investigate` (read-only search),
  `consult` (parallel second opinions) and `status`.
- Workspace jail, read-only tool sets, secret-free shell environment, and limits on turns, tokens
  and time.
- `deputy doctor` to check the key, the endpoint and that thinking is on.

[0.3.0]: https://github.com/alimohammadiamirhossein/deputy/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/alimohammadiamirhossein/deputy/compare/2347242...v0.2.0
[0.1.0]: https://github.com/alimohammadiamirhossein/deputy/commit/2347242
