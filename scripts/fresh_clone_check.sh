#!/usr/bin/env bash
# Verify the repository as a stranger receives it: clone the committed state into a temporary
# directory and build it there, with nothing from this working tree in scope. Catches files that
# are gitignored by accident, a lockfile that does not resolve, and README commands that only
# work because your .venv is already warm.
#
#   scripts/fresh_clone_check.sh [--ref <git-ref>] [--skip-docker] [--with-e2e] [--keep]
#
# Exit code 0 only if every check that ran passed and none was skipped without an explicit flag.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
REF="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)"
SKIP_DOCKER=0
WITH_E2E=0
KEEP=0

# Files a cloner must receive, and files they must never receive.
REQUIRED_PATHS=(
  README.md
  Makefile
  Dockerfile
  pyproject.toml
  uv.lock
  .python-version
  docs/domains.txt
  docs/backlog.md
  output.json
  output.details.json
  src/techscope/__main__.py
  src/techscope/infrastructure/repositories/data/technologies.json
)
FORBIDDEN_PATHS=(
  assigment
  .venv
  .env
  e2e.log
  .claude/settings.local.json
)

while [ $# -gt 0 ]; do
  case "$1" in
    --ref) REF="$2"; shift 2 ;;
    --skip-docker) SKIP_DOCKER=1; shift ;;
    --with-e2e) WITH_E2E=1; shift ;;
    --keep) KEEP=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

WORK="$(mktemp -d "${TMPDIR:-/tmp}/techscope-freshclone.XXXXXX")"
CLONE="$WORK/TechScope"
FAILURES=()
PASSES=()

cleanup() {
  if [ "$KEEP" -eq 1 ]; then
    echo ""
    echo "clone kept at $CLONE"
    return
  fi

  rm -rf "$WORK"
}
trap cleanup EXIT

record_step() {
  local label="$1"
  shift

  echo ""
  echo "── $label"

  if "$@"; then
    PASSES+=("$label")
    return 0
  fi

  FAILURES+=("$label")
  return 0
}

check_required_paths() {
  local missing=()

  for path in "${REQUIRED_PATHS[@]}"; do
    if [ ! -e "$CLONE/$path" ]; then
      missing+=("$path")
    fi
  done

  if [ ${#missing[@]} -gt 0 ]; then
    printf 'missing from the clone: %s\n' "${missing[*]}"
    return 1
  fi

  echo "all ${#REQUIRED_PATHS[@]} required paths present"
}

check_forbidden_paths() {
  local leaked=()

  for path in "${FORBIDDEN_PATHS[@]}"; do
    if [ -e "$CLONE/$path" ]; then
      leaked+=("$path")
    fi
  done

  if [ ${#leaked[@]} -gt 0 ]; then
    printf 'must not be committed: %s\n' "${leaked[*]}"
    return 1
  fi

  echo "no ignored path leaked into the commit"
}

check_docker() {
  if [ "$SKIP_DOCKER" -eq 1 ]; then
    echo "skipped by --skip-docker"
    return 0
  fi

  make -C "$CLONE" docker-build IMAGE=techscope:freshclone
}

echo "fresh-clone check"
echo "  repo: $REPO_ROOT"
echo "  ref:  $REF"
echo "  into: $CLONE"

if ! git -C "$REPO_ROOT" diff --quiet HEAD; then
  echo ""
  echo "note: this working tree has uncommitted changes; they are NOT part of this check."
fi

git clone --quiet --branch "$REF" "$REPO_ROOT" "$CLONE"

record_step "committed files: required present" check_required_paths
record_step "committed files: ignored paths absent" check_forbidden_paths
record_step "uv sync --frozen (lockfile resolves)" env -C "$CLONE" uv sync --frozen --quiet
record_step "make check" make -C "$CLONE" check
record_step "console script runs" env -C "$CLONE" uv run techscope --help
record_step "python -m techscope runs" env -C "$CLONE" uv run python -m techscope --help
record_step "docker build" check_docker

if [ "$WITH_E2E" -eq 1 ]; then
  record_step "make e2e (live)" make -C "$CLONE" e2e
fi

echo ""
echo "───────────────────────────────"
printf 'passed: %d\n' "${#PASSES[@]}"

if [ "$SKIP_DOCKER" -eq 1 ]; then
  echo "skipped: docker build (--skip-docker)"
fi

if [ "$WITH_E2E" -eq 0 ]; then
  echo "skipped: live e2e (pass --with-e2e to include it)"
fi

if [ ${#FAILURES[@]} -gt 0 ]; then
  printf 'FAILED: %s\n' "${FAILURES[*]}"
  exit 1
fi

echo "fresh clone builds clean."
