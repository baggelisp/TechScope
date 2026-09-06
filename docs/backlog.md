# TechScope Backlog

Ordered feature list. `/ship-next` takes the first `[ ]` item, ships it as one PR, marks it `[~]`
with the PR number, and marks it `[x]` on the next run once the PR is merged. Do not reorder
without updating the spec. Paths follow `.claude/rules/architecture.md`.

Status: `[ ]` todo · `[~]` in PR · `[x]` merged

---

## [x] 1. Project scaffold, quality gate, CLI skeleton, Docker image — PR #1
**Goal:** a runnable, fully-linted, fully-typed, containerised empty project so every later PR is
small and the architecture boundary is enforced from day one.
**Acceptance:**
- `uv` project, Python 3.13 pinned (`.python-version`), `pyproject.toml` with `src/` layout,
  package `techscope`, console script `techscope`, deps `httpx` + `dnspython`, dev deps
  `pytest pytest-asyncio respx ruff mypy`, `uv.lock` committed.
- Layer packages created with `__init__.py`: `domain`, `application/ports`,
  `application/use_cases`, `infrastructure/{http,extractors,dns,collectors,repositories,writers}`,
  `presentation`, plus `bootstrap.py` and `__main__.py`.
- `domain/domain_name.py` (`decide_domain_or_none`), `domain/domain_list.py`
  (`build_domain_list`), `domain/models.py` with `ScanReport` / `DomainScanResult` only. The
  enums, `errors.py` and `decide_apex_domain` move to the features that consume them (2, 4, 6):
  writing them here would ship untested code with no caller.
- `application/ports/scan_report_writer.py` + `infrastructure/writers/json_report_writer.py`.
- `presentation/cli.py`: `techscope scan <file> -o <out>` parses the domain file (strip, skip
  blanks/comments, dedupe, lowercase, strip scheme/`www.`/path/port) and writes
  `{ "<domain>": [] }` for each domain in input order via `bootstrap.run_scan(options)`.
  `--log-level` flag; logging to stderr; `--concurrency` and `--timeout` accepted (unused until
  feature 8). Exit codes: 0 ok, 2 usage, 1 unexpected.
- `tests/unit/test_architecture.py`: walks `src/techscope` with `ast`, asserts the import table in
  `architecture.md`; part of `make check`.
- `Makefile`: `check`, `fmt`, `test`, `e2e`, `docker-build`, `docker-scan`.
- `Dockerfile` (multi-stage, target `cli`, per spec §7), `.dockerignore` (excludes `.venv`,
  `.git`, `tests`, `docs`, `web`), `compose.yaml` with a `scan` service under profile `cli`
  (`api`/`web` services arrive with items 10–11). `make docker-build && make docker-scan`
  produces the same `output.json` as the local run.
- `README.md` with install, run (local + Docker); `.gitignore` completed.
- Tests: domain-file parsing cases, `decide_domain_or_none` / `build_domain_list`, the JSON
  writer, CLI exit codes, and the architecture rule (including negative cases proving the
  checker rejects a forbidden import).
**E2E:** n/a.

## [x] 2. Fingerprint model and Wappalyzer-format repository — PR #2
**Goal:** fingerprints are data in the real Wappalyzer shape; the 24 assignment patterns load.
**Acceptance:**
- `domain/enums.py`: `ChannelEnum` (moved from feature 1 — this is its first consumer).
- `domain/errors.py`: `TechScopeError` base and `FingerprintLoadError` (moved from feature 1).
- `domain/models.py`: `Pattern` (channel, compiled value regex with `re.I`, optional compiled
  key regex, `confidence` 0–100 default 100, optional `version` template, `source` text),
  `Fingerprint` (name, patterns, `implies`, `categories`), `FingerprintIndex`
  (patterns grouped by `ChannelEnum`, built by `domain/matcher.build_fingerprint_index`).
- `application/ports/fingerprint_repository.py`: `FingerprintRepository.load()`.
- `infrastructure/repositories/wappalyzer_pattern.py`: parses `regex\;confidence:N\;version:X`,
  accepts string or list values; `infrastructure/repositories/json_fingerprint_repository.py`
  maps Wappalyzer keys to `ChannelEnum` through one registry, raises `FingerprintLoadError`
  naming the technology on an invalid regex.
