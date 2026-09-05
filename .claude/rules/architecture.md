# Architecture — lightweight Clean / Hexagonal

TechScope keeps its core business logic independent of HTTP libraries, DNS libraries, the CLI, and
the filesystem. Four layers, one dependency direction, no enterprise ceremony. This file is the
source of truth for the layout; `CLAUDE.md` summarises it, the spec explains the reasoning, and a
unit test (`tests/unit/test_architecture.py`) enforces the import rules mechanically.

## Layers and the dependency rule

```
presentation ──► application ──► domain ◄── infrastructure
      │                │                          ▲
      └────────────────┴──── bootstrap.py ────────┘   (composition root: the only module
                                                        that imports every layer)
```

| Layer | May import | Must never import |
|---|---|---|
| `domain/` | stdlib except `argparse`/`json`, `domain` | `application`, `infrastructure`, `presentation`, `httpx`, `dns`, `argparse`, `json` file I/O |
| `application/` | stdlib except `argparse`/`json`, `domain`, `application` | `infrastructure`, `presentation`, `httpx`, `dns` |
| `infrastructure/` | stdlib except `argparse`, `domain`, `application.ports`, `infrastructure`, `httpx`, `dns` | `application.use_cases`, `presentation` |
| `presentation/` | stdlib, `domain`, `application`, `presentation`, `bootstrap`, `fastapi` (api only) | `infrastructure`, `httpx`, `dns` |
| `bootstrap.py` | everything except `presentation` and `argparse` | `presentation` |

The rule in one sentence: **the arrow always points inward**; the domain knows nothing, the
application knows the domain and its own ports, adapters implement ports, and only the
composition root knows which adapter is plugged in. There are **two drivers** of the same use
cases — the CLI (the graded deliverable) and the HTTP API behind the web app — and neither knows
about the other or about any adapter.

## Package layout

```
src/techscope/
  __init__.py
  __main__.py                          `python -m techscope` → presentation.cli.main
  bootstrap.py                         composition root: build adapters, wire use cases, run
  domain/                              PURE — no I/O, no clock, no globals, no third-party imports
    enums.py                           ChannelEnum, BlockReasonEnum, FailureReasonEnum
    models.py                          Signal, Pattern, Fingerprint, FingerprintIndex, Evidence,
                                       Detection, CollectionFailure, DomainScanResult, ScanReport
    errors.py                          TechScopeError, FingerprintLoadError
    domain_name.py                     decide_domain_or_none (one input line -> a domain),
                                       decide_apex_domain (arrives with the DNS collector)
    domain_list.py                     build_domain_list (file text -> ordered, deduplicated)
    matcher.py                         build_fingerprint_index, match_signals
  application/
    ports/                             Protocols the use cases depend on
      signal_collector.py              SignalCollector: async collect(domain) -> CollectionResult
      fingerprint_repository.py        FingerprintRepository: load() -> tuple[Fingerprint, ...]
      scan_report_writer.py            ScanReportWriter: write(report, destination)
    use_cases/
      scan_domain.py                   ScanDomainUseCase: collectors → signals → matcher → result
      scan_domains.py                  ScanDomainsUseCase: semaphore, deadline, per-domain isolation
    presenters/
      scan_report_presenter.py         present_summary / present_details: ScanReport → JSON-ready
                                       records, shared by the file writer and the API
  infrastructure/
    http/
      models.py                        FetchResult, FetchFailure (adapter-private records)
      homepage_fetcher.py              HomepageFetcher: httpx, https→http fallback, redirects, body cap
      soft_block.py                    decide_block_reason_or_none (403/429/503, challenge pages)
    extractors/                        PURE — FetchResult → tuple[Signal, ...], one channel each
      headers.py  cookies.py  scripts.py  meta.py  html.py  jsglobals.py
      registry.py                      EXTRACTORS: the ordered tuple the HTTP collector runs
    dns/
      resolver.py                      Resolver Protocol + DnsPythonResolver
    collectors/                        SignalCollector adapters
      http_collector.py                HttpSignalCollector: one fetch, then every extractor
      dns_collector.py                 DnsSignalCollector: MX / TXT / CNAME on the apex
    repositories/
      wappalyzer_pattern.py            parse `regex\;confidence:N\;version:X` → Pattern
      json_fingerprint_repository.py   JsonFingerprintRepository (Wappalyzer JSON shape)
      data/technologies.json           the assignment's 24 fingerprints
    writers/
      json_report_writer.py            JsonReportWriter: `{domain: [tech]}` and the --details shape
  presentation/
    cli.py                             argparse, logging setup, exit codes; calls bootstrap
    api/                               (backlog item 10) FastAPI driver for the web app
      app.py                           create_app(): lifespan builds the scan service via bootstrap
      routes.py                        POST /scans, GET /fingerprints, GET /health
      schemas.py                       request/response records for the JSON boundary
web/                                   (backlog item 11) Next.js app; talks only to presentation/api
tests/
  unit/                                mirrors src/techscope/<layer>/…; no network, ever
  fixtures/                            recorded HTML / headers / DNS answers as small files
  live/                                @pytest.mark.live, used only by `make e2e`
```

