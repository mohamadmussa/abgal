"""abgal github-runner create, container backend.

No real docker/podman, gh, urlopen or /.dockerenv runs. subprocess.run is
replaced, urlopen is replaced with a small in-memory tar.gz, and
abgal.RUNNERS/abgal.HOME sit under tmp_path so nothing touches the real
machine.
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
    monkeypatch.setattr(abgal, "running_in_container", lambda: False)
    return tmp_path


def write_runner_versions(home, sha256):
    (home / "runner-versions.conf").write_text(
        "linux-x64 | 2.337.0 | https://example.invalid/runner.tar.gz | %s\n" % sha256)


def runner_tarball():
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


def args(name, repo=None, labels=None, backend="container", version=None, key=None):
    return argparse.Namespace(name=name, repo=repo, labels=labels, backend=backend,
                              version=version, key=key)


def done(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_create_fails_when_abgal_itself_is_in_a_container(home, monkeypatch, capsys):
    monkeypatch.setattr(abgal, "running_in_container", lambda: True)

    assert abgal.cmd_github_runner_create(args("ci-01", repo="o/r")) == 1
    assert "nested containers" in capsys.readouterr().err


def test_create_fails_without_docker_or_podman(home, monkeypatch, capsys):
    monkeypatch.setattr(abgal, "container_engine", lambda: None)

    assert abgal.cmd_github_runner_create(args("ci-01", repo="o/r")) == 1
    assert "neither docker nor podman" in capsys.readouterr().err


def test_create_pulls_the_image_and_runs_the_container(home, monkeypatch):
    raw, sha = runner_tarball()
    write_runner_versions(home, sha)
    monkeypatch.setattr(abgal.urllib.request, "urlopen", lambda url, timeout: FakeResponse(raw))
    monkeypatch.setattr(abgal, "container_engine", lambda: "docker")
    monkeypatch.setattr(abgal.shutil, "which", lambda name: "/usr/bin/gh")

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:2] == ["gh", "api"]:
            return done(stdout="tok3n\n")
        return done()

    monkeypatch.setattr(abgal.subprocess, "run", fake_run)

    assert abgal.cmd_github_runner_create(
        args("ci-01", repo="myorg/myrepo", labels="linux,x64")) == 0

    pull_call = next(c for c in calls if c[:2] == ["docker", "pull"])
    assert pull_call[2] == abgal.CONTAINER_RUNNER_IMAGE
    run_call = next(c for c in calls if c[:2] == ["docker", "run"])
    assert "--device" in run_call and "/dev/kvm" in run_call
    assert "RUNNER_TOKEN=tok3n" in run_call
    assert run_call[-1] == abgal.CONTAINER_RUNNER_IMAGE

    state = abgal.read_runner_state("ci-01")
    assert state["backend"] == "container"
    assert state["engine"] == "docker"
    assert state["container"] == "ci-01"


def test_create_builds_locally_when_the_pull_fails(home, monkeypatch):
    raw, sha = runner_tarball()
    write_runner_versions(home, sha)
    (home / "docker" / "runner").mkdir(parents=True)
    (home / "docker" / "runner" / "Dockerfile").write_text("FROM scratch\n")
    monkeypatch.setattr(abgal.urllib.request, "urlopen", lambda url, timeout: FakeResponse(raw))
    monkeypatch.setattr(abgal, "container_engine", lambda: "docker")
    monkeypatch.setattr(abgal.shutil, "which", lambda name: "/usr/bin/gh")

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:2] == ["docker", "pull"]:
            return done(returncode=1, stderr="no such image")
        if command[:2] == ["gh", "api"]:
            return done(stdout="tok3n\n")
        return done()

    monkeypatch.setattr(abgal.subprocess, "run", fake_run)

    assert abgal.cmd_github_runner_create(args("ci-01", repo="o/r")) == 0

    assert any(c[:2] == ["docker", "build"] for c in calls)


def test_create_fails_when_neither_pull_nor_local_dockerfile_work(home, monkeypatch, capsys):
    raw, sha = runner_tarball()
    write_runner_versions(home, sha)
    monkeypatch.setattr(abgal.urllib.request, "urlopen", lambda url, timeout: FakeResponse(raw))
    monkeypatch.setattr(abgal, "container_engine", lambda: "docker")
    monkeypatch.setattr(abgal.subprocess, "run",
                        lambda command, **k: done(returncode=1, stderr="no network"))

    assert abgal.cmd_github_runner_create(args("ci-01", repo="o/r", key="pat-token")) == 1
    assert "could not pull" in capsys.readouterr().err
    assert not (home / "runners" / "ci-01").exists()
