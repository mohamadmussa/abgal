"""--port outside 5554 to 5584 or odd is refused."""

import argparse

import pytest

import abgal


def start_args(port):
    return argparse.Namespace(
        name=["dev"], port=port, dry_run=False, no_watch=True,
    )


@pytest.mark.parametrize("port", [5552, 5586, 5555, 4000])
def test_bad_port_is_refused(monkeypatch, port):
    monkeypatch.setattr(abgal, "resolve", lambda name: name)

    with pytest.raises(SystemExit) as excinfo:
        abgal.cmd_start(start_args(port))

    assert excinfo.value.code == 1


def test_port_with_more_than_one_guest_is_refused(monkeypatch):
    monkeypatch.setattr(abgal, "resolve", lambda name: name)
    args = argparse.Namespace(name=["dev-01", "dev-02"], port=5554,
                              dry_run=False, no_watch=True)

    with pytest.raises(SystemExit) as excinfo:
        abgal.cmd_start(args)

    assert excinfo.value.code == 1
