"""The local state file abgal writes for a self hosted GitHub Actions runner.

Nothing here talks to svc.sh, Docker or Podman, only the state file itself,
which status, log, create and remove all read and write later.
"""

import pytest

import abgal


@pytest.fixture
def runners(tmp_path, monkeypatch):
    monkeypatch.setattr(abgal, "RUNNERS", tmp_path / "runners")
    return tmp_path / "runners"


def test_read_runner_state_without_a_file_is_none(runners):
    assert abgal.read_runner_state("ci-01") is None


def test_write_then_read_runner_state_round_trips(runners):
    abgal.write_runner_state("ci-01", {"name": "ci-01", "backend": "host"})

    assert abgal.read_runner_state("ci-01") == {"name": "ci-01", "backend": "host"}


def test_write_runner_state_creates_the_runners_folder(runners):
    assert not runners.exists()

    abgal.write_runner_state("ci-01", {"name": "ci-01", "backend": "host"})

    assert runners.is_dir()


def test_runner_names_is_empty_without_the_folder(runners):
    assert abgal.runner_names() == []


def test_runner_names_lists_every_state_file_sorted(runners):
    abgal.write_runner_state("tablet-runner", {"name": "tablet-runner", "backend": "host"})
    abgal.write_runner_state("ci-01", {"name": "ci-01", "backend": "container"})

    assert abgal.runner_names() == ["ci-01", "tablet-runner"]


def test_runner_dir_and_state_path_sit_under_runners(runners):
    assert abgal.runner_dir("ci-01") == runners / "ci-01"
    assert abgal.runner_state_path("ci-01") == runners / "ci-01.json"
