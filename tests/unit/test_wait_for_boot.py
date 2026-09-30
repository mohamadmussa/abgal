"""wait_for_boot, and the restart a reboot causes."""

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
    # The pattern a reboot causes: up once, down for the restart, up again
    # and staying up. A single 1 must not be enough on its own.
    monkeypatch.setattr(abgal, "adb", fake_adb(["1", "0", "1", "1"]))
    monkeypatch.setattr(abgal.time, "sleep", lambda seconds: None)

    assert abgal.wait_for_boot("emulator-5554", seconds=30) is True


def test_wait_for_boot_false_when_never_settled(monkeypatch):
    times = iter([0, 1, 2, 3, 100])
    monkeypatch.setattr(abgal.time, "time", lambda: next(times))
    monkeypatch.setattr(abgal, "adb", fake_adb(["1", "0", "1", "0"]))
    monkeypatch.setattr(abgal.time, "sleep", lambda seconds: None)

    assert abgal.wait_for_boot("emulator-5554", seconds=30) is False


def test_apply_locale_writes_the_setting_and_reboots_before_waiting(monkeypatch):
    calls = []
    monkeypatch.setattr(abgal, "adb", lambda *args, **kwargs: calls.append((args, kwargs)) or (0, "", ""))
    monkeypatch.setattr(abgal, "wait_for_boot", lambda serial, seconds: True)

    assert abgal.apply_locale("emulator-5554", "ar-SA", seconds=30) is True
    assert calls[0] == (("shell", "settings", "put", "system", "system_locales", "ar-SA"),
                        {"serial": "emulator-5554"})
    assert calls[1] == (("reboot",), {"serial": "emulator-5554"})


def test_apply_locale_returns_false_when_the_reboot_never_settles(monkeypatch):
    monkeypatch.setattr(abgal, "adb", lambda *args, **kwargs: (0, "", ""))
    monkeypatch.setattr(abgal, "wait_for_boot", lambda serial, seconds: False)

    assert abgal.apply_locale("emulator-5554", "ar-SA", seconds=30) is False
