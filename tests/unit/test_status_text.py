"""abgal status, the human readable table (#56: word states, clearer headers)."""

import io
from contextlib import redirect_stdout

import abgal


def make_guest(tmp_path, name, template="phone-1080x2400-480-api35-x86_64"):
    folder = tmp_path / (name + ".avd")
    folder.mkdir()
    (folder / "abgal-template").write_text(template)
    return folder


def run_status_text(monkeypatch, tmp_path, pid=None, attached_state=None):
    monkeypatch.setattr(abgal, "AVD", tmp_path)
    monkeypatch.setattr(abgal, "running_pid", lambda name: pid)
    monkeypatch.setattr(abgal, "process_stats", lambda p: None)
    monkeypatch.setattr(abgal, "available_mb", lambda: 4096)
    if attached_state is None:
        monkeypatch.setattr(abgal, "attached", lambda: {})
    else:
        monkeypatch.setattr(abgal, "attached", lambda: {"emulator-5554": attached_state})
        monkeypatch.setattr(abgal, "serial_name", lambda serial: "dev-a")
    args = abgal.build_parser().parse_args(["status"])
    out = io.StringIO()
    with redirect_stdout(out):
        abgal.cmd_status(args)
    return out.getvalue()


def test_status_text_headers_use_name_and_device(monkeypatch, tmp_path):
    make_guest(tmp_path, "dev-a")

    out = run_status_text(monkeypatch, tmp_path)

    header = out.splitlines()[0].split()
    assert header[:5] == ["NAME", "ID", "STATE", "DEVICE", "ADB"]


def test_status_text_state_is_stopped_without_a_pid(monkeypatch, tmp_path):
    make_guest(tmp_path, "dev-a")

    out = run_status_text(monkeypatch, tmp_path)

    assert "stopped" in out
    assert "live" not in out


def test_status_text_state_is_live_with_a_pid(monkeypatch, tmp_path):
    make_guest(tmp_path, "dev-a")

    out = run_status_text(monkeypatch, tmp_path, pid=1234, attached_state="device")

    assert "live" in out
    assert "pid" not in out
