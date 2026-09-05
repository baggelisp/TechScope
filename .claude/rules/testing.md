# Testing

- **Framework:** `pytest` with `pytest-asyncio` (`asyncio_mode = "auto"`). Run offline tests with
  `uv run pytest` (default excludes `live`); `make check` runs them.
- **TDD is mandatory.** Use `superpowers:test-driven-development`: write the failing test, watch it
  fail, write the minimum code, watch it pass, refactor. Never write implementation first and
  backfill tests.
- **No network in unit tests.** Ever. HTTP goes through `respx` mocks against `httpx`; DNS goes
  through a fake resolver implementing the `Resolver` protocol; use cases are tested with fake
  `SignalCollector`s and an in-memory `FingerprintRepository`. A unit test that reaches the
  internet is a bug.
- **Test layout mirrors the source layers:** `tests/unit/domain/`, `tests/unit/application/`,
  `tests/unit/infrastructure/`, `tests/unit/presentation/`. Domain tests import nothing from
  `infrastructure`.
- **Architecture is a test.** `tests/unit/test_architecture.py` parses every module under
  `src/techscope` with `ast` and asserts the import table in `.claude/rules/architecture.md`.
  It is part of `make check`; never mark it xfail.
- **Docker is not a unit test.** `make docker-scan` is an e2e-only check (feature 8 onwards);
  `make check` never needs Docker.
- **Fixtures are files, not strings.** Recorded HTML / header sets / DNS answers live in
  `tests/fixtures/<domain-or-case>/` and are small (trim pages to the relevant parts). Name them
  after what they demonstrate (`shopify_storefront.html`, `cloudflare_block_403.html`).
- **Every fingerprint in `technologies.json` has at least one positive and one negative test**
  in `tests/unit/domain/test_matcher.py` — a signal that must match and a near-miss that must
  not (e.g. `js.stripe.com/v2` for the Stripe `v3` pattern).
- **Every extractor has:** empty input → no signals; malformed input (broken HTML, header with
  no value, cookie without `=`) → no exception; the assignment's own example → expected signal.
- **Fetch layer tests cover:** 301 → 200 chain, https failing then http succeeding, timeout,
  connection error, 403/429/503 soft blocks, a challenge page with 200 status, oversized body.
- **Use-case tests cover:** one collector failing does not lose the other's signals; one domain
  failing does not affect others; output contains every input domain in order; concurrency
  limit is respected; total wall time under fake slow collectors.
- **Assertion quality:** assert the actual detections / signals, not "did not raise". Parametrize
  instead of copy-pasting. No snapshot tests of whole JSON blobs — assert the specific keys.
- **Live tests** (`tests/live/`) are marked `@pytest.mark.live`, deselected by default, and are
  what `make e2e` / the `e2e-cli-run` skill use. They may be flaky by nature; they never gate
  `make check`.
- **Assert on reason codes, not messages.** `assert result.error.reason is BlockReasonEnum.CHALLENGE_PAGE`,
  never a substring of a message string.
- **Tests follow the house style too:** descriptive names, no single-letter loop variables,
  parametrize IDs that read as sentences, no logic in tests (no `if` in a test body).
- **Test naming:** `test_<unit>_<condition>_<expected>` e.g.
  `test_matcher_stripe_v2_script_does_not_match`.
