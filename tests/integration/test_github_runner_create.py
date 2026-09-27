"""abgal github-runner create, host backend.

No real network, gh, config.sh or svc.sh runs. urllib.request.urlopen is
replaced with a small tar.gz built in memory, subprocess.run is replaced for
gh, config.sh and svc.sh, and abgal.RUNNERS and abgal.HOME sit under
tmp_path so nothing touches the real machine.
"""

import argparse
import hashlib
import io
import tarfile
from types import SimpleNamespace

import pytest

import abgal


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(abgal, "HOME", tmp_path)
    monkeypatch.setattr(abgal, "RUNNERS", tmp_path / "runners")
    monkeypatch.setattr(abgal.platform, "machine", lambda: "x86_64")
    return tmp_path


def write_runner_versions(home, sha256):
    (home / "runner-versions.conf").write_text(
        "linux-x64 | 2.337.0 | https://example.invalid/runner.tar.gz | %s\n" % sha256)


def runner_tarball():
    """A minimal tar.gz standing in for the real runner download, and its sha256."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as archive:
        data = b"#!/bin/sh\necho config\n"
        info = tarfile.TarInfo("config.sh")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    raw = buf.getvalue()
    return raw, hashlib.sha256(raw).hexdigest()


class FakeResponse:
    def __init__(self, data):
        self._data = data
        self.headers = {"Content-Length": str(len(data))}
        self._sent = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n):
        if self._sent:
            return b""
        self._sent = True
        return self._data


def args(name, repo=None, labels=None, backend=None, version=None, key=None):
    return argparse.Namespace(name=name, repo=repo, labels=labels, backend=backend,
                              version=version, key=key)


def done(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_create_fails_without_a_repo(home, capsys):
    assert abgal.cmd_github_runner_create(args("ci-01")) == 1
    assert "no repo" in capsys.readouterr().err


def test_create_fails_for_container_backend(home, capsys):
    assert abgal.cmd_github_runner_create(args("ci-01", repo="o/r", backend="container")) == 1
    assert "not implemented yet" in capsys.readouterr().err


def test_create_fails_without_a_tested_version(home, capsys):
    assert abgal.cmd_github_runner_create(args("ci-01", repo="o/r")) == 1
    assert "runner-versions.conf" in capsys.readouterr().err


def test_create_fails_when_the_target_already_exists(home, capsys):
    raw, sha = runner_tarball()
    write_runner_versions(home, sha)
    (home / "runners" / "ci-01").mkdir(parents=True)

    assert abgal.cmd_github_runner_create(args("ci-01", repo="o/r")) == 1
    assert "already exists" in capsys.readouterr().err


def test_create_downloads_registers_and_starts(home, monkeypatch, capsys):
    raw, sha = runner_tarball()
    write_runner_versions(home, sha)
    monkeypatch.setattr(abgal.urllib.request, "urlopen", lambda url, timeout: FakeResponse(raw))

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:2] == ["gh", "api"]:
            return done(stdout="tok3n\n")
        return done()

    monkeypatch.setattr(abgal.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(abgal.subprocess, "run", fake_run)

    assert abgal.cmd_github_runner_create(
        args("ci-01", repo="myorg/myrepo", labels="linux,x64")) == 0

    config_call = next(c for c in calls if c[0].endswith("config.sh"))
    assert "https://github.com/myorg/myrepo" in config_call
    assert "tok3n" in config_call
    assert "linux,x64" in config_call
    assert [c[-1] for c in calls if c[0].endswith("svc.sh")] == ["install", "start"]

    state = abgal.read_runner_state("ci-01")
    assert state == {"name": "ci-01", "backend": "host", "repo": "myorg/myrepo",
                     "labels": "linux,x64", "version": "2.337.0"}
    assert (home / "runners" / "ci-01" / "config.sh").exists()


def test_create_uses_runner_conf_when_no_flags_given(home, monkeypatch):
    raw, sha = runner_tarball()
    write_runner_versions(home, sha)
    (home / "runner.conf").write_text("ci-01 | myorg/myrepo | linux,x64 | host\n")
    monkeypatch.setattr(abgal.urllib.request, "urlopen", lambda url, timeout: FakeResponse(raw))
    monkeypatch.setattr(abgal.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(abgal.subprocess, "run", lambda command, **k: done(stdout="tok3n\n"))

    assert abgal.cmd_github_runner_create(args("ci-01")) == 0

    assert abgal.read_runner_state("ci-01")["repo"] == "myorg/myrepo"


def test_create_with_key_skips_gh(home, monkeypatch):
    raw, sha = runner_tarball()
    write_runner_versions(home, sha)
    monkeypatch.setattr(abgal.urllib.request, "urlopen", lambda url, timeout: FakeResponse(raw))
    monkeypatch.setattr(abgal.shutil, "which", lambda name: None)

    calls = []
    monkeypatch.setattr(abgal.subprocess, "run", lambda command, **k: calls.append(command) or done())

    assert abgal.cmd_github_runner_create(args("ci-01", repo="o/r", key="pat-token")) == 0

    config_call = next(c for c in calls if c[0].endswith("config.sh"))
    assert "pat-token" in config_call


def test_create_fails_with_a_bad_checksum(home, monkeypatch, capsys):
    raw, _ = runner_tarball()
    write_runner_versions(home, "0" * 64)
    monkeypatch.setattr(abgal.urllib.request, "urlopen", lambda url, timeout: FakeResponse(raw))

    assert abgal.cmd_github_runner_create(args("ci-01", repo="o/r")) == 1
    assert "sha256" in capsys.readouterr().err
    assert not (home / "runners" / "ci-01").exists()
