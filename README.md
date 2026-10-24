<div align="center">

<!-- mcp-name: io.github.alimohammadiamirhossein/deputy -->

<img src="https://raw.githubusercontent.com/alimohammadiamirhossein/deputy/main/.claude-plugin/icon.png" alt="Deputy sheriff badge logo" width="128" height="128">

# Deputy

### Deputize cheap models. Claude stays the sheriff.

**Deputy is a Claude Code plugin and MCP server that has a cheap model, DeepSeek V4.1 Flash, review
Claude's code for bugs and give second opinions, for under a cent each. Claude keeps writing the
code.**

[![GitHub stars](https://img.shields.io/github/stars/alimohammadiamirhossein/deputy?style=social)](https://github.com/alimohammadiamirhossein/deputy/stargazers)
[![CI](https://github.com/alimohammadiamirhossein/deputy/actions/workflows/ci.yml/badge.svg)](https://github.com/alimohammadiamirhossein/deputy/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/deputy-cc.svg)](https://pypi.org/project/deputy-cc/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/alimohammadiamirhossein/deputy/blob/main/LICENSE)
[![MCP](https://img.shields.io/badge/protocol-MCP-purple.svg)](https://modelcontextprotocol.io/)

<img src="https://raw.githubusercontent.com/alimohammadiamirhossein/deputy/main/docs/demo/review.gif" alt="Deputy reviews an uncommitted change in Claude Code: two cheap reviewers flag an off-by-one bug for a tenth of a cent, and Claude confirms it with the repro before fixing it" width="820">

<sub>A replay of one benchmark case. Deputy's findings, time and cost, the repro and the test run are real.</sub>

</div>

```bash
claude plugin marketplace add alimohammadiamirhossein/deputy
claude plugin install deputy@deputy
```

Inside Claude Code the same thing is `/plugin marketplace add alimohammadiamirhossein/deputy`.
You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and a
[DeepInfra API key](#quick-start).

## What it costs (measured)

| Run | Time | Cost |
|---|---|---|
| `review`: two reviewers check a change with a planted off-by-one bug (both caught it) | 27 s | **$0.0011** |
| `consult`: second opinions from 2 angles | 68 s | **$0.0018** |
| `investigate`: list a project's functions and their tests | 18 s | **$0.0004** |
| `delegate`: fix a bug, add 3 tests, run pytest until green | 46 s | **$0.0006** |

Measured on a small demo project with thinking `high`. On real projects, expect `consult` and
`review` to stay under $0.01. Every result shows its real tokens and cost.

## Benchmark: Opus with and without Deputy

Four small Python tasks with hidden tests Claude never sees ([bench/](https://github.com/alimohammadiamirhossein/deputy/tree/main/bench)),
one run each on Claude Opus 5.5, October 2026:

| Config | Hidden tests passed | Mean cost (Claude + Deputy) | Median time |
|---|---|---|---|
| Opus alone | 4/4 | $0.18 | 30 s |
| Opus + `/deputy:review` | 4/4 | $0.31 ($0.30 + $0.013) | 3.7 min |
| Opus + `/deputy:delegate` | 4/4 | $0.19 ($0.19 + $0.0015) | 76 s |

What this shows, and what it doesn't:

- **No accuracy gain to measure here.** The tasks are too easy: Opus passed every hidden test on
  its own.
- **Reviews cost Claude more than they cost Deputy.** Deputy's share is about a cent, but Claude
  spends more checking the findings, so a reviewed task cost 68% more and took longer. One review
  took 24 minutes because a reviewer thought for 73k tokens.
- **The findings still changed the code.** In 3 of 4 tasks Claude hardened the code beyond the
  spec: it fixed a rate limiter that a NaN timestamp would block forever, and added missing tests.
  It rejected one finding that contradicted the spec.
- **Delegating saved nothing on tasks this small.** Claude's own reading and checking cost about as
  much as writing the code itself.
- **Small sample.** One run per config. Full table:
  [bench/results/2026-10-24-opus](https://github.com/alimohammadiamirhossein/deputy/blob/main/bench/results/2026-10-24-opus/results.md).

### Does `review` catch bugs, and how often does it cry wolf?

Deputy's `review` on its own, without Claude, on 6 changes with a planted bug and 8 clean changes.
Each planted bug has a clean twin, the same change done right. Five runs each
([bench/review_cases](https://github.com/alimohammadiamirhossein/deputy/tree/main/bench/review_cases)):

| Diffs | Reviews | Flagged | Flagged major or critical | Mean cost | Mean time |
|---|---|---|---|---|---|
| Planted bug | 30 | **30/30 caught** | 30/30 | $0.0022 | 55 s |
| Clean | 39 | 23/39 | 7/39 | $0.0067 | 4 min |

- **Every planted bug was caught,** at major or critical severity, by both reviewers every time.
- **Clean code still draws findings,** so Claude has to check each one. Most are minor (50 of
  61), and 18% of clean reviews included a major claim.
- **Many of those findings are fair,** such as a test that can't fail, an entry point no test
  covers, or a cache key wider than the change assumed (5 of the 7 major claims).
- **The benchmark already fixed one cause of false alarms.** In the first run, reviewers read new
  files labelled "(untracked)" as left out of the change. Deputy now shows them as `git diff`
  does. Those findings went from 6 to 0, and clean reviews with a major claim from 11/39 to 7/39
  (part of that drop is run-to-run noise).
- **Agreement is weak evidence on clean code.** Both reviewers flagged the same spot on 26% of
  clean diffs, so a finding isn't real just because two reviewers report it.
- Every finding on a clean diff is listed in the results:
  [latest run](https://github.com/alimohammadiamirhossein/deputy/blob/main/bench/results/2026-10-24-review-after-fix/results.md),
  [first run](https://github.com/alimohammadiamirhossein/deputy/blob/main/bench/results/2026-10-24-review/results.md).

## What it does

Claude (for example Opus 5.5) stays in charge and **writes the code**. Deputy adds four tools that
run a much cheaper model as a helper inside your project:

| Tool | What it does |
|---|---|
| **`review`** | Independent reviewers hunt for bugs in Claude's change before it calls the task done |
| **`consult`** | Second opinions from 2–4 angles at once, before Claude commits to a plan |
| **`investigate`** | Reads lots of code and returns `file:line` leads |
| **`delegate`** | Hands a coding task to the cheap model (off by default; on request, or in savings mode) |
| **`stats`** | Shows roughly how many tokens and dollars Deputy saved: this session, today, this week, all time |

Claude treats everything Deputy says as an **unverified hint**: it checks each finding against
the code and keeps only what holds up.

### See what you saved

Every result ends with a one-line estimate, for example from a real `investigate` run:

```text
Savings (rough): this work would cost about $0.0082 on Claude Opus 5.5; Deputy did it for $0.0001. Saved about $0.0074 and 2.0k Claude Opus 5.5 tokens.
```

Ask Claude for `stats`, or run `deputy stats`, for totals. Reviews and second opinions are listed
separately as extra checks, so they never inflate the savings. The estimate assumes your lead
model would use about as many tokens, so treat it as an order of magnitude. Only numbers are
stored, never code or prompts. Set your lead model with `DEPUTY_LEAD_MODEL` (`opus`, `sonnet`,
`haiku`, `fable` or `custom`).

## When to use Deputy, and when not to

**Use it for:**

- Non-trivial changes where a missed bug costs more than a cent: logic, edge cases, refactors that
  touch several files.
- A second opinion before Claude commits to a design, without spending Claude tokens on it.
- Wide reading in a big codebase, such as "where is this setting read?".
- Well-specified mechanical work (boilerplate, renames, test scaffolding) in `lean`, `balanced`,
  `partner` or `savings` mode, when you want to save Claude tokens on larger jobs. On small tasks it saved
  nothing in the [benchmark](#benchmark-opus-with-and-without-deputy).

**Skip it for:**

- Trivial edits like typos and one-liners. A review takes a few minutes and adds little there.
- Code you may not share with a third party. Deputy sends code to DeepInfra, or to whatever
  endpoint you set in `DEPUTY_BASE_URL` (a local model works too).
- Final answers. Findings come from a weaker model and include false positives, which is why
  Claude verifies every one.
- Architecture and security-sensitive decisions in `savings` mode. Keep those with Claude.

## Quick start

**1. Get a DeepInfra API key** (DeepInfra hosts DeepSeek's models in the US)

1. Sign up at **[deepinfra.com](https://deepinfra.com/)** with GitHub, Google or email.
2. In **Dashboard → Billing**, add a card and **$5–10** of credit, then set a **spending limit**
   equal to that amount.
3. In **API Keys**, create a key (it starts with `sk-di-`) and copy it. Keep it private.

You don't need a plan, a model purchase or a dedicated GPU. Pay-as-you-go credit is enough.

**2. Install** [uv](https://docs.astral.sh/uv/getting-started/installation/) and the plugin

```bash
claude plugin marketplace add alimohammadiamirhossein/deputy
claude plugin install deputy@deputy
```

Claude Code asks for your DeepInfra key and stores it in your system's secure storage.

**3. Restart Claude Code and try it**

```text
/deputy:review
/deputy:consult I plan to cache sessions in Redis. What am I missing?
/deputy:investigate how does a request reach the database?
```

Or just work normally: Claude consults and reviews on its own for non-trivial tasks.

### Cursor and Codex

One command adds Deputy to the editor's MCP config (with a backup of the old file) and installs
the playbook as a Cursor rule or Codex skill:

```bash
uvx --from git+https://github.com/alimohammadiamirhossein/deputy deputy setup cursor --project .
uvx --from git+https://github.com/alimohammadiamirhossein/deputy deputy setup codex
```

Set `DEEPINFRA_API_KEY` in your environment first, then restart the editor. Add `--dry-run` to
see the changes without writing them. Ready-made files are in
[integrations/](https://github.com/alimohammadiamirhossein/deputy/tree/main/integrations).

**Grok instead of DeepSeek (experimental, not tested yet):** Grok support follows xAI's
documentation but has not been run with a real xAI key. If you try it, please
[tell us what worked and what didn't](https://github.com/alimohammadiamirhossein/deputy/issues/new?title=Grok%20feedback%3A%20), even if it was just a one-word "works".
Add `--provider xai` and set `XAI_API_KEY` (from console.x.ai)
instead. Deputy then uses `grok-4.3`; set `DEPUTY_MODEL` to `grok-build-0.1` (xAI's coding model)
or `grok-4.7` (its strongest). Grok costs about 10 times more per token than DeepSeek V4.1
Flash.

```bash
uvx --from git+https://github.com/alimohammadiamirhossein/deputy deputy setup cursor --project . --provider xai
```

### Other MCP clients (Cline, Windsurf, Claude Desktop)

Deputy is on PyPI as [`deputy-cc`](https://pypi.org/project/deputy-cc/). Add a stdio MCP server
that runs:

```bash
uvx deputy-cc serve
```

with `DEEPINFRA_API_KEY` set in its environment. Check your setup with `uvx deputy-cc doctor`.

## Recommended model: DeepSeek V4.1 Flash, thinking `high`

The default is `deepseek-ai/DeepSeek-V4.1-Flash-1017` on DeepInfra with thinking set to `high`.
It's the best price-to-quality option we found for this job:

- **Cheap:** $0.098 per 1M input tokens and $0.294 per 1M output tokens (October 2026), cheaper
  than DeepSeek's own API.
- **Capable:** about 1M tokens of context and reliable tool calling.
- **Thinking actually on:** DeepInfra leaves its thinking **off** unless asked. Deputy always asks
  (`high`), which we confirmed by measuring the reasoning tokens.
- **Private:** DeepInfra says it doesn't train on your data. Your code isn't sent to DeepSeek's
  own servers.

## Modes

| Mode | Who writes the code | Pick it when |
|---|---|---|
| **accuracy** (default) | Claude, always | You want the best result |
| **lean** | Claude for small and tricky changes; Deputy reads code and takes larger well-specified work | You want to spend as few Claude tokens as possible with little loss of accuracy |
| **balanced** | Claude; Deputy takes boilerplate | You want some savings without risk |
| **partner** | Deputy does all low-level work; Claude checks every diff | You want Deputy doing the legwork and pitching ideas, with Claude verifying |
| **savings** | Deputy, Claude verifies | You want to save the most tokens |

Change it in the plugin settings (`/plugin`) or with `DEPUTY_MODE`.

## Learn more

- **[SKILL.md](https://github.com/alimohammadiamirhossein/deputy/blob/main/SKILL.md)**: the
  playbook Claude follows (consult → decide → implement → review → check each finding). Also works
  without the plugin.
- **[docs/REFERENCE.md](https://github.com/alimohammadiamirhossein/deputy/blob/main/docs/REFERENCE.md)**:
  all settings, costs, safety, terms of service, the research behind the design, troubleshooting
  and the roadmap.
- **[CHANGELOG.md](https://github.com/alimohammadiamirhossein/deputy/blob/main/CHANGELOG.md)**:
  what changed in each release.

Deputy stays within Anthropic's rules: Claude Code runs unmodified, and Deputy never touches your
Claude login. It's an ordinary MCP tool using your own DeepInfra key.

## Support the project

If Deputy caught a bug for you, **[give it a ⭐](https://github.com/alimohammadiamirhossein/deputy/stargazers)**
and share it with someone who uses Claude Code. Issues and pull requests are welcome; the
[good first issues](https://github.com/alimohammadiamirhossein/deputy/labels/good%20first%20issue)
are a good place to start.

[![Star History Chart](https://api.star-history.com/svg?repos=alimohammadiamirhossein/deputy&type=Date)](https://star-history.com/#alimohammadiamirhossein/deputy&Date)

---

[MIT](https://github.com/alimohammadiamirhossein/deputy/blob/main/LICENSE) © 2026 Amirhossein
Alimohammadi · Not affiliated with Anthropic, DeepSeek or DeepInfra.

<sub>Keywords: Claude Code plugin, MCP server, Model Context Protocol, AI code review, second
opinion, DeepSeek V4.1 Flash, DeepInfra, subagent, Opus, agentic coding, reduce Claude Code cost.</sub>
