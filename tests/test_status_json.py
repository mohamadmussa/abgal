"""abgal status --json, the machine readable shape view-service.py reads."""

import io
import json
from contextlib import redirect_stdout

import abgal


def make_guest(tmp_path, name, template="phone-1080x2400-480-api35-x86_64"):
    folder = tmp_path / (name + ".avd")
    folder.mkdir()
    (folder / "abgal-template").write_text(template)
    return folder


def run_status_json(monkeypatch, tmp_path, **kwargs):
    monkeypatch.setattr(abgal, "AVD", tmp_path)
    monkeypatch.setattr(abgal, "attached", lambda: {})
    monkeypatch.setattr(abgal, "available_mb", lambda: 4096)
    args = abgal.build_parser().parse_args(["status", "--json", *kwargs.get("extra", [])])
    out = io.StringIO()
    with redirect_stdout(out):
        abgal.cmd_status(args)
    return json.loads(out.getvalue())


def test_status_json_lists_every_guest_on_disk(monkeypatch, tmp_path):
    make_guest(tmp_path, "dev-a")
    make_guest(tmp_path, "dev-b")

    result = run_status_json(monkeypatch, tmp_path)

    assert result["free_mb"] == 4096
    names = {g["name"] for g in result["guests"]}
    assert names == {"dev-a", "dev-b"}


def test_status_json_reports_no_pid_or_serial_when_not_running(monkeypatch, tmp_path):
    make_guest(tmp_path, "dev-a")

    result = run_status_json(monkeypatch, tmp_path)

    row = result["guests"][0]
    assert row["pid"] is None
    assert row["serial"] is None
    assert row["adb"] is None
    assert row["stats"] is None


def test_status_json_with_no_guests_on_disk_is_an_empty_list(monkeypatch, tmp_path):
    result = run_status_json(monkeypatch, tmp_path)

    assert result["guests"] == []
