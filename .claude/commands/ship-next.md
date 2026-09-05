---
description: Run the full analyse → TDD implement → review → e2e → commit → push → PR cycle for the next feature in docs/backlog.md, then stop.
---

# Ship Next Feature

Deliver **one** feature from `docs/backlog.md` end-to-end and stop with an open PR.
`$ARGUMENTS` may name a backlog number to run instead of the next unchecked one; otherwise pick
the first item whose status is `[ ]`.

This is a loop body: it must be safe to run repeatedly (e.g. via `/loop 15m /ship-next`). Every
preflight failure is a clean stop with a one-paragraph explanation, never a partial feature.

## 0. Preflight — stop cleanly if any fails

1. Read `CLAUDE.md`, `.claude/rules/*.md`, `assigment/assigment.md`, `docs/backlog.md`, and the spec in
   `docs/superpowers/specs/`.
2. `gh auth status` must show `baggelisp` as the active account. Otherwise stop: "gh is logged in
   as <account>; run `gh auth login` / `gh auth switch --user baggelisp`."
3. Working tree must be clean (`git status --porcelain` empty). Otherwise stop and list the files.
4. **Previous feature settled?** Find backlog items with status `[~]` (in PR). For each, run
   `gh pr view <number> --json state,mergedAt`.
   - If merged: mark it `[x]` in the backlog (this edit is committed as part of *this* feature's
     PR, on this feature's branch — not on main).
   - If still open: stop. "Feature N is waiting for merge at <url>. Merge it, then rerun."
   - If closed without merge: stop and ask the user what to do.
5. `git fetch origin main`. If the local `main` exists, it is never edited; branches come from
   `origin/main`.
6. Pick the feature. If none remain, stop: "Backlog complete."

## 1. Branch

```bash
git switch -c feat/NN-<slug> origin/main
```

## 2. Analyse (design note — no code yet)

Write a short design note **in your reply** (it becomes the PR "Design notes" section):

- Restate the feature's acceptance criteria from the backlog.
- List the files to create/modify, matching the layout in CLAUDE.md.
- State the approach and one rejected alternative with the reason.
- List the test cases you will write first (names, per `.claude/rules/testing.md`).
- Flag any assignment constraint the feature touches (60 s budget, no headless, accuracy).

Use `superpowers:brainstorming` judgement here but do **not** wait for user approval — the backlog
item was approved when the backlog was; this step only makes the plan explicit. If the note
reveals the feature is under-specified or bigger than one PR, stop and ask instead of guessing.

## 3. Implement with TDD

Invoke `superpowers:test-driven-development` and follow it strictly: failing test → minimal code →
green → refactor. Keep the core pure and inject I/O (see `python-style.md`).
Update `README.md` for anything user-visible (new flag, new channel, install step) and
`docs/backlog.md` (set this item to `[~]`, PR number filled in at step 7).

## 4. Quality gate

```bash
make check
```

Must be fully green. Fix, don't skip. If a tool is legitimately wrong, the exception is explicit
and commented, and mentioned in the PR body.

## 5. Code review

Run `/review` (which delegates to the `reviewer` agent, and the deeper panel when its escalation
triggers fire). Then:

- CRITICAL → fix, rerun step 4, rerun review. Repeat until no CRITICAL. Max 3 rounds; if still
  failing, stop and report.
- WARNING → fix if it is real and cheap; otherwise justify in the PR "Deferred" section.
- SUGGESTION → apply if it makes the code clearly better, else ignore.

Invoke `superpowers:receiving-code-review` when judging findings — verify before accepting.

## 6. E2E review

Run `/e2e`. It is `n/a` until the CLI can scan (backlog items 1–3 declare this). Otherwise it must
report: runtime for the 20 domains, blocked domains, and the `output.json` diff versus `main`.
Any *lost* detection versus the previous run must be explained (blocked this time? fixed a false
positive?) in the PR body. Any 60 s budget breach is a CRITICAL: fix before shipping.

## 7. Verify, commit, push, PR

Invoke `superpowers:verification-before-completion`: rerun `make check`, show the output.

```bash
git status --short            # review; stage by path only
git add <files...>
git commit -m "<conventional message per git-workflow.md>"
git push -u origin feat/NN-<slug>
gh pr create --base main --title "feat: NN — <title>" --body "<PR body per git-workflow.md template>"
```

Then put the PR number into the backlog line (`[~] … — PR #<n>`), amend nothing: make a second
small commit `docs(backlog): link PR #<n>` and push.

## 8. Stop and report

Final message, standing on its own:

- Feature number and title, PR URL.
- Verification summary (check counts, review status, e2e numbers).
- What the user must do: merge the PR, then run `/ship-next` again (or let `/loop` do it).
- Anything deferred.

Do **not** start the next feature.
