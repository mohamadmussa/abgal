#!/bin/bash
# Registers and starts the runner already sitting in /runner, abgal's bind
# mount of the tarball it fetched on the host. Runs in the foreground so the
# container's own lifecycle is the runner's lifecycle, there is no svc.sh or
# systemd inside a container.
set -euo pipefail

cd /runner
./config.sh --url "$RUNNER_URL" --token "$RUNNER_TOKEN" --name "$RUNNER_NAME" \
    --labels "$RUNNER_LABELS" --unattended --replace --work _work
exec ./run.sh
