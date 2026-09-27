"""abgal shutdown, both the plain stop and the confirmed --DELETE.

adb and /proc are fakes and os.kill/time.sleep are replaced, so no real
process is signalled. avdmanager is faked too, by deleting the guest folder
the same way the real tool would, so no real SDK binary runs.
"""

import argparse
import builtins
import re

import pytest

import abgal


@pytest.fixture
def no_signals(fake_proc, monkeypatch):
    monkeypatch.setattr(abgal.os, "kill", lambda pid, number: None)
    monkeypatch.setattr(abgal.time, "sleep", lambda seconds: None)


@pytest.fixture
def two_guests(tmp_path, fake_proc, fake_adb, monkeypatch):
    monkeypatch.setattr(abgal, "AVD", tmp_path / "avd")
    for name in ("pixel", "tablet"):
        (tmp_path / "avd" / (name + ".avd")).mkdir(parents=True)
    fake_proc.add_emulator(4100, "pixel")
    fake_proc.add_emulator(4200, "tablet")
    fake_adb.attach("emulator-5554", "pixel", pid=4100)
    fake_adb.attach("emulator-5556", "tablet", pid=4200)
    return tmp_path / "avd"


@pytest.fixture
def fake_avdmanager(monkeypatch):
    """Removes the guest folder, the one effect cmd_shutdown checks for."""
    calls = []

    def fake_run_tool(command, answer="", quiet=False):
        name = command[-1]
        calls.append(name)
        abgal.shutil.rmtree(abgal.guest_folder(name), ignore_errors=True)
        return 0

    monkeypatch.setattr(abgal, "run_tool", fake_run_tool)
    return calls


def args(DELETE=False, grace=0):
    return argparse.Namespace(DELETE=DELETE, grace=grace)


def test_shutdown_stops_every_running_guest(two_guests, no_signals, capsys):
    assert abgal.cmd_shutdown(args()) == 0

    out = capsys.readouterr().out
    assert "Stopped 2 of 2: pixel, tablet" in out
    assert abgal.running_pid("pixel") is None
    assert abgal.running_pid("tablet") is None


def test_shutdown_without_delete_leaves_guests_on_disk(two_guests, no_signals):
    abgal.cmd_shutdown(args())

    assert abgal.guest_folder("pixel").is_dir()
    assert abgal.guest_folder("tablet").is_dir()


def test_shutdown_reports_when_nothing_is_running(tmp_path, fake_proc, monkeypatch, capsys):
    monkeypatch.setattr(abgal, "AVD", tmp_path / "avd")

    assert abgal.cmd_shutdown(args()) == 0

    assert "Nothing is running." in capsys.readouterr().out


def test_delete_without_a_tty_refuses(two_guests, no_signals, fake_avdmanager, monkeypatch):
    monkeypatch.setattr(abgal.sys, "stdin", type("Stdin", (), {"isatty": staticmethod(lambda: False)})())

    with pytest.raises(SystemExit):
        abgal.cmd_shutdown(args(DELETE=True))

    assert fake_avdmanager == []
    assert abgal.guest_folder("pixel").is_dir()


def test_delete_with_the_wrong_answer_deletes_nothing(two_guests, no_signals, fake_avdmanager,
                                                       monkeypatch, capsys):
    monkeypatch.setattr(abgal.sys, "stdin", type("Stdin", (), {"isatty": staticmethod(lambda: True)})())
    monkeypatch.setattr(builtins, "input", lambda prompt: "wrong")

    assert abgal.cmd_shutdown(args(DELETE=True)) == 1

    assert fake_avdmanager == []
    assert abgal.guest_folder("pixel").is_dir()
    assert "Wrong answer. Nothing was deleted." in capsys.readouterr().out


def test_delete_rejects_enter_yes_and_y(two_guests, no_signals, fake_avdmanager, monkeypatch):
    monkeypatch.setattr(abgal.sys, "stdin", type("Stdin", (), {"isatty": staticmethod(lambda: True)})())

    for reply in ("", "yes", "y"):
        monkeypatch.setattr(builtins, "input", lambda prompt, reply=reply: reply)
        assert abgal.cmd_shutdown(args(DELETE=True)) == 1

    assert fake_avdmanager == []


def test_delete_with_the_right_answer_removes_every_guest(two_guests, no_signals, fake_avdmanager,
                                                           monkeypatch, capsys):
    monkeypatch.setattr(abgal.sys, "stdin", type("Stdin", (), {"isatty": staticmethod(lambda: True)})())

    def solve(prompt):
        match = re.search(r"What is (\d+) \+ (\d+)\?", prompt)
        return str(int(match.group(1)) + int(match.group(2)))

    monkeypatch.setattr(builtins, "input", solve)

    assert abgal.cmd_shutdown(args(DELETE=True)) == 0

    assert sorted(fake_avdmanager) == ["pixel", "tablet"]
    assert not abgal.guest_folder("pixel").exists()
    assert not abgal.guest_folder("tablet").exists()
    out = capsys.readouterr().out
    assert "Removed 2 guest(s): pixel, tablet" in out


def test_delete_with_no_guests_on_disk_asks_nothing(tmp_path, fake_proc, monkeypatch, capsys):
    monkeypatch.setattr(abgal, "AVD", tmp_path / "avd")

    def fail_if_called(prompt):
        raise AssertionError("should not ask when there is nothing to delete")

    monkeypatch.setattr(builtins, "input", fail_if_called)

    assert abgal.cmd_shutdown(args(DELETE=True)) == 0

    assert "No guests on disk" in capsys.readouterr().out
