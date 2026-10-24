# Changelog

All notable changes to Deputy. The format follows [Keep a Changelog](https://keepachangelog.com/),
and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Grok (xAI) as a provider.** `DEPUTY_PROVIDER=xai` (or `grok`) with `XAI_API_KEY` uses
  `grok-4.3` by default; `grok-build-0.1` and `grok-4.7` are priced too. Deputy sends
  `max_completion_tokens`, maps thinking levels to xAI's (and leaves them out for models with
  fixed reasoning), and adds an `x-grok-conv-id` header per run for prompt caching.
  `deputy setup cursor|codex --provider xai` writes a config that forwards only `XAI_API_KEY`.
  Tested against xAI's documentation, not yet with a live key.
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

[0.2.0]: https://github.com/alimohammadiamirhossein/deputy/compare/2347242...v0.2.0
[0.1.0]: https://github.com/alimohammadiamirhossein/deputy/commit/2347242