- `infrastructure/repositories/data/technologies.json` containing exactly the assignment's 24
  fingerprints (mapping per spec §3 — `gtag\(` under `scripts`, the rest of `[script]` under
  `scriptSrc`; header/cookie names are regex keys per spec §4).
- Loads the full Wappalyzer DB shape without code changes (tested with a synthetic 500-entry
  file for load time < 1 s).
**E2E:** n/a.

## [x] 3. Pure matcher core — PR #3
**Goal:** `Signals × FingerprintIndex → Detections`, exhaustively tested, no I/O.
**Acceptance:**
- `domain/models.py`: `Signal(channel, value, key=None)`, `Evidence(channel, key,
  pattern_source, matched_text)`, `Detection(name, confidence, evidence)`.
- `domain/matcher.match_signals(signals, index) -> tuple[Detection, ...]`: per-channel lookup,
  key regex + value regex semantics per spec §4 — the key is matched with `re.match` and the
  value with `re.search`; using `re.search` on the key reports F5 BigIP on every WordPress site,
  so a test must pin that case. Confidence = max over matched patterns,
  threshold 50, `implies` at the implier's confidence, sorted by name, no duplicates.
- Positive + near-miss negative test per assignment fingerprint; header-key case
  insensitivity; `X-Stripe-.*` key regex; `^intercom-` cookie name; `js` patterns match
  `JS_GLOBAL` names; `scripts` patterns match `SCRIPT_INLINE` bodies.
**E2E:** n/a.

## [x] 4. HTTP fetcher with redirect, timeout, and soft-block handling — PR #4
**Goal:** one polite, bounded, non-crashing homepage fetch per domain.
**Acceptance:** `domain/enums.py` gains `BlockReasonEnum` and `FailureReasonEnum` (moved from
feature 1 — the first failures appear here). Then, per `network-etiquette.md` —
`infrastructure/http/homepage_fetcher.py`
(`HomepageFetcher` over an injected `httpx.AsyncClient`): https then http fallback, ≤ 5
redirects, connect 5 s / read 10 s / total 15 s, honest UA, body cap 2 MB, retry once on
transient errors; returns `FetchResult` (final URL, status, headers incl. all `Set-Cookie`, body
text) or `FetchFailure(reason)`. `infrastructure/http/soft_block.py` classifies 403/429/503 and
challenge pages, keeping headers. `application/ports/signal_collector.py` (`SignalCollector`,
`CollectionResult`, `CollectionFailure`) and `application/use_cases/scan_domain.py`
(`ScanDomainUseCase`) land here with a fake collector test. `HttpSignalCollector` wired in
`bootstrap.py` with no extractors yet. Tests with `respx`.
**E2E:** first live run — sequential is fine; verify 20/20 domains present and no crash.

## [x] 5. Response extractors: headers, cookies, script src, meta, html — PR #5
**Goal:** five pure extractors from `FetchResult` → `tuple[Signal, ...]`.
**Acceptance:** `infrastructure/extractors/headers.py`, `cookies.py` (names from every
`Set-Cookie`), `scripts.py` (`<script src>` incl. protocol-relative and unquoted attrs; inline
bodies captured as `SCRIPT_INLINE` for feature 7), `meta.py` (`name` and `property`), `html.py`
(raw body); `registry.py` lists them; `HttpSignalCollector` runs the registry. Robust to broken
HTML (`html.parser`, never regex over the whole document). Fixtures for Shopify, WordPress,
HubSpot, Cloudflare-block pages.
**E2E:** live; first real detections expected (Cloudflare, Shopify, HubSpot, Stripe…). Name the
signal for each.

## [x] 6. DNS collector — PR #6
**Goal:** MX / TXT / CNAME on the apex, concurrent with the fetch.
**Acceptance:** `domain/domain_name.py` gains `decide_apex_domain` (moved from feature 1, where
it had no caller; the public-suffix trade-off is decided here and documented in the README).
`infrastructure/dns/resolver.py` (`Resolver` Protocol + `DnsPythonResolver`),
`infrastructure/collectors/dns_collector.py` (`DnsSignalCollector`): apex via
`decide_apex_domain`; 3 s timeout per record type; NXDOMAIN/NoAnswer/timeout → empty for that
type, logged at DEBUG; TXT strings joined; CNAME chain first hop. `ScanDomainUseCase` runs both
collectors concurrently. Matched via `dns` patterns (Google Workspace, Microsoft 365, SendGrid,
HubSpot verification, Salesforce). Fake resolver in tests.
**E2E:** live; expect mail-provider detections on most domains.