## The core abstraction: `Signal`

Every collector, whatever its source, produces the same thing:

```python
@dataclass(frozen=True, slots=True)
class Signal:
    channel: ChannelEnum      # HEADER, COOKIE, SCRIPT_SRC, SCRIPT_INLINE, HTML, META, JS_GLOBAL,
                              # DNS_MX, DNS_TXT, DNS_CNAME
    value: str                # header value, cookie value, script URL, inline body, meta content, …
    key: str | None = None    # header name, cookie name, meta name — None for keyless channels
```

The matcher only ever sees `tuple[Signal, ...]` and a `FingerprintIndex` (fingerprints grouped by
channel once at load time). It never learns where a signal came from. Adding a collector — TLS,
WHOIS, robots.txt — is a new adapter that emits `Signal`s and one line in `bootstrap.py`.

## Ports (application/ports)

```python
class SignalCollector(Protocol):
    name: str                                         # for logs: "http", "dns"
    async def collect(self, domain: str) -> CollectionResult: ...
    # CollectionResult(signals: tuple[Signal, ...], failure: CollectionFailure | None)
    # A soft block returns the header signals it got AND a failure reason. Never raises.

class FingerprintRepository(Protocol):
    def load(self) -> tuple[Fingerprint, ...]: ...    # raises FingerprintLoadError, nothing else

class ScanReportWriter(Protocol):
    def write(self, report: ScanReport, destination: Path) -> None: ...
```

Ports are small `typing.Protocol`s, not ABCs. An adapter is any class with the right shape; tests
use hand-written fakes (`FakeSignalCollector`, `InMemoryFingerprintRepository`) — never
`unittest.mock` patching of `httpx` or `dns` internals.

## Use cases (application/use_cases)

- `ScanDomainUseCase(collectors, fingerprint_index)` — runs every collector concurrently for one
  domain (`asyncio.gather(..., return_exceptions=True)` as a last-resort guard), flattens the
  signals, calls `match_signals`, returns `DomainScanResult(domain, detections, failures)`.
- `ScanDomainsUseCase(scan_domain, concurrency, deadline_seconds)` — bounded fan-out with an
  `asyncio.Semaphore`, per-domain `try/except` isolation so one domain can never drop another,
  whole-run deadline, results in input order. Returns `ScanReport`.

Two use cases on purpose: the single-domain one is trivially unit-tested with fake collectors;
the multi-domain one owns concurrency and is tested with fake slow collectors and a fake clock.

## Composition root (bootstrap.py)

The only place that knows concrete classes. It exposes two things:

- `build_scan_service(options) -> AsyncContextManager[ScanService]` — opens the
  `httpx.AsyncClient`, builds `HomepageFetcher`, `HttpSignalCollector`, `DnsSignalCollector`,
  loads fingerprints through `JsonFingerprintRepository`, builds the `FingerprintIndex`, wires
  `ScanDomainUseCase` → `ScanDomainsUseCase`, and closes the client on exit. `ScanService` is a
  small frozen record holding the wired `ScanDomainsUseCase` and the loaded fingerprints.
- `run_scan(options) -> ScanReport` — the CLI's one-shot convenience over `build_scan_service`.

`presentation/cli.py` parses arguments into a `ScanOptions` record and calls `run_scan`.
`presentation/api/app.py` calls `build_scan_service` once in its lifespan and keeps the service
for the process lifetime. No module outside `bootstrap.py` constructs an adapter.

## Two drivers, one core

| | CLI (`presentation/cli.py`) | API (`presentation/api/`) |
|---|---|---|
| Input | domains file | `POST /scans {domains: [...]}` |
| Output | `output.json` (+ `--details`) via `JsonReportWriter` | JSON body from `present_details` |
| Wiring | `bootstrap.run_scan` per invocation | `bootstrap.build_scan_service` at startup |
| Deps | stdlib only | `fastapi` + `uvicorn` in the optional `api` extra |
| Ships in | the graded submission | Docker `api` target + `web/` (backlog 10–11) |

The presenter in `application/presenters` is the single place that turns a `ScanReport` into
JSON-shaped records, so the file the CLI writes and the body the API returns can never drift.

## What is deliberately NOT here

- No abstract base classes, no `Handler`/`Strategy` hierarchies, no DI container, no events.
- No repository for the domain list — the CLI reads the text file and passes `tuple[str, ...]`.
- No port for logging — `logging.getLogger(__name__)` is fine everywhere.
- No job queue or scan persistence for the API: a scan is a synchronous request bounded by the
  same deadline as the CLI. If history is ever wanted, it is a new port + adapter, not a rewrite.
- The web app never imports Python and never reads the filesystem; it only calls the API.
