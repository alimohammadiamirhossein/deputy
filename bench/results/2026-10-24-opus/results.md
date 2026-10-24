# Benchmark results

Model: Claude Opus 5.5 (`--model opus`), Claude Code 2.1.308, Deputy 0.2.0 with DeepSeek V4.1 Flash on DeepInfra, thinking `high`. One run per task and config (n=1), 2026-10-24.

rename_refactor was re-run after its hidden test was fixed: the first version also flagged a test that calls the deprecated alias on purpose, which failed two otherwise correct runs.

| Task | Config | Hidden tests | Claude | Deputy | Total | Time | Deputy calls |
|---|---|---|---|---|---|---|---|
| booking_ranges | claude | pass (10 passed in 0.21s) | $0.1589 | $0.0000 | $0.1589 | 25 s | - |
| booking_ranges | review | pass (10 passed in 0.21s) | $0.2306 | $0.0130 | $0.2436 | 269 s | review 1 |
| booking_ranges | delegate | pass (10 passed in 0.19s) | $0.1676 | $0.0015 | $0.1691 | 59 s | delegate 1 |
| expense_report | claude | pass (7 passed in 0.47s) | $0.1788 | $0.0000 | $0.1788 | 30 s | - |
| expense_report | review | pass (7 passed in 0.59s) | $0.3557 | $0.0321 | $0.3878 | 1456 s | review 1 |
| expense_report | delegate | pass (7 passed in 0.24s) | $0.2033 | $0.0022 | $0.2055 | 107 s | delegate 1 |
| rate_limiter | claude | pass (10 passed in 0.32s) | $0.1758 | $0.0000 | $0.1758 | 34 s | - |
| rate_limiter | review | pass (10 passed in 0.26s) | $0.3183 | $0.0043 | $0.3226 | 176 s | review 1 |
| rate_limiter | delegate | pass (10 passed in 0.25s) | $0.1910 | $0.0010 | $0.1920 | 92 s | delegate 1 |
| rename_refactor | claude | pass (5 passed in 0.22s) | $0.2199 | $0.0000 | $0.2199 | 29 s | - |
| rename_refactor | review | pass (5 passed in 0.21s) | $0.2761 | $0.0030 | $0.2791 | 95 s | review 1 |
| rename_refactor | delegate | pass (5 passed in 0.19s) | $0.1932 | $0.0011 | $0.1943 | 50 s | delegate 1 |

| Config | Runs | Pass rate | Mean total cost | Mean time |
|---|---|---|---|---|
| claude | 4 | 4/4 | $0.1833 | 30 s |
| review | 4 | 4/4 | $0.3083 | 499 s |
| delegate | 4 | 4/4 | $0.1902 | 77 s |
