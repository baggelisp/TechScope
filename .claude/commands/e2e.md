---
description: Live end-to-end run of the CLI against the 20 assignment domains; checks the 60 s budget, blocked domains, and the output.json diff.
---

# E2E

Invoke the `e2e-cli-run` skill (`.claude/skills/e2e-cli-run/SKILL.md`) and follow it exactly.
`$ARGUMENTS` may be an alternative domains file; default is `docs/domains.txt`.

If the CLI cannot scan yet (no `techscope scan` entry point, or backlog says the feature is
pre-scanner), report `E2E: n/a — <reason>` and stop; this is not a failure.
