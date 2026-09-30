"""wait_for_boot, and the restart -change-locale causes."""

import abgal


def fake_adb(readings):
    """Returns readings in order, then keeps repeating the last one."""
    calls = []

    def adb(*args, serial=None, timeout=30):
        calls.append(serial)
        index = min(len(calls) - 1, len(readings) - 1)
        return 0, readings[index], ""

    return adb


def test_wait_for_boot_true_on_two_readings_in_a_row(monkeypatch):
    monkeypatch.setattr(abgal, "adb", fake_adb(["1", "1"]))
    monkeypatch.setattr(abgal.time, "sleep", lambda seconds: None)

    assert abgal.wait_for_boot("emulator-5554", seconds=30) is True


def test_wait_for_boot_ignores_a_single_reading_before_a_restart(monkeypatch):
    # The pattern -change-locale causes: up once, down for the restart, up
    # again and staying up. A single 1 must not be enough on its own.
    monkeypatch.setattr(abgal, "adb", fake_adb(["1", "0", "1", "1"]))
    monkeypatch.setattr(abgal.time, "sleep", lambda seconds: None)

    assert abgal.wait_for_boot("emulator-5554", seconds=30) is True


def test_wait_for_boot_false_when_never_settled(monkeypatch):
    times = iter([0, 1, 2, 3, 100])
    monkeypatch.setattr(abgal.time, "time", lambda: next(times))
    monkeypatch.setattr(abgal, "adb", fake_adb(["1", "0", "1", "0"]))
    monkeypatch.setattr(abgal.time, "sleep", lambda seconds: None)

    assert abgal.wait_for_boot("emulator-5554", seconds=30) is False
