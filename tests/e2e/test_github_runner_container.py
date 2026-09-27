"""A real container backend runner, created and removed against a real repo.

Runs the real abgal binary as its own process, with the real docker or
podman on this machine, pulling or building the real image and registering
against GitHub for real. What changes between runs, the repo, comes from
ABGAL_E2E_RUNNER_REPO, never hard coded here; a CI job sets it as a
variable. The token comes from gh, already logged in through a CI secret
or, locally, through the developer's own login, same as a normal
abgal github-runner create. Skipped, not failed, without the repo set, so
a plain ABGAL_E2E=1 run elsewhere never needs it.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

REPO = os.environ.get("ABGAL_E2E_RUNNER_REPO")

pytestmark = pytest.mark.skipif(
    not REPO, reason="set ABGAL_E2E_RUNNER_REPO to a repo this account can register a runner on")


def run_abgal(*args):
    return subprocess.run([sys.executable, str(ROOT / "abgal")] + list(args),
                          capture_output=True, text=True, timeout=180)


def test_container_backend_registers_runs_and_deregisters():
    name = "abgal-e2e-%d" % os.getpid()
    try:
        created = run_abgal("github-runner", "create", "-n", name, "--repo", REPO,
                            "--backend", "container", "--labels", "self-hosted,linux,x64")
        assert created.returncode == 0, created.stdout + created.stderr

        status = run_abgal("github-runner", "status", "-n", name, "--wait", "60")
        assert status.returncode == 0, status.stdout + status.stderr
        assert " up " in status.stdout

        log = run_abgal("github-runner", "log", "-n", name)
        assert "listening for jobs" in log.stdout.lower()
    finally:
        removed = run_abgal("github-runner", "remove", "-n", name)
        assert removed.returncode == 0, removed.stdout + removed.stderr
