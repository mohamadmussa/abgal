"""abgal stop, the polite way first and signals only afterwards.

adb and /proc are fakes, os.kill and time.sleep are replaced, so no real
process receives a signal and no test waits.
"""

import argparse
import signal

import pytest

import abgal


@pytest.fixture
def kills(fake_proc, monkeypatch):
    """Records each signal. The emulator in the fake tree dies on the ones listed."""
    sent = []
    fatal = set()

    def fake_kill(pid, number):
        sent.append((pid, number))
        if number in fatal:
            fake_proc.remove(pid)

    monkeypatch.setattr(abgal.os, "kill", fake_kill)
    monkeypatch.setattr(abgal.time, "sleep", lambda seconds: None)
    return sent, fatal


def test_a_guest_that_obeys_the_console_gets_no_signal(fake_proc, fake_adb, kills):
    sent, _ = kills
    fake_proc.add_emulator(4100, "pixel")
    fake_adb.attach("emulator-5554", "pixel", pid=4100)
    said = []

    assert abgal.stop_one("pixel", "emulator-5554", grace=5, say=said.append)

    assert fake_adb.serials_called("emu", "kill") == ["emulator-5554"]
    assert sent == []
    assert said[-1] == "  pixel: stopped."


def test_a_stubborn_guest_gets_sigterm(fake_proc, fake_adb, kills):
    sent, fatal = kills
    fatal.add(signal.SIGTERM)
    fake_proc.add_emulator(4100, "pixel")
    fake_adb.attach("emulator-5554", "pixel", pid=4100, stubborn=True)

    assert abgal.stop_one("pixel", "emulator-5554", grace=0, say=lambda m: None)

    assert sent == [(4100, signal.SIGTERM)]


def test_sigkill_comes_only_after_sigterm(fake_proc, fake_adb, kills):
    sent, fatal = kills
    fatal.add(signal.SIGKILL)
    fake_proc.add_emulator(4100, "pixel")

    assert abgal.stop_one("pixel", None, grace=0, say=lambda m: None)

    assert sent == [(4100, signal.SIGTERM), (4100, signal.SIGKILL)]
    assert fake_adb.serials_called("emu", "kill") == []


def test_a_guest_that_survives_both_signals_is_reported(fake_proc, fake_adb, kills):
    fake_proc.add_emulator(4100, "pixel")
    said = []

    assert not abgal.stop_one("pixel", None, grace=0, say=said.append)

    assert said[-1] == "  pixel: still running. Nothing else this program can do."
    assert fake_proc.pids() == [4100]


def test_stop_tries_every_guest_before_judging(tmp_path, fake_proc, fake_adb,
                                               kills, monkeypatch, capsys):
    monkeypatch.setattr(abgal, "AVD", tmp_path / "avd")
    for name in ("pixel", "tablet"):
        (tmp_path / "avd" / (name + ".avd")).mkdir(parents=True)
    fake_proc.set_available(4 * 1024 * 1024)
    fake_proc.add_emulator(4100, "pixel")
    fake_proc.add_emulator(4200, "tablet")
    fake_adb.attach("emulator-5554", "pixel", pid=4100, stubborn=True)
    fake_adb.attach("emulator-5556", "tablet", pid=4200)
    args = argparse.Namespace(name=["pixel", "tablet"], grace=0, parser=None)

    assert abgal.cmd_stop(args) == 1

    assert fake_proc.pids() == [4100]
    assert "1 of 2 stopped. Memory available: 4096 MB." in capsys.readouterr().out
