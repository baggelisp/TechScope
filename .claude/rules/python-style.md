# Python Style — vspathonis house style, Python edition

This is the user's personal code style (the `vspathonis-code-style` skill) translated from
TypeScript/React to Python. The React/JSX/Tailwind/i18n rules have no counterpart here; every
rule below is binding and the `reviewer` agent checks them. When a rule here and generic PEP 8
taste disagree, this file wins.

## Baseline

- Python 3.13, `src/` layout, native syntax (`list[str]`, `X | None`); `ruff` formats, `mypy
  --strict` type-checks. Both are part of `make check`.
- Type every parameter and return. **No `Any`**, no `cast()`, no `# type: ignore` — if a type
  is hard to express, reshape the data. The single exception is a documented boundary
  (e.g. parsing untyped JSON in the fingerprint loader), with a one-line reason on the same line.
- **Models are frozen dataclasses** (`@dataclass(frozen=True, slots=True)`), named accurately for
  what they hold; rename when the meaning drifts. No dicts passed around as records. No empty
  subclass that only inherits.
- `logging.getLogger(__name__)` everywhere; `print` only in `cli.py`. No debug output in shipped
  code.

## Naming (the `decide*` family)

| Prefix / suffix | Use for | Example |
|---|---|---|
| `fetch_*` | reads from the network | `fetch_homepage`, `fetch_dns_records` |
| `load_*` | reads from disk / package data | `load_fingerprints` |
| `collect` | the `SignalCollector` port method: source → `CollectionResult` | `HttpSignalCollector.collect` |
| `extract_*` | pure: raw response → signals | `extract_script_srcs` |
| `match_*` | pure: signals × fingerprints → detections | `match_signals` |
| `build_*` | pure: derives a structure from data once | `build_fingerprint_index` |
| `*UseCase` | application-layer orchestration class | `ScanDomainUseCase` |
| `*Collector` / `*Repository` / `*Writer` | infrastructure adapter implementing a port | `DnsSignalCollector`, `JsonFingerprintRepository` |
| `decide_*` | pure: resolves one value from inputs | `decide_apex_domain` |
| `decide_*_or_none` | same, may return `None` | `decide_charset_or_none` |
| `is_*` / `has_*` | predicate returning `bool` | `is_soft_blocked`, `has_location_header` |
| `check_*_or_raise` | validates and raises on failure, does nothing else | `check_pattern_compiles_or_raise` |
| `write_*` | side effect to disk / stdout | `write_output_json` |
| `*Enum` | every enum class | `ChannelEnum`, `BlockReasonEnum` |
| `*Error` | every exception | `FingerprintLoadError` |

- **No abbreviations, no single letters** — `response` not `resp`, `fingerprint` not `fp`,
  `for record in records` not `for r in records`, `channel_value` not `cv`. Full words in
  comprehensions and `key=` lambdas too.
- **Name by the concept, not the first variant.** Once code handles several channels, the
  generic fields are `patterns`, `signal_values`, not `script_patterns`.
- A helper named `check_*_or_raise` **only guards**. It never also performs the work. If it
  fetches, parses, or writes, it is misnamed.
- Constants are `UPPER_SNAKE` at the top of the module. Any string or number with domain
  meaning — a timeout, a header name, a status code list, a confidence threshold, a user-agent —
  is a named constant, never an inline literal. Shared across modules → `constants.py`.

## Control flow

- **Guard clauses first, happy path last, no nesting.** Negative early returns for input
  validation; the main path is the final `return` at indentation level one.
- **Prefer positive `if`** for branching logic (`if is_html: … else: …`, not `if not is_html`).
  Negative conditions are only for guard clauses.
- **No inline conditionals in a `return`, an argument, an f-string, or a dict/dataclass
  literal.** `x if cond else y`, `a or b`, `a and b` used as value selectors are resolved into a
  named local first, usually via a `decide_*` helper:

  ```python
  # ❌
  return Detection(name=fingerprint.name, confidence=pattern.confidence or DEFAULT_CONFIDENCE)

  # ✅
  confidence = decide_pattern_confidence(pattern)
  return Detection(name=fingerprint.name, confidence=confidence)
  ```

- **Dense boolean chains → named intermediate locals.**

  ```python
  # ❌
  if response.status_code in BLOCK_STATUS_CODES and not body and "cf-ray" in headers: ...

  # ✅
  is_block_status = response.status_code in BLOCK_STATUS_CODES
  is_empty_body = len(body) == 0
  is_cloudflare = CLOUDFLARE_RAY_HEADER in headers
  is_soft_blocked = is_block_status and is_empty_body and is_cloudflare

  if is_soft_blocked: ...
  ```

- **`decide_*` helpers use positive `if` + early return**, one blank line between blocks:

  ```python
  def decide_scheme_fallback_or_none(error: httpx.HTTPError) -> str | None:
      if isinstance(error, httpx.ConnectError):
          return HTTP_SCHEME

      return None
  ```

- **Blank line before and after every compound block** (`if`, `for`, `with`, `try`, `match`)
  at the same indentation level, and a blank line after the guard-clause group.
- **No variable reassignment across branches.** Do not declare `result = None` and overwrite it
  in `if`/`else` arms; return early, or compute the value once with a `decide_*`. Never shadow a
  parameter.
- **`match` statements: one-line `return` per case, always a `case _:`** that raises on the
  unexpected value (never a silent fallback) unless an empty value is logically correct.
  Complex per-case logic goes into a named helper.
