# TechScope — Design Spec (2026-09-05)

Approved design for the technographic-detection CLI in `assigment/assigment.md` and for the
Claude-driven delivery workflow. Amend this file when a decision changes.

Revision 2 (same day): architecture changed from a flat single-package layout to a lightweight
Clean / Hexagonal layout at the user's request; Docker added as a first-class run mode; the
HTTP API driver and Next.js web app added as backlog items 10–11, after the submission; `doc/`
merged into `docs/`.

## 1. Goal and constraints

Given a text file of domains, detect which technologies each uses from public HTTP + DNS signals,
matched against Wappalyzer-format fingerprints, and write `{ "domain": [technologies] }`.
Binding constraints: HTTP only (no headless browser), no paid API, ≥ 4 channels (we do 6), 20
domains < 60 s, accuracy over recall, never crash on a bad domain, fingerprint set extensible to
~7,500 entries with no code change. Deliverables: public repo, README, `output.json`.

## 2. Architecture

Lightweight Clean / Hexagonal. Layout, dependency rule, ports and use cases are specified in
`.claude/rules/architecture.md`; this section records the reasoning.

```
domains.txt ─► presentation/cli.py ─► bootstrap.py ─► ScanDomainsUseCase
                                                          │ per domain, under a semaphore
                                                          ▼
                                                   ScanDomainUseCase
                                        ┌─────────────────┴─────────────────┐
                                        ▼                                   ▼
                           HttpSignalCollector                    DnsSignalCollector
                     (HomepageFetcher → extractors)          (Resolver → MX/TXT/CNAME)
                                        └──────────── tuple[Signal, …] ─────┘
                                                          ▼
                                 domain/matcher.match_signals(signals, FingerprintIndex)
                                                          ▼
                                     DomainScanResult ─► ScanReport ─► JsonReportWriter
                                                                          ▼
                                                              output.json (+ details JSON)
FingerprintIndex ◄── build_fingerprint_index ◄── JsonFingerprintRepository ◄── technologies.json
```

- **Why hexagonal here:** the assignment's two hard qualities — accuracy and extensibility — live
  in the matcher and the fingerprint data. Keeping the domain free of `httpx`/`dns` means the
  accuracy logic is tested from fixtures alone, and "add a TLS / WHOIS / JS collector" is a new
  adapter plus one line in the composition root.
- **Why lightweight:** `Protocol`s instead of ABCs, dataclasses instead of pydantic, a hand-written
  `bootstrap.py` instead of a DI container. Two use cases, three ports, two collectors. Nothing
  exists for a future that isn't in the backlog.
- **The `Signal` abstraction:** every channel is reduced to `Signal(channel, value, key)`. Keyed
  channels (header, cookie, meta) carry the name in `key`; keyless ones (script src, inline
  script, html, js global, dns) leave it `None`. The matcher groups fingerprints by channel once
  (`FingerprintIndex`) so matching is per-channel, never all × all.
- **Collectors return, never raise.** `CollectionResult(signals, failure)`: a soft-blocked
  domain yields the header signals that arrived plus a `CollectionFailure(reason)`. The use case
  still wraps each collector in `gather(return_exceptions=True)` as a last line of defence.
- **Data-driven fingerprints:** `technologies.json` in the real Wappalyzer shape (`headers`,
  `cookies`, `scriptSrc`, `scripts`, `html`, `meta`, `js`, `dns`, `implies`, `cats`). The
  repository parses the `\;confidence:N` / `\;version:X` suffixes, compiles every regex once with
  `re.IGNORECASE`, and fails loudly on a bad pattern.

## 3. Channels

| ChannelEnum | Source | Wappalyzer key | Signal.key |
|---|---|---|---|
| HEADER | response headers, every value | `headers` (name → value regex) | header name |
| COOKIE | every `Set-Cookie` | `cookies` (name → value regex) | cookie name |
| SCRIPT_SRC | `<script src>` incl. `//` protocol-relative | `scriptSrc` | — |
| SCRIPT_INLINE | `<script>` bodies, static text | `scripts` | — |
| HTML | raw body | `html` | — |
| META | `<meta name|property … content>` | `meta` (name → content regex) | meta name |
| JS_GLOBAL | names assigned on `window`/top-level in inline scripts, static only | `js` | — |
| DNS_MX / DNS_TXT / DNS_CNAME | records on the apex | `dns.{MX,TXT,CNAME}` | — |

HTML is parsed with a tolerant parser (`html.parser`), never regex over the whole document.

Assignment-to-Wappalyzer mapping of the 24 given patterns: `[script]` → `scriptSrc`, **except**
`gtag\(` which can only occur in inline script text and goes to `scripts`; `[header]` → `headers`;
`[cookie]` → `cookies`; `[html]` → `html`; `[dns_mx|txt|cname]` → `dns.MX|TXT|CNAME`.

