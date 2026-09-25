#!/usr/bin/env bash
# The one gate, the same steps CI runs. Stops at the first red one.
#   tools/run-all.sh            staged files only, what a commit needs
#   tools/run-all.sh --all      every tracked file, what CI checks on a push
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
exec python3 "$root/tools/run_all.py" "$@"
