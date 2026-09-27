"""abgal status, the human readable table (#56: word states, clearer headers)."""

import io
from contextlib import redirect_stdout

import abgal


def make_guest(tmp_path, name, template="phone-1080x2400-480-api35-x86_64"):
    folder = tmp_path / (name + ".avd")
    folder.mkdir()
    (folder / "abgal-template").write_text(template)
    return folder


def run_status_text(monkeypatch, tmp_path, pid=None, attached_state=None, stats=None):
    monkeypatch.setattr(abgal, "AVD", tmp_path)
    monkeypatch.setattr(abgal, "running_pid", lambda name: pid)
    monkeypatch.setattr(abgal, "process_stats", lambda p: stats)
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
    assert header[:8] == ["NAME", "ID", "STATE", "DEVICE", "ADB", "MEM", "CPU", "UPTIME"]


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


def test_status_text_mem_cpu_and_uptime_are_blank_without_a_pid(monkeypatch, tmp_path):
    make_guest(tmp_path, "dev-a")

    out = run_status_text(monkeypatch, tmp_path)

    row = out.splitlines()[1].split()
    assert row[5:8] == ["-", "-", "-"]


def test_status_text_mem_cpu_and_uptime_come_from_process_stats(monkeypatch, tmp_path):
    make_guest(tmp_path, "dev-a")

    out = run_status_text(monkeypatch, tmp_path, pid=1234, attached_state="device",
                          stats={"mem_mb": 612, "cpu_percent": 3.2, "uptime_s": 12})

    row = out.splitlines()[1].split()
    assert row[5:8] == ["612", "3.2", "00:00:00"]


def test_status_text_uptime_is_days_hours_minutes(monkeypatch, tmp_path):
    make_guest(tmp_path, "dev-a")
    seconds = 2 * 86400 + 5 * 3600 + 7 * 60 + 30

    out = run_status_text(monkeypatch, tmp_path, pid=1234, attached_state="device",
                          stats={"mem_mb": 612, "cpu_percent": 3.2, "uptime_s": seconds})

    row = out.splitlines()[1].split()
    assert row[7] == "02:05:07"


def test_status_text_mem_cpu_and_uptime_are_blank_when_process_stats_fails(monkeypatch, tmp_path):
    make_guest(tmp_path, "dev-a")

    out = run_status_text(monkeypatch, tmp_path, pid=1234, attached_state="device", stats=None)

    row = out.splitlines()[1].split()
    assert row[5:8] == ["-", "-", "-"]