- **Lookups by key, not scans.** Use `next((x for x in xs if …), None)`-style single lookups
  wrapped in a `decide_*_or_none`; never `any(...)` followed by a `filter`. Index fingerprints
  per channel in a dict once at load time; never loop all fingerprints × all signals × all
  channels.
- **Comprehensions stay one-line and one-clause.** A comprehension that both filters and
  transforms, or nests, becomes a named function or a plain loop.
- **No multi-line lambdas; no lambdas beyond trivial `key=`.** Named functions.

## Variant behaviour — one registry keyed by the discriminator

When behaviour varies by an enum (channel, block reason, DNS record type), put the per-variant
behaviour in **one dict keyed by that enum** and have callers read from it. Never scatter
`if channel == ChannelEnum.HEADERS` checks across modules; adding a variant must be exactly one
registry entry (+ one data entry where a data list feeds it).

```python
WAPPALYZER_KEY_TO_CHANNEL: dict[str, ChannelEnum] = {
    "headers": ChannelEnum.HEADER,
    "cookies": ChannelEnum.COOKIE,
    "scriptSrc": ChannelEnum.SCRIPT_SRC,
    ...
}
```

The registry stays **pure** — it maps to functions, field names, and formatters, never to I/O.

Counter-rule: do **not** build a handler/strategy class hierarchy for two or three *pure*
variants touched in one or two places. A short direct call or a registry is clearer than a
`Handler` interface plus a coordinator. The exception is the I/O boundary: `SignalCollector`,
`FingerprintRepository`, `ScanReportWriter` and `Resolver` are `Protocol` ports by design (see
`architecture.md`) — they exist so the application layer never imports `httpx` or `dns`, not to
model variants. Do not add a port for something that has no I/O.

## Functions and modules

- **The main work stays in the main function; helpers take the side concerns.** A pipeline
  step should read as its actual steps, not as a list of guards followed by one call to a helper
  that does everything. Helpers are `decide_*`, `is_*`, `check_*_or_raise`, and pure mappings —
  each small enough to understand without its caller.
- **Small functions, one job.** Longer than ~40 lines is a smell; split by responsibility.
- **One primary public thing per module.** One extractor per module, one class per module for the
  substantial classes (`HomepageFetcher`, `HttpSignalCollector`, `DnsSignalCollector`,
  `ScanDomainUseCase`, `ScanDomainsUseCase`); private helpers are `_`-prefixed in the same
  module. Modules replace the TypeScript "utility classes" — do not create `StringUtility`-style
  static classes in Python.
- **Types live where they are owned.** Cross-layer records in `domain/models.py`; adapter-private
  records (`FetchResult`, `FetchFailure`) next to their adapter; a module never imports a type
  from its caller. No circular imports. The layer import table in `architecture.md` is enforced
  by a test.
- **Pass the whole object, not a fan of scalars.** Extractors take `FetchResult`, not
  `(headers, body, cookies, final_url)`. If a function needs several fields of one object, pass
  the object. **Pass data, not derived booleans** — `is_blocked` is decided inside the consumer
  from the result, not computed by the caller and threaded down.
- **Don't add a parameter that never varies.** If every call site passes the same literal,
  inline it in the callee as a constant. **Don't give a parameter a default when every call site
  passes it** — optional parameters signal "may be omitted".
- **Single source of truth.** Shared state (the `FingerprintIndex`, the HTTP client, the
  semaphore) lives in one owner and is passed down; never rebuilt or copied in a callee.
- **Inject I/O through ports.** Use cases receive `SignalCollector`s and a
  `FingerprintRepository`; adapters receive the `httpx.AsyncClient` / `Resolver` in their
  constructor. Everything is wired once in `bootstrap.py`; tests substitute fakes without
  monkeypatching.

## Absence and errors

- **`None` means absent — never coerce to `""`, `0`, or `[]` at the data layer.** A missing
  charset is `None`; the consumer decides what to do. Handle absence in the caller with an early
  return so callees receive resolved, non-`None` values. Convert at the boundary with a
  `decide_*_or_none` helper, never an inline `or ""`.
- **Partial failure: record `None` / the typed error, never fabricate a fallback.** DNS timing
  out yields an empty record list *and* a logged reason — not a guessed value, not a crash.
- **Typed exceptions with reason codes**, not message strings. `TechScopeError` base;
  `FetchError(domain, reason: BlockReasonEnum | FailureReasonEnum)`, `FingerprintLoadError(
  technology, pattern)`. Tests assert on the reason code, not on text.
- **Never bare `except:`, never `except Exception: pass`.** Catch the specific `httpx` / `dns`
  exceptions at the I/O edge and turn them into the typed error on the result.
- **Don't raise when you are already reporting.** Once the pipeline has logged a domain's failure
  and recorded it on the result, it does not also raise. Only real failures go into the failure
  list — "no detections" is not a failure.
- **Regexes compiled once at load time** with `re.IGNORECASE`. A pattern that fails to compile is
  a `FingerprintLoadError` naming the technology — never skipped.

## Output

- Deterministic: domains in input order, technologies sorted by name, no duplicates, JSON
  `indent=2, ensure_ascii=False`, trailing newline.

## Dependencies

Runtime: `httpx`, `dnspython`. Dev: `pytest`, `pytest-asyncio`, `respx`, `ruff`, `mypy`.
Anything else needs a reason in the feature's design note. No pydantic, no typer — stdlib
dataclasses and argparse are enough and keep the reviewer's install trivial.
