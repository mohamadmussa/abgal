"""abgal github-runner remove, host backend.

No real gh, config.sh or svc.sh runs. subprocess.run is replaced, and
abgal.RUNNERS and abgal.HOME sit under tmp_path so nothing touches the
real machine.
"""

import argparse
from types import SimpleNamespace

import pytest

import abgal


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(abgal, "HOME", tmp_path)
    monkeypatch.setattr(abgal, "RUNNERS", tmp_path / "runners")
    return tmp_path


def args(name, repo=None, key=None, backend=None):
    return argparse.Namespace(name=name, repo=repo, key=key, backend=backend)


def done(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def write_state(home, name, **extra):
    state = {"name": name, "backend": "host", "repo": "myorg/myrepo",
              "labels": "linux,x64", "version": "2.337.0"}
    state.update(extra)
    (home / "runners").mkdir(parents=True, exist_ok=True)
    (home / "runners" / (name + ".json")).write_text(__import__("json").dumps(state))
    (home / "runners" / name).mkdir(parents=True, exist_ok=True)
    return state


def test_remove_fails_for_an_unknown_runner(home, capsys):
    assert abgal.cmd_github_runner_remove(args("ci-01")) == 1
    assert "no runner named" in capsys.readouterr().err


def test_remove_stops_uninstalls_deregisters_and_cleans_up(home, monkeypatch):
    write_state(home, "ci-01")

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:2] == ["gh", "api"]:
            return done(stdout="rm-tok3n\n")
        return done()

    monkeypatch.setattr(abgal.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(abgal.subprocess, "run", fake_run)

    assert abgal.cmd_github_runner_remove(args("ci-01")) == 0

    assert [c[-1] for c in calls if c[0].endswith("svc.sh")] == ["stop", "uninstall"]
    config_call = next(c for c in calls if c[0].endswith("config.sh"))
    assert config_call[1:] == ["remove", "--token", "rm-tok3n"]
    assert "repos/myorg/myrepo/actions/runners/remove-token" in \
        next(c for c in calls if c[:2] == ["gh", "api"])[4]

    assert not (home / "runners" / "ci-01").exists()
    assert abgal.read_runner_state("ci-01") is None


def test_remove_with_key_skips_gh(home, monkeypatch):
    write_state(home, "ci-01")

    calls = []
    monkeypatch.setattr(abgal.shutil, "which", lambda name: None)
    monkeypatch.setattr(abgal.subprocess, "run", lambda command, **k: calls.append(command) or done())

    assert abgal.cmd_github_runner_remove(args("ci-01", key="pat-token")) == 0

    config_call = next(c for c in calls if c[0].endswith("config.sh"))
    assert "pat-token" in config_call


def test_remove_continues_locally_when_svc_sh_fails(home, monkeypatch, capsys):
    write_state(home, "ci-01")

    monkeypatch.setattr(abgal.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(abgal.subprocess, "run",
                        lambda command, **k: done(returncode=1, stderr="boom") if
                        command[0].endswith("svc.sh") else done(stdout="tok\n"))

    assert abgal.cmd_github_runner_remove(args("ci-01")) == 0
    assert "svc.sh" in capsys.readouterr().err
    assert not (home / "runners" / "ci-01").exists()


def test_remove_without_a_known_repo_only_cleans_up_locally(home, monkeypatch, capsys):
    write_state(home, "ci-01", repo="")

    calls = []
    monkeypatch.setattr(abgal.subprocess, "run", lambda command, **k: calls.append(command) or done())

    assert abgal.cmd_github_runner_remove(args("ci-01")) == 0
    assert "not deregistering" in capsys.readouterr().err
    assert not any(c[0].endswith("config.sh") for c in calls)
    assert not (home / "runners" / "ci-01").exists()


def test_remove_without_a_state_file_still_cleans_up_the_folder(home, monkeypatch):
    (home / "runners" / "ci-01").mkdir(parents=True)

    monkeypatch.setattr(abgal.subprocess, "run", lambda command, **k: done())

    assert abgal.cmd_github_runner_remove(args("ci-01")) == 0
    assert not (home / "runners" / "ci-01").exists()
