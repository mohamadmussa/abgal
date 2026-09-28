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
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

REPO = os.environ.get("ABGAL_E2E_RUNNER_REPO")

pytestmark = pytest.mark.skipif(
    not REPO, reason="set ABGAL_E2E_RUNNER_REPO to a repo this account can register a runner on")


def run_abgal(*args):
    return subprocess.run([sys.executable, str(ROOT / "abgal")] + list(args),
                          capture_output=True, text=True, timeout=180)


def wait_for_registration(name, timeout=30):
    """Polls the log until it reports listening.

    status --wait only reports the container process as up, which happens
    before config.sh inside it has finished registering, so a single log
    read right after status can still catch it mid registration.
    """
    deadline = time.time() + timeout
    log = run_abgal("github-runner", "log", "-n", name)
    while "listening for jobs" not in log.stdout.lower() and time.time() < deadline:
        time.sleep(2)
        log = run_abgal("github-runner", "log", "-n", name)
    return log


def test_container_backend_registers_runs_and_deregisters():
    name = "abgal-e2e-%d" % os.getpid()
    try:
        created = run_abgal("github-runner", "create", "-n", name, "--repo", REPO,
                            "--backend", "container", "--labels", "self-hosted,linux,x64")
        assert created.returncode == 0, created.stdout + created.stderr

        status = run_abgal("github-runner", "status", "-n", name, "--wait", "60")
        assert status.returncode == 0, status.stdout + status.stderr
        assert " up " in status.stdout

        log = wait_for_registration(name)
        assert "listening for jobs" in log.stdout.lower(), log.stdout + log.stderr
    finally:
        removed = run_abgal("github-runner", "remove", "-n", name)
        assert removed.returncode == 0, removed.stdout + removed.stderr
