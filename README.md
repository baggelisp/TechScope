# TechScope

A technographic scanner: given a list of domains it fetches each homepage over plain HTTP,
extracts signals from several channels, matches them against Wappalyzer-format fingerprints and
writes which technologies each domain uses.

```json
{
  "stripe.com": ["Cloudflare", "Stripe"],
  "notion.so": ["Amplitude", "Segment"]
}
```

No headless browser and no paid API: everything comes from one HTTP response per domain plus DNS
records on the apex.

## Status

The scaffold is in place — CLI, layered architecture, quality gate and container. Detection
itself lands feature by feature (`docs/backlog.md`); until then every domain reports an empty
technology list.

| Capability | State |
|---|---|
| Domain file parsing, CLI, JSON output | done |
| Fingerprint loading, Wappalyzer format | done |
| Matching signals against fingerprints | done |
| HTTP fetch, response channels | backlog 4–5 |
| DNS channel, bounded concurrency | done |
| JavaScript-global channel | done |
| Run deadline and structured output | backlog 8 |

## Install

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13 (uv fetches the interpreter itself).

```bash
brew install uv          # or: curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

## Run

```bash
uv run techscope scan docs/domains.txt -o output.json
```

Options on the `scan` command:

| Flag | Default | Meaning |
|---|---|---|
| `-o`, `--output` | `output.json` | where the results JSON is written |
| `--fingerprints` | the packaged set | a Wappalyzer-format JSON database to match against |
| `--concurrency` | `10` | domains scanned in parallel (applied from backlog 8) |
| `--timeout` | `15.0` | seconds allowed per domain (applied from backlog 8) |
| `--log-level` | `WARNING` | verbosity on stderr: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

The input file is one domain per line. Blank lines and `#` comments are skipped; schemes, a
`www.` prefix, paths, query strings and ports are stripped; duplicates are removed while input
order is kept. `python -m techscope` works the same way as the console script.

Exit codes: `0` success, `2` unusable arguments or input file, `1` unexpected failure.

## Run in Docker

```bash
make docker-build
make docker-scan
```

The image carries only the virtual environment and runs as a non-root user. `make docker-scan`
mounts the repository at `/data`, so the domains file is read and `output.json` is written back
into the working tree — the same result as the local run. Compose wraps the same command:

```bash
docker compose --profile cli run --rm scan
```

On Linux a bind mount keeps host ownership, so tell Compose which identity to run as:
`DOCKER_USER="$(id -u):$(id -g)" docker compose --profile cli run --rm scan`. `make docker-scan`
already does this for you.

## Development

```bash
make check    # ruff lint, format check, mypy --strict, offline tests
make fmt      # format and apply safe lint fixes
make e2e      # timed live scan of the 20 assignment domains
```

Unit tests never touch the network. `make check` must be green before anything ships.

## Architecture

A lightweight Clean/Hexagonal layout: the dependency arrow always points inward, and
`tests/unit/test_architecture.py` fails the build if any import crosses a boundary the wrong way.

```
presentation/cli.py ──► bootstrap.py ──► application/use_cases ──► domain
                             │                     │                  ▲
                             │                     ▼                  │
                             └──────────► application/ports ◄── infrastructure
```

| Layer | Holds | Knows about |
|---|---|---|
| `domain` | the vocabulary and the matching logic, pure | nothing |
| `application` | use cases and the ports they depend on | the domain |
| `infrastructure` | HTTP, DNS, extractors, fingerprint repository, writers | the domain and the ports |
| `presentation` | the CLI driver | the domain, the application, the composition root |
| `bootstrap.py` | the composition root, the only place adapters are constructed | everything but the drivers |

Two consequences worth stating up front: the matching core is tested entirely from fixtures
because it has no I/O, and a new signal source is a new adapter plus one line in the composition
root rather than a change to the scanner.

The full rules live in `.claude/rules/architecture.md`; the reasoning is in
`docs/superpowers/specs/2026-09-05-techscope-design.md`.

## Fingerprints are data

Technologies live in `src/techscope/infrastructure/repositories/data/technologies.json`, in the
upstream Wappalyzer shape. Adding one is a data change, never a code change. The loader reads
`headers`, `cookies`, `meta`, `js`, `scriptSrc`, `scripts`, `html` and `dns`, understands the
`\;confidence:N` and `\;version:X` modifiers, and ignores keys this scanner cannot observe over
plain HTTP such as `url`, `dom` and `xhr`. Anything present but unusable — a regex that will not
compile, a confidence outside 0–100 — is an error naming the technology, because a silently
dropped pattern looks exactly like a technology that is not in use.

That claim is measured rather than asserted: the complete upstream database of 7,613 technologies
loads through this repository in 0.4 s, producing 13,373 patterns across all ten channels with no
code change. Point `--fingerprints` at any such file to use it.

### DNS

Mail, verification and alias records are read from the apex, three record types at once, with
no more than ten lookups in flight across the whole run. That bound is not politeness theatre:
scanning twenty domains ten at a time means thirty simultaneous queries, and unbounded the
resolver returned 661 to 676 records and a different number on every run. Bounded, it returns
749 every time, and faster. Three consecutive scans now produce byte-identical output.

DNS is the one part of a scan that does not reproduce exactly. Repeated runs on this machine
returned between 713 and 749 records depending on how the local resolver was behaving, while a
public resolver returned 749 every time and fifteen times faster. The scanner does not choose one
for you; a run's DNS detections are as good as the resolver it was given.

A `www.` prefix is stripped, and nothing else is: reducing `blog.example.com` to `example.com`
needs a public suffix list, and guessing wrong attributes another organisation's DNS to this
one. `myblog.wordpress.com` would become `wordpress.com`, whose mail records belong to
Automattic. A domain below the registrable level therefore yields fewer DNS signals, which is a
miss rather than a wrong answer.

### JavaScript globals, without running anything

The sixth channel reads the names a page's inline scripts define — `window.Intercom = …`,
`window['analytics']`, a top-level `var` or `function` — by scanning script text. Nothing is
executed. Each script is first mapped to learn which stretches are string or comment content and
which are at the top level, and names are then read only out of real top-level code. That map is
what keeps a documentation snippet inside a string from being mistaken for the global it
describes, and it is why a `var` inside a function is correctly read as a local.

The fingerprint set the assignment supplies contains no `js` patterns, so this channel adds no
detections to `output.json`. It is not idle capability: pointed at the full upstream database
with `--fingerprints`, it finds six technologies on the assignment's own domains that the other
five channels miss, among them Optimizely and Marker on typeform.com, each from a global its
inline script really defines.

Two things it deliberately does not do. A bare `X = 1` is not read as a global, because without
a parser it cannot be told from a default parameter or a loop variable, and the short names it
would add collide with upstream keys. And a global's *value* is never known: an upstream `js`
pattern that constrains the value, usually to extract a version, cannot match, because knowing
the value would mean running the script — which is the one thing the assignment forbids.

### A limitation worth stating

A script URL is matched only where a page really loads it, in a `src` attribute. Several vendors
are loaded instead by a snippet that writes the URL from JavaScript, and on the assignment's own
domains Segment, Zendesk and Sentry are all invisible for that reason. Matching the URL anywhere
in script text would find them, and was tried — but it also reported Sentry on sentry.io, where
the only occurrence is a code sample inside the page's own onboarding documentation. Since a
false positive is worse than a miss, the narrower rule stands. The channel that would detect
these properly is `window.*` globals, and the fingerprint set the assignment supplies contains
no such patterns.
