"""abgal github-runner status, local liveness only.

subprocess.run is replaced, so no real svc.sh, docker or podman runs. Only
the state file abgal itself would have written and the backend check are
exercised.
"""

import argparse
from types import SimpleNamespace

import pytest

import abgal


@pytest.fixture
def runners(tmp_path, monkeypatch):
    monkeypatch.setattr(abgal, "RUNNERS", tmp_path / "runners")
    return tmp_path / "runners"


def done(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def args(name=None, wait=0):
    return argparse.Namespace(name=name, wait=wait)


def write_service_file(runners, name, unit="actions.runner.myorg-myrepo.ci-01.service"):
    folder = runners / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ".service").write_text(unit + "\n")


def test_status_with_no_runners_reports_that(runners, capsys):
    assert abgal.cmd_github_runner_status(args()) == 0
    assert "This machine manages no runner." in capsys.readouterr().out


def test_status_with_an_unknown_name_fails(runners, capsys):
    assert abgal.cmd_github_runner_status(args(name="ghost")) == 1
    assert "No runner named ghost" in capsys.readouterr().out


def test_status_host_backend_up(runners, monkeypatch, capsys):
    abgal.write_runner_state("ci-01", {"name": "ci-01", "backend": "host", "version": "2.337.0"})
    write_service_file(runners, "ci-01")
    text = "Active: active (running) since Sat 2026-09-27 08:00:00 UTC; 2h 15min ago\n"
    monkeypatch.setattr(abgal.subprocess, "run", lambda *a, **k: done(stdout=text))

    assert abgal.cmd_github_runner_status(args(name="ci-01")) == 0

    out = capsys.readouterr().out
    assert "ci-01" in out and "up" in out and "2.337.0" in out
    assert "2h 15min" in out
    assert "since" not in out.split("\n")[1]


def test_status_host_backend_reads_systemctl_directly_without_sudo(runners, monkeypatch):
    abgal.write_runner_state("ci-01", {"name": "ci-01", "backend": "host"})
    write_service_file(runners, "ci-01", unit="actions.runner.myorg-myrepo.ci-01.service")

    calls = []
    monkeypatch.setattr(abgal.subprocess, "run",
                        lambda command, **k: calls.append(command) or done(stdout="active\n"))

    assert abgal.cmd_github_runner_status(args(name="ci-01")) == 0

    assert calls == [["systemctl", "--no-pager", "status", "actions.runner.myorg-myrepo.ci-01.service"]]


def test_status_host_backend_not_yet_installed(runners, monkeypatch, capsys):
    abgal.write_runner_state("ci-01", {"name": "ci-01", "backend": "host"})

    monkeypatch.setattr(abgal.subprocess, "run",
                        lambda *a, **k: pytest.fail("systemctl must not run without a .service file"))

    assert abgal.cmd_github_runner_status(args(name="ci-01")) == 1

    assert "not installed" in capsys.readouterr().out


def test_status_host_backend_down(runners, monkeypatch, capsys):
    abgal.write_runner_state("ci-01", {"name": "ci-01", "backend": "host"})
    write_service_file(runners, "ci-01")
    monkeypatch.setattr(abgal.subprocess, "run", lambda *a, **k: done(stdout="inactive (dead)\n"))

    assert abgal.cmd_github_runner_status(args(name="ci-01")) == 1

    assert "down" in capsys.readouterr().out


def test_status_container_backend_reads_engine_state(runners, monkeypatch, capsys):
    abgal.write_runner_state("ci-02", {"name": "ci-02", "backend": "container", "engine": "docker",
                                       "labels": "linux,x64"})
    started = (abgal.datetime.datetime.utcnow() - abgal.datetime.timedelta(minutes=40))
    monkeypatch.setattr(abgal.subprocess, "run",
                        lambda *a, **k: done(stdout="running|%sZ\n" % started.strftime("%Y-%m-%dT%H:%M:%S")))

    assert abgal.cmd_github_runner_status(args(name="ci-02")) == 0

    out = capsys.readouterr().out
    assert "up" in out and "linux,x64" in out
    assert "00:00:39" in out or "00:00:40" in out


def test_status_labels_wider_than_the_fixed_guess_stay_in_their_column(runners, monkeypatch, capsys):
    abgal.write_runner_state("ci-01", {"name": "ci-01", "backend": "container", "engine": "docker",
                                       "labels": "self-hosted,linux,x64"})
    monkeypatch.setattr(abgal.subprocess, "run", lambda *a, **k: done(stdout="running|\n"))

    assert abgal.cmd_github_runner_status(args(name="ci-01")) == 0

    header, row = capsys.readouterr().out.splitlines()[:2]
    assert header.index("DETAIL") == row.index("running")


def test_status_without_a_name_lists_every_runner(runners, monkeypatch, capsys):
    abgal.write_runner_state("ci-01", {"name": "ci-01", "backend": "host"})
    abgal.write_runner_state("ci-02", {"name": "ci-02", "backend": "host"})
    write_service_file(runners, "ci-01")
    write_service_file(runners, "ci-02")
    monkeypatch.setattr(abgal.subprocess, "run", lambda *a, **k: done(stdout="active\n"))

    assert abgal.cmd_github_runner_status(args()) == 0

    out = capsys.readouterr().out
    assert "ci-01" in out and "ci-02" in out


def test_status_wait_retries_until_up(runners, monkeypatch, capsys):
    """--wait polls the backend again instead of failing on the first look,
    useful right after create when the process is up but not yet settled."""
    abgal.write_runner_state("ci-01", {"name": "ci-01", "backend": "host"})
    write_service_file(runners, "ci-01")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return done(stdout="active\n" if len(calls) >= 3 else "inactive\n")

    monkeypatch.setattr(abgal.subprocess, "run", fake_run)
    monkeypatch.setattr(abgal.time, "sleep", lambda seconds: None)

    assert abgal.cmd_github_runner_status(args(name="ci-01", wait=30)) == 0
    assert len(calls) >= 3
