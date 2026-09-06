# TechScope

A technographic scanner. Given a list of domains it fetches each homepage over plain HTTP, reads
signals out of eight channels, matches them against Wappalyzer-format fingerprints, and writes
which technologies each domain uses.

```json
{
  "shopify.com": ["Cloudflare", "Google Workspace", "SendGrid", "Shopify"],
  "sentry.io": ["Google Workspace", "SendGrid"],
  "loom.com": []
}
```

No headless browser and no paid API. Everything comes from one HTTP request per domain plus DNS
records on the apex.

## Install

Requires [uv](https://docs.astral.sh/uv/). It fetches Python 3.13 itself.

```bash
brew install uv          # or: curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

## Run

```bash
uv run techscope scan docs/domains.txt -o output.json --details output.details.json
```

The input is one domain per line. Blank lines and `#` comments are skipped; schemes, a `www.`
prefix, paths, query strings, ports and trailing dots are stripped; duplicates are removed while
input order is kept. `python -m techscope` behaves identically.

| Flag | Default | Meaning |
|---|---|---|
| `-o`, `--output` | `output.json` | where the results go |
| `--details` | not written | a second file with the evidence, problems and timings behind every result |
| `--fingerprints` | the packaged set | a Wappalyzer-format JSON database to match against |
| `--nameserver` | the system resolver | DNS server to query, repeatable |
| `--concurrency` | `10` | domains scanned in parallel |
| `--timeout` | `15.0` | seconds allowed per domain |
| `--deadline` | `55.0` | seconds allowed for the whole scan |
| `--log-level` | `WARNING` | `DEBUG`, `INFO`, `WARNING` or `ERROR`, on stderr |

Exit codes: `0` success, `2` unusable arguments or input, `1` unexpected failure.

### In Docker

```bash
make docker-build
make docker-scan
```

The image carries only the virtual environment and runs as a non-root user. `make docker-scan`
mounts the repository at `/data`, so the domains file is read and the results are written back
into the working tree — the same output as the local run. Compose wraps the same command:

```bash
docker compose --profile cli run --rm scan
```

On Linux a bind mount keeps host ownership, so tell Compose which identity to run as:
`DOCKER_USER="$(id -u):$(id -g)" docker compose --profile cli run --rm scan`. `make docker-scan`
already does this.

The container runs the same code, but not necessarily on the same network, and the committed
`output.json` is a container run: 20 domains, 46 detections, no domain with a problem. Earlier
container runs did differ — one lost zendesk.com to its 15-second budget, a host that answers in
5.2 s from the host machine and 15.9 s from inside — and the details file said so rather than
reporting an empty result. A scan of the live internet is not byte-reproducible across
environments or across runs; what is reproducible is that every difference has a recorded
reason.

## Architecture decisions

A lightweight Clean/Hexagonal layout. The dependency arrow always points inward, and
`tests/unit/test_architecture.py` parses every module and fails the build if an import crosses a
boundary the wrong way — the boundary is a fact rather than a convention.

```
presentation/cli.py ──► bootstrap.py ──► application/use_cases ──► domain
                             │                     │                  ▲
                             │                     ▼                  │
                             └──────────► application/ports ◄── infrastructure
```

| Layer | Holds | Knows about |
|---|---|---|
| `domain` | the vocabulary and the matching logic, pure | nothing |
| `application` | use cases, the ports they depend on, and the output presenters | the domain |
| `infrastructure` | HTTP, DNS, extractors, the fingerprint repository, writers | the domain, the ports, the presenters |
| `presentation` | the CLI | the domain, the application, the composition root |
| `bootstrap.py` | the composition root, the only place an adapter is constructed | everything but the drivers |

Four decisions did most of the work.

**One abstraction for every signal.** Whatever collected it — a response header, a cookie, a
script URL, a meta tag, a JavaScript global, a DNS record — it becomes the same record:
`Signal(channel, value, key)`. The matcher never learns where a signal came from, so adding a
source is a new adapter plus one line in the composition root, and the matching core is tested
entirely from fixtures because it has no I/O at all.

**Fingerprints are data, never code.** There is no technology-specific branch anywhere in the
Python. Adding a technology is an entry in a JSON file. That is measured, not asserted: the
complete upstream Wappalyzer database of 7,613 technologies loads through this repository in
0.4 s, producing 13,373 patterns across all ten channels, with no code change. Point
`--fingerprints` at any such file to use it.

**Keys are matched end to end.** Upstream fingerprint keys are literal header and cookie names,
but the assignment's are regex-shaped (`X-Stripe-.*`, `^intercom-`), so a key is compiled as a
case-insensitive regex — a strict superset, since a literal name is a valid regex. It is matched
with `fullmatch`, and that detail matters: over the 7,894 keyed patterns of the full upstream
database, cross-technology key collisions number 883 under `search`, 199 under `match` and 3
under `fullmatch`. Unanchored, the F5 BigIP cookie key `TIN` matches the ordinary WordPress
cookie `wp-settings-time-1`, and every WordPress site is reported as running F5 BigIP.

**A block is evidence, not an error.** A host that answers 403, rate-limits, or serves a
challenge page still tells us something, and its response headers are still collected — a
Cloudflare challenge is itself proof of Cloudflare. Blocks are classified, logged with a reason,
and the domain keeps whatever it yielded.

## Accuracy: what it will and will not report

A technology is reported only when a pattern matched a signal that was really observed, and every
detection carries the evidence that produced it. Nothing is inferred from a company name or a
domain name: `stripe.com` is reported as using Stripe because the response carries an
`X-Stripe-…` header, not because of what it is called.

Two decisions this cost, both taken deliberately, and both settled by measurement rather than
argument.

**A script URL counts only where the page really loads it, in a `src` attribute.** Several
vendors are loaded instead by a snippet that writes the URL from JavaScript, and on the
assignment's own domains Segment, Zendesk and Sentry are invisible for that reason. Matching the
URL anywhere in script text would find all three — and it also reported Sentry on sentry.io,
where the only occurrence is a code sample inside the page's own onboarding documentation. A
false positive is worse than a miss, so the narrower rule stands.

**Only executable script is script.** A `<script>` whose type is `application/json`,
`application/ld+json` or `text/template` is page data. Every server-rendered framework serialises
a page's own editorial copy into exactly those, so treating them as code matches vendor URLs in
prose.

`output.json` is the shape the assignment asks for, and it has one blind spot: a domain that runs
nothing detectable and a domain that refused to answer are both an empty list. `--details` is
where that difference lives.

The `pattern` is what the fingerprint asked for and `matched` is what the page actually had —
for a keyed channel like a header, the pattern names the header and the match is its value.

```json
{
  "domain": "shopify.com",
  "observed_url": "https://www.shopify.com/",
  "duration_seconds": 1.428,
  "technologies": ["Cloudflare", "Google Workspace", "SendGrid", "Shopify"],
  "detections": [
    {"name": "Cloudflare", "confidence": 100,
     "evidence": [{"channel": "header", "key": "cf-cache-status",
                   "pattern": "cf-cache-status", "matched": "BYPASS"}]}
  ],
  "problems": []
}
```

A domain cut short by the deadline reports `duration_seconds: null` rather than a fabricated
zero. One presenter produces both shapes, so the file and a future HTTP API cannot drift.

## The channels

| Channel | Read from | Fingerprint key |
|---|---|---|
| headers | every response header | `headers` |
| cookies | the name and value of every `Set-Cookie` | `cookies` |
| script src | `<script src>`, kept exactly as written | `scriptSrc` |
| inline scripts | the body of every executable `<script>` | `scripts` |
| meta tags | `<meta name>` or `<meta property>` with content | `meta` |
| html | the raw response body | `html` |
| JavaScript globals | names inline scripts define, read statically | `js` |
| DNS | MX, TXT and CNAME on the apex | `dns` |

HTML is parsed once per response with a tolerant parser, never with a regex over the whole
document, and the parsed view is shared by every extractor: a 1.5 MB page costs a quarter of a
second to parse, and doing it per extractor would have spent that several times over.

The JavaScript channel reads names without running anything. Each script is first mapped to learn
which stretches are string, comment or regex-literal content and which are at the top level, and
names are taken only from real top-level code. That map is what keeps a documentation snippet
inside a string from being mistaken for the global it describes, and why a `var` inside a
function is correctly read as a local.

## Robustness

One request per host, ever: the homepage, following up to five redirects, `https` first and
`http` only if the connection itself failed. Connect 5 s, read 10 s, and one `asyncio.timeout`
bounding the whole attempt including its retry, so no arrangement of attempts can exceed a
domain's budget. Bodies are streamed and capped at 2 MB, decoded by the declared charset with
replacement. The scanner identifies itself honestly and detects a block rather than trying to
evade one.

DNS uses two bounds rather than one: 1 s per nameserver attempt, 5 s for the whole lookup. A
large TXT answer is truncated over UDP and must be retried over TCP, and a single budget let one
slow nameserver consume it first — with it, four of fifteen lookups returned nothing where `dig`
confirms records exist. Lookups are also capped at ten in flight across the run, because a
resolver asked for thirty at once starts dropping them: unbounded, the assignment's domains
returned 661 to 676 records and a different number every run; bounded, 749 and faster.

One domain can never cost another. Each collector is isolated, each domain is isolated, and a
domain cut short by the whole-scan deadline still appears in the output saying so.

## Known limitations

- **A domain that redirects to another company is scanned as that company.** Acquisitions do
  this: in the committed run, drift.com serves salesloft.com, so its HTTP detections describe
  Salesloft's page and only its DNS detections describe drift.com itself. Which domains do it
  varies between runs: segment.com and sendgrid.com sometimes serve twilio.com and sometimes
  themselves, and hotjar.com sometimes serves contentsquare.com. The tool follows redirects
  because the assignment asks it to, and it records `observed_url` per domain in the details
  file, so the substitution is visible in every run rather than silent.
- **DNS is the only part of a run that does not reproduce exactly.** Repeated runs here returned
  between 713 and 749 records depending on the local resolver, while a public one returned 749
  every time and fifteen times faster. `--nameserver` is the lever.
- **Loader-injected vendors are missed.** Segment, Zendesk and Sentry are not detected on their
  own domains, for the reason above. The channel that would find them properly is `window.*`
  globals, and the fingerprint set the assignment supplies contains no `js` patterns.
- **A global's value is never known**, so an upstream `js` pattern that constrains the value,
  usually to extract a version, cannot match. Knowing it would mean running the script.
- **The apex is not guessed.** A `www.` prefix is stripped and nothing else: reducing
  `blog.example.com` to `example.com` needs a public suffix list, and guessing wrong attributes
  another organisation's DNS. `myblog.wordpress.com` would become `wordpress.com`, whose mail
  records belong to Automattic. A domain below the registrable level yields fewer DNS signals —
  a miss rather than a wrong answer.
- **An unclosed inline `<script>` swallows the rest of the document.** Browsers do the same, so
  such a page is broken for everyone, but later tags are lost rather than merely unparsed.
- **The deadline bounds the scan, not the process.** Work already handed to a worker thread
  cannot be cancelled, so the interpreter waits for it on the way out. Today that is one HTML
  parse over a capped body.

## Security notes

Three sentences hold the whole model. This scanner fetches pages it does not control; it never
executes them; and every resource they can consume is bounded.

Five guards make that true, each with its own test against a hostile fixture.

**Targets are checked on every redirect hop, not only the first.** A name someone else chose
becomes an outbound request from this host, so before each request the name is resolved and
refused if any address is not public: loopback, private ranges, link-local — including the
`169.254.169.254` metadata address — unique local addresses, and any scheme that is not `http`
or `https`. Redirects are followed by this code rather than by the HTTP library precisely so
that each hop passes the same check.

**The connection goes to the address that was checked.** A name is not what a socket connects
to, and a check that does not bind the connection describes an answer nobody is held to. Two
gaps follow from that, and both are closed here. The host is punycode-encoded once, with the
same library the HTTP client uses, because the resolver's IDNA 2003 folds `straße` to `strasse`
while the client's IDNA 2008 encodes it to `xn--strae-oqa`, and an attacker who owns both names
is otherwise checked on one and fetched on the other. Then the approved addresses travel with
the approval down to where a name becomes a socket, so a nameserver that answers publicly to the
check and privately to the connection has nowhere to put the second answer. The name is still
what the `Host` header and the certificate check see, and one address per family is approved so
that a host stays reachable from a container with no IPv6 route. Independently of all of that,
the address a response actually arrived from is checked before its body is read.

**Regexes compiled from data are checked for catastrophic backtracking.** Fingerprints are
untrusted input run against untrusted pages, and Python's `re` has no timeout, so `(a+)+$`
against a long run of `a` outlasts any deadline. A group that repeats without bound is refused at
load time, as an error naming the technology, when nothing in its body anchors one repetition
against the next, when one alternative begins with another, or when a branch can grow without
limit. Every spelling of a shape has to be read as that shape, because a rule that catches only
one of them is a rule an attacker writes around: `{1,}` is `+`, and `(?P<name>…)` and `(?i:…)`
are groups like any other. The rule is narrow on purpose — it refuses all fourteen catastrophic
shapes tested and none of the 44,980 pattern texts and keys in the full upstream database — and
the matcher separately caps what any one pattern may be run against, rather than trusting its
caller to have done it.

**Every read is bounded in decoded bytes.** The 2 MB body cap counts what came out of the
decompressor, not what came in: a 50 KB gzip bomb that expands to 50 MB stops at the cap. Each
domain has a 15-second bound including retries, the whole scan has a deadline, and both the
domain fan-out and the DNS lookups are capped in flight.

**Nothing hostile reaches our own output.** Text quoted from a page as evidence is truncated and
stripped of control characters — NUL, terminal escapes, and the bidirectional overrides that
make text display in an order it was not written in — because that evidence ends up in a
terminal, a JSON file and, later, a web page.

The container runs non-root, read-only, with all capabilities dropped and `no-new-privileges`;
`make docker-scan` passes those flags. `pip-audit` over the lockfile reports no known
vulnerabilities.

Two limits worth stating rather than hiding. Pinning a connection to a checked address is
done by substituting the address at the HTTP library's network layer, which means reaching for
one attribute that library does not document; the code refuses to build a client at all if that
attribute ever moves, so the failure is a startup error and never a silently unpinned
connection. And when a network-facing driver is added, none of the above may be relaxed for it:
it is the driver that turns a stranger's input into our outbound requests, so the domain list it
accepts must be bounded in length and normalised through the same parser the CLI uses.

## Extending it

**A new fingerprint** is an entry in
`src/techscope/infrastructure/repositories/data/technologies.json`, in the upstream Wappalyzer
shape. The loader understands the confidence and version modifiers and ignores keys this scanner
cannot observe over plain HTTP. Anything present but unusable — a regex that will not compile, a
confidence outside 0 to 100 — is an error naming the technology, because a silently dropped
pattern looks exactly like a technology that is not in use.

**A new signal source** is a class with `name` and `async collect(domain) -> CollectionResult`,
plus one line in `bootstrap.py`. Nothing else changes: the use case does not tell its collectors
apart, and the matcher never learns where a signal came from. A TLS certificate collector or a
`robots.txt` collector would touch no existing file.

**A new response channel** is one module under `infrastructure/extractors/` and one entry in that
package's registry.

## Development

```bash
make check    # ruff, format check, mypy --strict, and the offline tests
make fmt      # format and apply safe lint fixes
make e2e      # timed live scan of the 20 assignment domains
```

490 tests, none of which touch the network: HTTP goes through `respx`, DNS through injected
fakes, and an autouse fixture makes a real nameserver unreachable from any unit test. Every
shipped fingerprint has a positive case and a near-miss that must not match, and a test fails the
build if any pattern has no case exercising it.

## Assignment checklist

| Requirement | Where |
|---|---|
| Plain-text file of domains, one per line | `docs/domains.txt`, parsed by `domain/domain_list.py` |
| Fetch each homepage; redirects, timeouts, soft blocks | `infrastructure/http/homepage_fetcher.py` |
| At least four signal channels | eight: headers, cookies, script src, inline scripts, meta, html, JavaScript globals, DNS |
| Wappalyzer pattern format, extensible to the full database | `infrastructure/repositories/`, verified against all 7,613 upstream entries |
| Matching logic implemented here, not a dependency | `domain/matcher.py` |
| Structured JSON output | `output.json`, plus `output.details.json` |
| 20 domains in under 60 seconds | 6.7 s of scanning, 7.2 s wall |
| Never crash on a bad domain | every domain appears in the output, whatever happened to it |
| No headless browser, no paid API | one HTTP request and three DNS queries per domain |

`output.json` and `output.details.json` are the real results of one run against the twenty
domains in `docs/domains.txt`, taken through the machine's own system resolver rather than a
named one. The details file records that run's own summary: 20 domains, 45 detections across 19
of them, no domain with problems, 6.7 seconds of scanning. Every detection in it carries the
channel, the pattern and the text that matched, and every one of the 45 has at least one.

The measurements quoted in this README about the full upstream Wappalyzer database — 7,613
technologies, 13,373 patterns, the 0.4 s load and the key-collision counts — were taken by
loading that database through this repository with `--fingerprints`. It is not vendored here, so
those figures are recorded rather than re-checked by the test suite; everything about the shipped
fingerprint set is.
