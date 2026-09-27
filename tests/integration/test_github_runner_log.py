"""abgal github-runner log, the runner's own log.

subprocess.run is replaced for the container backend, so no real docker or
podman runs. The host backend reads a real file under a fake runners/ tree.
"""

import argparse
import os
from types import SimpleNamespace

import pytest

import abgal


@pytest.fixture
def runners(tmp_path, monkeypatch):
    monkeypatch.setattr(abgal, "RUNNERS", tmp_path / "runners")
    return tmp_path / "runners"


def done(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def args(name, lines=200):
    return argparse.Namespace(name=name, lines=lines)


def test_log_with_no_state_fails(runners, capsys):
    assert abgal.cmd_github_runner_log(args("ghost")) == 1
    assert "No runner named ghost" in capsys.readouterr().out


def test_log_host_backend_reads_diag_and_reports_ready(runners, capsys):
    abgal.write_runner_state("ci-01", {"name": "ci-01", "backend": "host"})
    diag = runners / "ci-01" / "_diag"
    diag.mkdir(parents=True)
    (diag / "Runner_20260927.log").write_text("starting\nConnected\nListening for Jobs\n")

    assert abgal.cmd_github_runner_log(args("ci-01")) == 0

    out = capsys.readouterr().out
    assert "Listening for Jobs" in out
    assert "is listening for jobs" in out


def test_log_host_backend_uses_the_newest_diag_file(runners, capsys):
    abgal.write_runner_state("ci-01", {"name": "ci-01", "backend": "host"})
    diag = runners / "ci-01" / "_diag"
    diag.mkdir(parents=True)
    older = diag / "Runner_20260101.log"
    newer = diag / "Runner_20260927.log"
    older.write_text("old attempt, failed\n")
    newer.write_text("Listening for Jobs\n")
    # mtime, not file name order, is what runner_log_lines sorts by.
    past = newer.stat().st_mtime - 100
    os.utime(older, (past, past))

    out = "\n".join(abgal.runner_log_lines(abgal.read_runner_state("ci-01"), 200))

    assert "Listening for Jobs" in out
    assert "failed" not in out


def test_log_container_backend_uses_engine_logs(runners, monkeypatch, capsys):
    abgal.write_runner_state("ci-02", {"name": "ci-02", "backend": "container", "engine": "podman"})
    monkeypatch.setattr(abgal.subprocess, "run",
                        lambda *a, **k: done(stdout="starting\nListening for Jobs\n"))

    assert abgal.cmd_github_runner_log(args("ci-02")) == 0

    assert "Listening for Jobs" in capsys.readouterr().out


def test_log_with_nothing_yet_fails(runners, capsys):
    abgal.write_runner_state("ci-01", {"name": "ci-01", "backend": "host"})

    assert abgal.cmd_github_runner_log(args("ci-01")) == 1
    assert "No log found" in capsys.readouterr().out
