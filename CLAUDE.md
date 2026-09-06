# TechScope — Claude Instructions

TechScope is a production-quality **CLI technographic scanner**: given a text file of domains it
fetches each homepage over plain HTTP, extracts signals from several channels, matches them against
a Wappalyzer-format fingerprint set, and writes `{ "domain": [technologies] }` as JSON.
It is a take-home assignment; the full brief is in `assigment/assigment.md` — read it before any
work. That folder is gitignored on purpose (the brief is not ours to publish); if it is missing,
stop and ask the user for it instead of guessing the requirements.

## Hard constraints (from the assignment — violations fail the submission)

- **HTTP only.** No headless browser (Playwright, Selenium, Puppeteer). JS globals are found by
  static analysis of script text, never by executing it.
- **No paid external API.** Only direct HTTP to the target domain and DNS lookups.
- **≥ 4 signal channels** from: HTTP headers, `<script src>`, cookie names, DNS (MX/TXT/CNAME on
  the apex), `<meta>` tags, `window.*` globals (static). We implement all six.
- **20 domains in < 60 s** on a laptop. Concurrency is mandatory; the budget is enforced in e2e.
- **Accuracy over recall.** Report a technology only on strong evidence. A false positive is worse
  than a miss.
- **Never crash on a bad domain.** Blocks, timeouts, DNS failures are logged and the domain still
  appears in the output (with an empty list).
- **Wappalyzer pattern format**, extensible to the full ~7,500-entry database with no code
  changes. Matching logic is ours — the Wappalyzer library is not a dependency.
- **Deliverables:** public GitHub repo, `README.md` (install, run, architecture decisions),
  `output.json` for the 20 test domains in `docs/domains.txt`.

## Tech stack

Python 3.13 · `uv` (env, lock, run) · `httpx` async client · `dnspython` · `pytest` + `respx` ·
`ruff` (lint + format) · `mypy --strict` · Docker (multi-stage image on the official `uv`
base, non-root, targets `cli` and `api`). `src/` layout, package `techscope`, console script
`techscope`. If `uv` is missing: `brew install uv`.

Two drivers share one core: the **CLI** (the graded deliverable, backlog 1–9) and, after the
submission is done, an **HTTP API** (`fastapi` in the optional `api` extra, backlog 11) with a
**Next.js web app** in `web/` (backlog 12). The web app only ever talks to the API.
Backlog 10 is the security pass that has to land between the submission and the API.

Verification entry points (feature 1 creates them):

```bash
make check         # ruff check + ruff format --check + mypy --strict + pytest (offline tests only)
make e2e           # live scan of docs/domains.txt → output.json, timed
make docker-build  # build the image techscope:local (target cli)
make docker-scan   # same scan as e2e, but inside the container (bind-mounts the repo at /data)
docker compose up  # (after backlog 12) api on :8000 + web app on :3000
```

`uv run <cmd>` for anything else. Never `pip install` into the system interpreter.

## Architecture — lightweight Clean / Hexagonal (binding)

Full rules and the package layout: `.claude/rules/architecture.md`. Build toward that layout;
don't invent alternatives. The essentials:

```
presentation/cli.py ──┐
presentation/api/  ───┴► application/use_cases ─► domain (Signal, Fingerprint, matcher)
                              │  depends on          ▲
                              ▼                      │ implements
                       application/ports ◄── infrastructure (http, dns, extractors, json repo, writer)
                       bootstrap.py = composition root, the only module that wires adapters
```

- **Domain is pure.** `domain/` has no I/O, no clock, no `httpx`/`dns`/`argparse`. It owns
  `Signal`, `Fingerprint`, `Detection`, and `match_signals`. Exhaustively unit-tested.
- **One abstraction: `Signal(channel, value, key)`.** Every collector — HTTP, DNS, anything added
  later — emits the same record. The matcher never knows the source.
- **Ports are small `Protocol`s** in `application/ports`: `SignalCollector`,
  `FingerprintRepository`, `ScanReportWriter`. Use cases depend only on them.
- **Adapters live in `infrastructure/`** and are the only code importing `httpx` and `dns`.
  `HttpSignalCollector` fetches once and runs the pure extractors; `DnsSignalCollector` queries
  the apex.
- **Fingerprints are data.** `infrastructure/repositories/data/technologies.json` in the real
  Wappalyzer shape. Adding 7,000 more must require zero Python changes.
- **Wiring happens once** in `bootstrap.py`. Nothing else constructs an adapter.
- `tests/unit/test_architecture.py` fails the build on any import that crosses a layer boundary
  the wrong way.

## Definition of done (every feature, every PR)

1. Tests written first (superpowers:test-driven-development), all passing offline.
2. `make check` is green — zero ruff findings, zero mypy errors, architecture test passing.
3. `reviewer` agent returns **PASS** (or WARNINGS you have addressed or consciously deferred in
   the PR body). CRITICAL never ships.
4. **Security holds.** Untrusted input stays bounded and inert: every fetch checks its target on
   every redirect hop, every regex compiled from data is checked for catastrophic backtracking,
   every read is capped in decoded bytes, and anything quoted from a page into our output is
   length-capped and stripped of control characters. The `reviewer` agent's security lens is the
   gate; a hole is a CRITICAL, never a style note.
5. `/e2e` run recorded: runtime, blocked domains, and `output.json` diff explained in the PR body
   (skipped only while the CLI does not exist yet — features 1–3).
6. `README.md` and `docs/backlog.md` updated in the same PR.
7. One feature, one branch, one PR. Nothing else rides along.

## How work is organised

- The feature list is `docs/backlog.md`. Work is done **in order** unless the user says otherwise.
- `/ship-next` runs the full cycle for the next feature and stops with an open PR. The user merges
  on GitHub; the next run starts from the updated `main`. Details: `.claude/commands/ship-next.md`.
- `/review` and `/e2e` are the standalone review and live-run steps.
- Design spec: `docs/superpowers/specs/2026-09-05-techscope-design.md`. Amend it when a decision
  changes; don't let it drift.
- Conventions live in `.claude/rules/` — architecture, python-style, testing, git-workflow,
  network-etiquette, and typescript-style (for `web/` only, on top of the
  `vspathonis-code-style` skill). `python-style.md` is the user's personal house style (the
  `vspathonis-code-style` skill) translated to Python: `decide_*` / `is_*` / `check_*_or_raise`
  naming, guard clauses then a flat happy path, no inline conditionals in returns, named boolean
  intermediates, one registry per enum-keyed variant, `None` over coerced empties, blank lines
  around blocks. Read it before writing any Python.
- Reply language: the user writes and reads Greek in chat; code, comments, commits, PRs, README
  and docs stay in English.

## Git identity — this is a PERSONAL repo

This machine has several GitHub identities. TechScope belongs to the **personal** one:

- GitHub user `baggelisp`, remote `https://github.com/baggelisp/TechScope.git`.
- Commit author: `Vangelis Spathonis <baggelisp.kef@hotmail.com>` (already set in local config).
- `gh` must be logged in as `baggelisp` for PR commands to work. Check with `gh auth status`;
  if the active account is not `baggelisp`, **stop and tell the user** — do not create PRs from
  the work account. Switch with `gh auth switch --user baggelisp` once that login exists.
- SSH alias for the personal key is `github.com-personal` (see `~/.ssh/config`) if the remote is
  ever moved to SSH.