## [x] 7. JS globals extractor (static) — PR #7
**Goal:** `window.*` names from inline scripts without execution.
**Acceptance:** `infrastructure/extractors/jsglobals.py` scans `SCRIPT_INLINE` bodies for
`window.X =`, `window['X'] =`, and top-level `var/let/const X =` or `function X(`; ignores
string literals, comments and regex literals; emits `JS_GLOBAL` signals. A bare global-shaped
`X = ` is deliberately **not** read: without a parser it cannot be told from a default
parameter, a `for` initialiser or a destructuring target, and the short names it would add
collide with upstream `js` keys under a fullmatch index — a direct false-positive path. Accuracy guard:
a name mentioned only inside a string does not count. Fixtures with GA4 `gtag(`, Intercom,
Segment snippets.
**E2E:** live; GA4 via `gtag(` in `SCRIPT_INLINE` expected on several domains.

## [x] 8. Concurrent scan, budget, structured output, details file — PR #8
**Goal:** the production run: bounded concurrency, hard budget, deterministic JSON, clean logs.
**Acceptance:** bounded concurrency and `--concurrency` moved forward into feature 6, because
adding DNS took the run from 16 s to 61 s and breached the assignment's 60 s budget; bootstrap
already fans out under a semaphore and per-domain isolation already lives in `ScanDomainUseCase`.
What remains here: `application/use_cases/scan_domains.py` (`ScanDomainsUseCase`) taking that
orchestration out of the composition root, a whole-run deadline, a WARNING line per blocked or
failed domain with its reason, and a summary line (domains, detections, blocked, seconds). `application/presenters/scan_report_presenter.py`
(`present_summary`, `present_details`) turns a `ScanReport` into JSON-ready records;
`JsonReportWriter` uses it for both `output.json` and `--details <path>` (spec §6). Tests with
fake slow collectors prove the budget and isolation.
Response parsing and extraction moved onto a worker thread in feature 7, after measurement
showed that blocking the loop pushed concurrent DNS attempts past their timeout and cost real
records in one full scan out of four. Matching is still on the loop: ~3 ms per domain with the
shipped 24 patterns, but ~530 ms against the full 13,373-pattern upstream database, so pointing
`--fingerprints` at that in a timed run would need the same treatment.
- `--nameserver` (repeatable), defaulting to the system resolver. Measured on this machine over
  three full runs each: the system resolver returned 713-749 DNS records and a different number
  per run, in 5-6 s; `1.1.1.1` returned 749 every time in 0.2-0.4 s. DNS-derived detections are
  the only part of `output.json` that does not reproduce, and a scanner reading public records
  has no need of a local resolver's private views — but the choice belongs to whoever runs it,
  so it is a flag rather than a new default. Feature 9's submitted run states which was used.
**E2E:** live, twice; target < 30 s. Docker run (`make docker-scan`) must match the local run.

## [x] 9. Final submission run, output.json, README architecture — PR #9
**Goal:** the deliverable, polished.
**Acceptance:** fresh live run committed as `output.json`; README sections: install (local +
Docker), run, architecture decisions (hexagonal layers and why, `Signal` abstraction,
data-driven fingerprints, key-regex superset, accuracy policy, block handling, budget), known
limitations, how to add a collector, how to extend the fingerprint DB; assignment checklist in
README ticked against `assigment/assigment.md`; `make check` green; the Docker run exercises the
same code path and is compared against the local one, with any difference explained from the
details file rather than assumed away — a network-dependent scan cannot be byte-identical across
environments with different network paths; repo public (the owner's call, not the tool's).
**Submission gate (this feature only):** `make fresh-check` green —
`scripts/fresh_clone_check.sh` clones the *committed* state into a temp dir and builds it there
(*the script and target were reverted in `acc6d8b`; the check is now run by hand — see item 13*):
required files present, `assigment/` and other ignored paths absent, `uv sync --frozen`
resolves, `make check`, both entry points run, `docker build`. Add `--with-e2e` for the
submitted run. No other gate covers this: `make check` runs in a warm working tree that still
has the brief in it.
**E2E:** live; this run is the one submitted.

