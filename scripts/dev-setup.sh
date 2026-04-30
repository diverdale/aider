#!/bin/bash

# Bootstrap local contributor setup for git hooks.
# Usage:
#   ./scripts/dev-setup.sh
#   ./scripts/dev-setup.sh --run-all

set -euo pipefail

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
    echo "Error: must be run from inside a git repository." >&2
    exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

RUN_ALL=0
if [[ "${1:-}" == "--run-all" ]]; then
    RUN_ALL=1
elif [[ -n "${1:-}" ]]; then
    echo "Unknown argument: $1" >&2
    echo "Usage: ./scripts/dev-setup.sh [--run-all]" >&2
    exit 1
fi

if command -v uvx >/dev/null 2>&1; then
    PRE_COMMIT_CMD=(uvx pre-commit)
elif command -v pre-commit >/dev/null 2>&1; then
    PRE_COMMIT_CMD=(pre-commit)
else
    echo "Error: neither 'uvx' nor 'pre-commit' was found in PATH." >&2
    echo "Install one of them and re-run this script." >&2
    exit 1
fi

echo "Installing pre-commit git hook..."
"${PRE_COMMIT_CMD[@]}" install

echo "Pre-commit hook installed."

if [[ "$RUN_ALL" -eq 1 ]]; then
    echo "Running all pre-commit hooks..."
    "${PRE_COMMIT_CMD[@]}" run --all-files
    echo "All hooks completed."
fi

echo "Done."