**A script URL is matched only as a src attribute, never in script text.** Widening it was tried
and reverted on evidence. Three of the assignment's own domains load their vendor by writing the
URL from an inline loader rather than as a src, so matching script text would have added Segment
on segment.com and sendgrid.com, and Zendesk on zendesk.com. It would also have added **Sentry on
sentry.io, which is false**: that page serialises its own onboarding documentation into a script
element, and the only occurrence of `browser.sentry-cdn.com` is a markdown code sample containing
a literal `<VERSION>` placeholder, with no corresponding script src anywhere on the page. The
brief's own channel list says "HTML `<script>` src attributes", and its stated priority is that a
technology be reported only on strong evidence. A URL sitting in arbitrary script text is not
that. The channel the brief provides for loader-based vendors is `window.*` globals; the 24 given
fingerprints contain no `js` patterns, so those vendors are simply not detectable with this set —
an honest limitation of the given data rather than something to paper over in the matcher.

**Only executable script counts as script.** A `<script>` element whose `type` is not a
JavaScript type — `application/json`, `application/ld+json`, `text/template` — is page data, not
code. Server-rendered frameworks serialise a page's own editorial copy into exactly those, so
treating them as script text would match vendor URLs in prose. The parser skips them, which also
keeps the JavaScript-global scan of feature 7 out of JSON blobs.

## 4. Matching and accuracy

- A pattern matches with `re.search` on each `Signal.value` of its channel.
- **Keyed channels:** Wappalyzer keys are literal names, but the assignment supplies regex-shaped
  names (`X-Stripe-.*`, `^intercom-`). We therefore treat the key as a case-insensitive regex
  against `Signal.key`, and the value pattern (empty = "any value") with `re.search` against
  `Signal.value`. A literal Wappalyzer key is a valid regex, so the full database still loads
  unchanged. This is a documented superset of Wappalyzer semantics.
- **The key is matched with `re.fullmatch`.** A keyed pattern must name the signal end to end.
  Anything less turns a literal upstream key into a substring or prefix test on another
  technology's name. Measured over the 7,894 keyed patterns of the full upstream database,
  cross-technology key collisions number **883 under `search`, 199 under `match` and 3 under
  `fullmatch`**: unanchored, the F5 BigIP cookie key `TIN` fires on the ordinary WordPress cookie
  `wp-settings-time-1`; anchored only at the start, `core-js`'s global `core` still fires on
  `window.corebine`. No upstream key is written as a prefix — zero of 5,507 literal keys begin
  with `^` — so requiring the whole name costs nothing there, and a pattern that really means
  "starts with" says so with its own quantifier. The one shipped pattern that needs this is the
  assignment's `^intercom-`, stored as `^intercom-.*`: the same meaning, spelled out. An empty
  *value* pattern stays legal on a keyed channel, where it means "this header exists"; on a
  keyless channel it would match every page, so the loader rejects it.
- A technology's confidence is the max over its matched patterns (default 100); reported only
  when ≥ 50. `implies` adds implied technologies at the implier's confidence.
- Detections carry `Evidence(channel, key, pattern_source, matched_text)` so every reported
  technology can be justified; e2e reports name the signal for each new detection, and the
  `--details` output exposes it.
- No inference from names, domains, or company identity. A soft-blocked domain still yields
  header + DNS evidence (a Cloudflare block proves Cloudflare).

## 5. Robustness and budget

- Per domain: https then http fallback, ≤ 5 redirects, connect 5 s / read 10 s / total 15 s,
  body cap 2 MB, one retry on transient errors, honest `User-Agent`.
- Soft blocks (403/429/503, challenge pages, empty bodies) are classified, logged at WARNING
  with reason, and never raise.
- Concurrency default 10; DNS per record type 3 s. Whole run has a deadline; the 20-domain e2e
  target is < 30 s, hard limit 60 s.
- Every input domain appears in the output, in input order, technologies sorted, no
  duplicates; JSON `indent=2`, trailing newline.

## 6. Output

- `output.json` — exactly the assignment shape: `{ "<domain>": ["Tech", …] }`.
- `--details <path>` (feature 8) — a second file for humans and the web app:
  per domain `detections[{name, confidence, evidence[]}]`, `failures[{collector, reason}]`,
  `duration_seconds`, plus a run `summary`. Never replaces `output.json`. Both shapes are
  produced by `application/presenters/scan_report_presenter.py`, which the API reuses verbatim.

## 7. Packaging and run modes

- **Local CLI:** `uv sync && uv run techscope scan docs/domains.txt -o output.json`.
- **Docker CLI:** multi-stage `Dockerfile`, target `cli` — builder on
  `ghcr.io/astral-sh/uv:python3.13-bookworm-slim` runs `uv sync --frozen --no-dev`; runtime on
  `python:3.13-slim-bookworm` copies only `.venv`, runs as a non-root user, `WORKDIR /data`,
  `ENTRYPOINT ["techscope"]`. Callers bind-mount the directory holding the domain file:
  `docker run --rm -v "$PWD:/data" techscope:local scan docs/domains.txt -o output.json`.
  `.dockerignore` excludes `.venv`, `.git`, tests, docs, `web/`.