## [x] 10. Security review and hardening — PR #10
**Goal:** a documented security pass over the shipped CLI, and the guards that make it safe to
put a second driver in front of the same core — feature 11 turns a third party's input into
outbound requests from our host, and every hole must be closed before that, not after.
**Acceptance:**
- Security added as a fifth lens to `.claude/agents/reviewer.md` (untrusted input handling,
  SSRF, ReDoS, resource exhaustion, secrets in images/logs) and to the Definition of Done in
  `CLAUDE.md`, so every later PR is covered by the merge gate rather than by one audit.
- One full-tree `/security-review` pass recorded in the PR body: every finding either fixed
  here, or triaged with a written reason for deferring it.
- **ReDoS.** Fingerprint regexes are untrusted data (24 today, ~13,373 with the upstream DB)
  run against untrusted bodies of up to 2 MB, and `re` has no timeout:
  `check_pattern_is_safe_or_raise` at load time rejects catastrophic shapes (nested quantifiers,
  alternation with overlapping branches under a quantifier) as a `FingerprintLoadError` naming
  the technology, plus a per-match input cap in the matcher. A hostile fixture that currently
  backtracks must finish under 100 ms; the full upstream database must still load clean.
- **SSRF, pre-emptively.** `is_public_target` in the fetcher, applied to the resolved address
  of the initial request *and* of every redirect hop: loopback, private, link-local, ULA and
  any non-`http(s)` scheme are refused with `BlockReasonEnum.PRIVATE_TARGET`, recorded as a
  typed failure on the result — never a crash, never a fetch. This is the guard that makes
  feature 11's `POST /scans` safe to expose.
- **Decompression bombs.** The 2 MB cap counts *decoded* bytes, not the compressed stream;
  a gzip-bomb fixture must stop the read at the cap instead of filling memory.
- **Hostile content in our own output.** Evidence snippets are length-capped and stripped of
  control characters, so a crafted page cannot corrupt `output.json` or smuggle markup into the
  web app's evidence popover.
- **Container and supply chain.** Non-root confirmed; image runs with `--read-only` and
  `--cap-drop ALL`; no secrets in any layer; `.dockerignore` excludes `assigment/`;
  `pip-audit` (dev dep only) run over `uv.lock` with the result in the PR body. No new runtime
  dependency.
- Tests: `tests/fixtures/hostile/` (backtracking page, gzip bomb, redirect to `127.0.0.1`,
  control-character HTML) with a unit test per guard; no network.
- README "Security notes": the three-line threat model (we fetch untrusted pages, we never
  execute them, every resource is bounded) and what the API driver must never relax.
**E2E:** live; `output.json` must be byte-identical to feature 9's submitted run — hardening
that changes detections is a bug — and the runtime no worse than +10%.

## [x] 11. HTTP API driver (only after 10 is merged) — PR #11
**Goal:** the same scan, runnable over HTTP for the web app — a second driver, zero core changes.
**Acceptance:**
- `pyproject.toml` optional extra `api = ["fastapi", "uvicorn[standard]"]`; the core install is
  unchanged.
- The API reuses `present_details` from `application/presenters` (feature 8) unchanged.
- The `is_public_target` guard from feature 10 is what makes an open `POST /scans` safe:
  domains arrive from a third party here, so no request may reach a private address.
- `bootstrap.build_scan_service(options)` async context manager; `run_scan` now uses it.
- `presentation/api/app.py` `create_app(service: ScanService | None = None)` with a lifespan
  that builds the service via bootstrap when none is injected; `routes.py`: `POST /scans`
  (normalises domains, caps at 50, runs `ScanDomainsUseCase`, returns the details shape),
  `GET /fingerprints`, `GET /health`; `schemas.py` for the JSON boundary. Errors are typed
  JSON (`{"error": {"code": ..., "message": ...}}`), never a traceback.
- `Dockerfile` target `api` (uvicorn on 8000, non-root); `compose.yaml` service `api`.
- Tests: `TestClient` + fake `ScanService` (no network): happy path, empty list → 422,
  > cap → 422, one domain failing still returns 200 with the failure recorded; architecture
  test extended for `presentation/api` and the `fastapi` allowance.
- README "API" section (run locally with `uv run --extra api uvicorn ...`, Docker, endpoints).
**E2E:** `docker compose up api` + `curl -X POST /scans` with the 20 domains; response matches
the CLI `--details` run for the same domains (modulo timing); under 60 s.

