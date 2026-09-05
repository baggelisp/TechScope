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
| Matching signals against fingerprints | backlog 3 |
| HTTP fetch, response channels | backlog 4–5 |
| DNS and JavaScript-global channels | backlog 6–7 |
| Concurrency and the run budget | backlog 8 |

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
