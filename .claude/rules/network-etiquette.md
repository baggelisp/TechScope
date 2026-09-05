# Network Etiquette & Robustness

The tool talks to real, third-party websites. Be a polite, predictable client.

- **Identify honestly.** `User-Agent: TechScope/<version> (+https://github.com/baggelisp/TechScope)`
  plus a browser-like `Accept` / `Accept-Language`. Do not spoof a browser UA to evade blocks —
  detect the block and skip.
- **One fetch per domain.** The homepage only (`https://<domain>/`, following redirects up to 5).
  If https fails at the connection level, try `http://` once. No crawling, no asset fetching.
- **Timeouts are short and explicit:** connect 5 s, read 10 s, total per domain ≤ 15 s. The whole
  20-domain run must finish well under 60 s, so per-domain work must be bounded.
- **Concurrency is bounded** by an `asyncio.Semaphore` (default 10). DNS lookups run
  concurrently with the HTTP fetch for the same domain.
- **Soft blocks are data, not errors.** Treat 403 / 429 / 503, Cloudflare / Akamai / PerimeterX
  challenge pages (even with status 200), and empty bodies as `SoftBlocked`. Log at WARNING, keep
  whatever headers/DNS signals were still collectable (a Cloudflare block still proves Cloudflare),
  and move on.
- **Retry once** on transient network errors (connect error, read timeout) with a short backoff.
  Never retry a 4xx.
- **Cap the body** at 2 MB; stream and stop. Decode with the declared charset, falling back to
  utf-8 with `errors="replace"`.
- **Static JS only.** `window.*` globals are found by scanning inline `<script>` text and
  `<script src>` URLs with regexes. Never fetch external scripts, never execute anything.
- **DNS:** query MX, TXT, CNAME on the apex (`example.com`, not `www.example.com`) with a 3 s
  timeout each; `NXDOMAIN` / `NoAnswer` / timeout → empty list for that record type, logged at
  DEBUG.
- **Accuracy rule.** A detection needs a real signal match. Do not infer technologies from
  company names, domain names, or "the domain is stripe.com so Stripe is used". `implies` chains
  from fingerprints are allowed because they are data-driven.