- **Docker API (feature 10):** same `Dockerfile`, target `api` — installs the `api` extra and
  runs `uvicorn techscope.presentation.api.app:create_app --factory` on port 8000.
- **Docker web (feature 11):** `web/Dockerfile` (Node 22, `next build`, `next start` on 3000).
- **`compose.yaml`:** services `scan` (one-shot CLI, profile `cli`), `api`, and `web`
  (`depends_on: api`, `API_URL=http://api:8000`). `docker compose up` gives the web app;
  `docker compose run --rm scan ...` gives the CLI. `make docker-scan` wraps the latter.
- The image is a convenience for the reviewer; `output.json` submitted is produced by the same
  code path either way (feature 9 checks local and Docker runs agree).

## 8. Testing strategy

Offline unit tests only in `make check`: `respx` for HTTP, a fake `Resolver` for DNS, fake
collectors for the use cases, fixtures as files. Each fingerprint has positive + near-miss tests.
`tests/unit/test_architecture.py` walks `src/techscope` with `ast` and fails on any import that
breaks the layer rule. Live runs (`tests/live`, marked `live`) are used only by the e2e step and
the final submission.

## 9. Delivery workflow

- Backlog in `docs/backlog.md`, in order, one PR each. Items 1–9 are the graded CLI
  submission; items 10–11 (API driver, web app) start only after 9 is merged so the submission
  is never blocked by them.
- `/ship-next` per feature: preflight (personal `gh` login, clean tree, previous PR merged) →
  branch from `origin/main` → design note → TDD → `make check` → `reviewer` agent (panel on
  escalation, adversarial-verifier gates every CRITICAL) → `/e2e` live run with 60 s check and
  `output.json` diff → commit by path → push → PR from the template → stop.
- The user merges on GitHub; `/loop 15m /ship-next` may drive the cadence, since the command
  stops cleanly while a PR is open.
- Repo identity is personal (`baggelisp`); the work `gh` account must never open PRs here.

## 10. Web app: API driver + Next.js (after submission)

The scan must be runnable from the CLI (the assignment) **and** from a web app. The hexagonal
layout makes the web app a second driver of the same use cases, not a second implementation:

- **`presentation/api/`** — a small FastAPI app. `POST /scans` takes `{domains: [...],
  concurrency?, timeout?}`, runs `ScanDomainsUseCase` synchronously under the same deadline as
  the CLI, and returns the details shape from the shared presenter. `GET /fingerprints` lists
  the loaded technologies and their channels. `GET /health`. Domains are normalised with the
  same `decide_domain_or_none` the CLI applies per line; the list is capped (default 50) to keep a request bounded.
  Dependencies `fastapi` + `uvicorn` live in an optional extra `techscope[api]` so the graded
  CLI install stays `httpx` + `dnspython` only. Tests use FastAPI's `TestClient` with a fake
  `ScanService` injected through `create_app(service=...)` — no network, no real adapters.
- **`web/`** — Next.js (App Router, TypeScript) with a textarea / file drop for domains, a
  "Scan" action calling a Next.js route handler that proxies to `API_URL` (no CORS in the
  browser), and a results view: domain × technology matrix, per-cell evidence popover (channel,
  key, pattern, matched text, confidence), blocked domains with reason, run summary and timing,
  and a "download output.json" that reproduces the assignment shape client-side. Follows the
  `vspathonis-code-style` skill. Own `package.json`, lint and typecheck; not part of
  `make check`.
- **Rejected:** a Next.js route handler spawning the Python CLI (couples two runtimes in one
  container, loses evidence detail); a static viewer over a JSON file (cannot run a scan);
  websockets / job queue for progress (not needed at 20 domains under 60 s — revisit only if a
  larger cap is ever wanted).

## 11. Rejected alternatives

- **Flat single-package layout** (`cli.py`, `matcher.py`, `fetch/`, `channels/`, `pipeline.py`):
  fewer files, but the I/O boundary was by convention only. Replaced by the hexagonal layout so
  the boundary is a tested import rule and the user's architecture brief is met.
- **Per-channel `Signals` dataclass** (one field per channel): forces a matcher change for every
  new channel. Replaced by the flat `Signal` record + `FingerprintIndex`.
- Workflow-tool multi-agent orchestration: token-expensive, unnecessary for a solo assignment.
- Separate hand-chained commands per phase: less automation than asked.
- Live-network unit tests: flaky and slow; fixtures + one live run per feature instead.
- pydantic / typer / a DI container: stdlib dataclasses, argparse and a hand-written
  `bootstrap.py` suffice; fewer moving parts for a reviewer to install.
- Making `fastapi` a core dependency: it would bloat the graded CLI install; it is an optional
  extra instead.
