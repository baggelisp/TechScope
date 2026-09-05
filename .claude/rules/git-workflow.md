# Git Workflow

## One feature = one branch = one PR

- Branch from a **fresh `origin/main`**: `git fetch origin main && git switch -c feat/NN-slug origin/main`
  where `NN` is the backlog number (`feat/04-http-fetcher`).
- Never commit directly on `main`. Never push to `main`. Never merge a PR yourself — the user
  merges on GitHub (`gh pr merge` is denied in settings).
- Never force-push, never `reset --hard`, never `git clean`.
- **Stage by path.** Never `git add -A`, `git add .`, or `git commit -a`. Review `git status` and
  add exactly the files the feature touched.
- Do not start a feature while a previous feature's PR is still open. Say so and stop.

## Commit messages

Conventional commits, imperative mood, scoped to the module:

```
feat(fetch): add homepage fetcher with redirect and soft-block handling

- https first, http fallback on connection error
- treat 403/429/503 and known challenge pages as SoftBlocked
- FetchError carries domain + reason for the pipeline log

Refs docs/backlog.md #4
```

End with the Claude attribution trailers the session provides. One commit per feature is the
norm; a second "address review" commit is fine, but squash-worthy noise is not.

## Pull request body (template — fill every section)

```
## Feature N — <title>

Closes backlog item N (docs/backlog.md).

### What
<2–4 bullets>

### Design notes
<the analyse-step decisions: approach chosen, alternatives rejected, why>

### Verification
- `make check`: <pass, counts>
- `reviewer` agent: <PASS / WARNINGS with what was done about each>
- `/e2e`: <runtime for 20 domains, blocked domains, output.json diff summary> — or "n/a until feature N"

### Deferred / follow-ups
<anything consciously left out, or "none">
```

## Identity

Personal repo — see CLAUDE.md "Git identity". Before any `gh pr create`, `gh auth status` must
show `baggelisp` as the active account. If it doesn't, stop and tell the user.
