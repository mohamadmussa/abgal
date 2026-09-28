"""abgal webui, the command line it hands to view-service.py and its warning."""

import io
from contextlib import redirect_stdout

import pytest

import abgal


def parse(*extra):
    return abgal.build_parser().parse_args(["webui", *extra])


def test_webui_listens_on_every_interface_by_default():
    command = abgal.webui_command(parse())

    assert command[:2] == [abgal.sys.executable, str(abgal.VIEW_SERVICE)]
    assert command[2:] == ["--address", "0.0.0.0"]


def test_webui_leaves_the_port_to_the_view_service():
    assert "--port" not in abgal.webui_command(parse())


def test_webui_passes_every_option_through():
    args = parse("--address", "127.0.0.1", "--port", "8100", "--guest", "dev-01",
                 "--allow-host", "lab", "--allow-host", "lab.local")

    assert abgal.webui_command(args)[2:] == [
        "--address", "127.0.0.1", "--port", "8100", "--guest", "dev-01",
        "--allow-host", "lab", "--allow-host", "lab.local"]


@pytest.mark.parametrize("address, warned", [
    ("0.0.0.0", True),
    ("192.0.2.20", True),
    ("127.0.0.1", False),
    ("::1", False),
])
def test_webui_warns_unless_on_loopback(monkeypatch, address, warned):
    monkeypatch.setattr(abgal.subprocess, "run",
                        lambda command: type("Done", (), {"returncode": 0})())
    out = io.StringIO()
    with redirect_stdout(out):
        code = abgal.cmd_webui(parse("--address", address))

    assert code == 0
    assert ("Anyone who can reach this address" in out.getvalue()) is warned


def test_webui_returns_the_exit_code_of_the_view_service(monkeypatch):
    monkeypatch.setattr(abgal.subprocess, "run",
                        lambda command: type("Done", (), {"returncode": 3})())

    with redirect_stdout(io.StringIO()):
        assert abgal.cmd_webui(parse("--address", "127.0.0.1")) == 3
