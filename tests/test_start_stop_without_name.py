"""start and stop without -n print help and end with exit code 1."""

import argparse

import abgal


class DummyParser:
    def print_help(self):
        pass


def test_start_without_name_returns_one(tmp_path, monkeypatch):
    monkeypatch.setattr(abgal, "HOME", tmp_path)
    monkeypatch.setattr(abgal, "AVD", tmp_path / "avd")
    args = argparse.Namespace(name=None, parser=DummyParser())

    assert abgal.cmd_start(args) == 1


def test_stop_without_name_returns_one(tmp_path, monkeypatch):
    monkeypatch.setattr(abgal, "HOME", tmp_path)
    monkeypatch.setattr(abgal, "AVD", tmp_path / "avd")
    args = argparse.Namespace(name=None, parser=DummyParser())

    assert abgal.cmd_stop(args) == 1
