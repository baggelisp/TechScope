---
description: Review the current branch diff (or a PR number) with the reviewer agent; escalate to the specialist panel when triggers fire.
---

# Review

Target: `$ARGUMENTS` if given (a PR number), else the working diff `git diff origin/main...HEAD`
plus untracked files.

## 1. Single-pass gate

Dispatch the `reviewer` agent with the target. It returns PASS / WARNINGS / CRITICAL plus an
optional "Escalation recommended" line.

## 2. Escalate only when asked

Run the panel **only** if the reviewer recommended escalation, or the user asked for a "deep
review". The panel is:

1. In parallel, one agent each: `correctness-reviewer`, `edge-case-hunter`,
   `test-coverage-analyst`. Give each the diff plus only the cross-file context it references.
2. Collect every candidate finding. For each one, dispatch `adversarial-verifier` with **only the
   claim and file:line** (never the finder's reasoning). Drop REFUTED. PLAUSIBLE below 0.7
   confidence goes to "For human attention".
3. Merge survivors with the single-pass report, ranked by blast radius (wrong result / crash /
   budget breach / accuracy regression > missing risky-path test > style).

## 3. Report

Use the reviewer's report format verbatim. Every CRITICAL carries the empirical check that
confirmed it (test run, grep, or a reproduction command). State clearly when the diff is clean.