## [x] 12. Web app — Next.js (only after 11 is merged) — PR #12
**Goal:** run a scan from the browser and see the evidence behind every detection.
**Acceptance:**
- `web/` Next.js (App Router, TypeScript, ESLint, no static export). Two routed pages: a scan
  form (textarea + `.txt` file drop) at `/`, and the matrix at `/multi-scan-results`, which runs
  the scan in its own server component so the form holds no result state. One domain is sent to
  its own page instead, since a one-row matrix says less than the detail view.
- A **server action** is the only code that talks to `API_URL` (server-side, no CORS in the
  browser). *Amended from "route handler": the same job, in the form this project prefers.*
- *Dropped: concurrency/timeout advanced options.* Feature 11 made those bounds a property of
  the shared, long-lived service, so a request that set them would set them for every other
  caller. Shipping controls that do nothing would be worse than not shipping them.
- Results: domain × technology matrix, a tick per detection dimmed below full confidence;
  per-cell popover with evidence (channel, key, pattern, matched text, confidence);
  blocked/failed domains with reason; summary (domains, detections, blocked, seconds);
  "Download output.json" producing the assignment shape client-side.
- Loading and error states (API down, deadline hit, validation errors from 422).
- `web/Dockerfile` (Node 22 multi-stage) and `compose.yaml` service `web` with
  `depends_on: api`; `docker compose up` brings up api + web on :3000.
- Follows the `vspathonis-code-style` skill and `.claude/rules/typescript-style.md`: strict
  tsconfig with `noUncheckedIndexedAccess`, zod parsing in the server action (the only code
  that calls `API_URL`), types inferred from the schemas, `as const` objects mirroring
  `ChannelEnum` values, no `any`/`as`/`!`/`enum`. *A discriminated-union `ScanState` is no
  longer needed: with the scan on its own route there is no client-side phase to model.*
- A third page, `/domain/<domain>`, scans one domain and shows every detection with all of its
  evidence open, plus the URL the page was read from and anything that went wrong. It is where
  submitting a single domain lands, and where a domain name in the matrix links to.
- `npm run lint` and `npx tsc --noEmit` clean. Not part of `make check`. README "Web app"
  section with a screenshot.
**E2E:** `docker compose up`, paste the 20 domains, scan completes under 60 s, matrix matches
`output.json` from the CLI run.

## [~] 13. Post-submission audit fixes
**Goal:** close what a full audit of the delivered tree against the brief turned up. A fresh
clone of `main` was built and gated by hand (`uv sync --frozen`, `make check`, both entry
points, Docker build, seven live runs), and the whole tree was reviewed against every line of
the brief. All hard constraints held; these are the corrections.
**Acceptance:**
- **A timed-out DNS lookup is a recorded problem, not an absence.** On the system resolver six
  live runs returned 40-46 detections with `problems: []` on every domain; via `1.1.1.1` all
  returned the committed 46. `Resolver.resolve` returns `DnsAnswer(records, failure)`;
  `DnsSignalCollector` turns failed record types into one `CollectionFailure` (`dns: timeout`)
  naming them, so the details file and the WARNING log say the records were never read.
- **An `implies` entry keeps its own confidence.** `PHP\;confidence:50` was reported at the
  implier's confidence. `Fingerprint.implies` is now `tuple[Implication, ...]`, and the matcher
  bounds an implied technology by the weaker of the two and applies the reporting threshold.
- **An input domain cannot carry invisible characters.** A byte order mark, a NUL or a bidi
  override in a line is removed before normalisation; whitespace is kept so two words are still
  refused. The API accepts domain lists from strangers, and those characters reached the log.
- **A dropped input line is warned about.** A line that normalises to nothing was dropped at
  every log level; it is now one WARNING quoting the line, invisible characters stripped and
  length-capped. Blank lines and comments stay silent.
- README: the `^intercom-` → `^intercom-.*` respelling is stated beside the `fullmatch` rule;
  the DNS section and the known limitations describe the recorded timeout; item 9's reverted
  fresh-clone gate is noted here; the spec's `implies` rule is amended.
**E2E:** live; `output.json` unchanged (the fixes change what is recorded, not what is
detected), a system-resolver run that loses TXT records now lists them under `problems`.
