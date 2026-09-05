---
name: e2e-cli-run
description: Use when asked to run the live end-to-end check of the TechScope CLI — how to run the real scan against the 20 assignment domains, enforce the 60 s budget, classify blocked domains, and diff output.json against the previous run. Invoked by /e2e and by /ship-next step 6.
---

# E2E — Live CLI Run

The only step in the loop that touches the real internet. It answers three questions: does the
tool finish in budget, does it survive hostile domains, and did detections change versus the
last shipped run.

## Precondition

`uv run techscope --help` works and `techscope scan` exists. If not: report
`E2E: n/a — CLI not scannable yet (backlog item N)` and stop. This is not a failure.

## Run

```bash
uv sync
/usr/bin/time -p uv run techscope scan docs/domains.txt -o output.json --log-level INFO 2> e2e.log
```

`docs/domains.txt` holds the 20 assignment domains — never edit it. `output.json` at the repo
root **is the submission artefact** and is committed with every feature that changes detections;
`e2e.log` is gitignored.

Run it **twice** if the first run is over 45 s or shows more than 3 blocked domains: the second
run separates real regressions from a transient network. Report both timings.

## Checks (all must hold; each failure maps to a severity)

| Check | Failure severity |
|---|---|
| Exit code 0 and `output.json` is valid JSON | CRITICAL |
| Every domain in `docs/domains.txt` is a key in `output.json` (in input order) | CRITICAL |
| Wall time (`real`) < 60 s — target < 30 s | CRITICAL |
| No Python traceback in `e2e.log` | CRITICAL |
| Each blocked / failed domain has one WARNING line in `e2e.log` with the reason | WARNING |
| Technologies sorted per domain, no duplicates | WARNING |

## Diff against the previous run

```bash
git diff origin/main -- output.json
```

For every technology that **disappeared** from a domain, explain it in the PR body: was the
domain blocked this time (check `e2e.log`), was it a false positive fixed on purpose, or is it a
regression (→ fix before shipping)? New detections are also listed and sanity-checked against
the accuracy rule: name the signal that produced each one (e.g. "`cf-ray` header"). If you cannot
name the signal, treat it as a false positive.

## Blocked-domain policy

A soft-blocked domain is expected on some of the 20 (Cloudflare / bot managers). It must still
appear in the output with whatever DNS/header evidence survived. Never work around a block by
spoofing a browser, adding cookies, or fetching through a proxy — that is out of scope for the
assignment and against `network-etiquette.md`.

## Report format (goes into the PR "Verification" section)

```
E2E: <PASS/FAIL>
Runtime: <real seconds> (second run: <s>)   budget 60 s
Domains: 20/20 in output
Blocked/failed: <domain — reason>, …
Detections: +<n> new (<domain: tech via signal>, …), −<n> lost (<domain: tech — reason>, …)
```
