"""The watch: a fake thermal zone and fake readings, the four real endings."""

import argparse

import abgal


def watch_args():
    return argparse.Namespace(name=None)


def fake_sequence(values):
    """A callable that returns the next value on every call, ignoring its args."""
    remaining = iter(values)

    def _next(*_args, **_kwargs):
        return next(remaining)

    return _next


def patch_common(monkeypatch, tmp_path):
    monkeypatch.setattr(abgal, "LOGS", tmp_path)
    monkeypatch.setattr(abgal, "thermal_zone", lambda: "fake-zone")
    monkeypatch.setattr(abgal.time, "sleep", lambda seconds: None)


def test_watch_warns_then_clears_then_ends_when_the_guest_is_gone(tmp_path, monkeypatch):
    patch_common(monkeypatch, tmp_path)
    # initial reading, then one warning reading (>= 88), then one reading
    # three degrees below the warning threshold, which clears it.
    monkeypatch.setattr(abgal, "temperature", fake_sequence([70, 90, 84]))
    # present for the initial check and two loop iterations, then gone.
    monkeypatch.setattr(abgal, "watched", fake_sequence([["dev"], ["dev"], ["dev"], []]))

    assert abgal.cmd_watch(watch_args()) == 0


def test_watch_aborts_at_the_stop_threshold(tmp_path, monkeypatch):
    patch_common(monkeypatch, tmp_path)
    stopped = []
    monkeypatch.setattr(abgal, "stop_one",
                        lambda name, serial, grace, say=print: stopped.append(name) or True)
    monkeypatch.setattr(abgal, "running_serials", lambda: {})
    monkeypatch.setattr(abgal, "temperature", fake_sequence([70, 97]))
    monkeypatch.setattr(abgal, "watched", fake_sequence([["dev"], ["dev"]]))

    assert abgal.cmd_watch(watch_args()) == 1
    assert stopped == ["dev"]


def test_watch_aborts_after_four_blind_readings(tmp_path, monkeypatch):
    patch_common(monkeypatch, tmp_path)
    monkeypatch.setattr(abgal, "temperature", fake_sequence([70, None, None, None, None]))
    monkeypatch.setattr(abgal, "watched", fake_sequence([["dev"]] * 5))

    assert abgal.cmd_watch(watch_args()) == 2


def test_watch_aborts_at_once_with_no_measurable_temperature(tmp_path, monkeypatch):
    patch_common(monkeypatch, tmp_path)
    monkeypatch.setattr(abgal, "temperature", fake_sequence([None]))
    monkeypatch.setattr(abgal, "watched", fake_sequence([["dev"]]))

    assert abgal.cmd_watch(watch_args()) == 2
