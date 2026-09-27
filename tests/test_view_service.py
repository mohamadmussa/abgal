"""Covers the hardening in view/view-service.py, from issue #81.

Every test starts its own ThreadingHTTPServer on a free loopback port and
talks to it with http.client, so headers such as Host and Origin can be set
freely. No adb and no abgal binary run here, guest_status, guest_rows and
guest_action are always monkeypatched.
"""

import contextlib
import http.client
import importlib.util
import json
import shlex
import threading
import time
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

loader = SourceFileLoader("view_service", str(ROOT / "view" / "view-service.py"))
spec = importlib.util.spec_from_loader("view_service", loader)
view_service = importlib.util.module_from_spec(spec)
loader.exec_module(view_service)

TOKEN = "test-token-a1b2c3d4e5"


@contextlib.contextmanager
def running_server(token, allow_hosts=()):
    srv = view_service.make_server("127.0.0.1", 0, 2, token, allow_hosts)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.fixture
def server():
    with running_server(TOKEN) as srv:
        yield srv


def request(server, method, path, host=None, token=None, origin=None,
            content_type=None, body=None):
    """Sends one request and returns (status, decoded body)."""
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    headers = {}
    if host is not None:
        headers["Host"] = host
    if token is not None:
        headers["X-AbGal-Token"] = token
    if origin is not None:
        headers["Origin"] = origin
    if content_type is not None:
        headers["Content-Type"] = content_type
    data = body.encode("utf-8") if isinstance(body, str) else body
    try:
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        text = resp.read().decode("utf-8", "replace")
        return resp.status, text
    finally:
        conn.close()


def host_for(server):
    return "127.0.0.1:%d" % server.server_port


class RecordingDevice(view_service.Device):
    """A Device whose adb calls are recorded instead of run for real."""

    def __init__(self):
        super().__init__("fake-serial", 2)
        self.width = 100
        self.height = 100
        self.calls = []

    def adb(self, *args, binary=False):
        self.calls.append(args)
        return b"" if binary else ""


def test_index_page_serves_with_the_token(server):
    status, body = request(server, "GET", "/", host=host_for(server))

    assert status == 200
    assert TOKEN in body


def test_guests_route_needs_the_right_token(server, monkeypatch):
    monkeypatch.setattr(view_service, "guest_status",
                        lambda: {"guests": [], "free_mb": 1})
    host = host_for(server)

    status, _ = request(server, "GET", "/guests", host=host)
    assert status == 403

    status, _ = request(server, "GET", "/guests", host=host, token="wrong")
    assert status == 403

    non_ascii_token = "wrong-" + chr(233)
    status, _ = request(server, "GET", "/guests", host=host, token=non_ascii_token)
    assert status == 403

    status, _ = request(server, "GET", "/guests", host=host, token=TOKEN)
    assert status == 200


def test_host_header_is_checked_before_the_token(server, monkeypatch):
    monkeypatch.setattr(view_service, "guest_status",
                        lambda: {"guests": [], "free_mb": 1})
    port = server.server_port

    status, _ = request(server, "GET", "/guests",
                        host="evil.example:%d" % port, token=TOKEN)
    assert status == 403

    for host in ("localhost:%d" % port, "127.0.0.1:%d" % port,
                 "[::1]:%d" % port):
        status, _ = request(server, "GET", "/guests", host=host, token=TOKEN)
        assert status == 200


def test_allow_host_option_accepts_a_named_host(monkeypatch):
    monkeypatch.setattr(view_service, "guest_status",
                        lambda: {"guests": [], "free_mb": 1})
    with running_server(TOKEN, allow_hosts=("myhost",)) as srv:
        host = "myhost:%d" % srv.server_port
        status, _ = request(srv, "GET", "/guests", host=host, token=TOKEN)
        assert status == 200


def test_origin_must_match_the_host_header(server, monkeypatch):
    monkeypatch.setattr(view_service, "guest_status",
                        lambda: {"guests": [], "free_mb": 1})
    host = host_for(server)

    status, _ = request(server, "GET", "/guests", host=host, token=TOKEN,
                        origin="http://evil.example")
    assert status == 403

    status, _ = request(server, "GET", "/guests", host=host, token=TOKEN,
                        origin="http://" + host)
    assert status == 200

    status, _ = request(server, "GET", "/guests", host=host, token=TOKEN)
    assert status == 200


def test_post_tap_content_type_and_body_checks(server):
    host = host_for(server)

    status, _ = request(server, "POST", "/tap", host=host, token=TOKEN,
                        content_type="text/plain", body="{}")
    assert status == 415

    status, _ = request(server, "POST", "/tap", host=host, token=TOKEN,
                        content_type="application/json", body="not json")
    assert status == 400

    status, _ = request(server, "POST", "/tap", host=host, token=TOKEN,
                        content_type="application/json", body="[1, 2]")
    assert status == 400


@pytest.mark.parametrize("word", ["a b", "x;reboot", "$(id)", "it's", "`id`"])
def test_type_text_quotes_the_whole_word_as_one_argument(word):
    device = RecordingDevice()

    device.type_text(word)

    assert len(device.calls) == 1
    args = device.calls[0]
    assert args[0] == "shell"
    assert args[1] == "input"
    assert args[2] == "text"
    assert len(args) == 4
    recovered = shlex.split(args[3])
    assert recovered == [word.replace(" ", "%s")]


def test_post_text_with_a_control_character_returns_400(server):
    device = RecordingDevice()
    server.device = device
    server.selected = "g1"
    host = host_for(server)

    status, body = request(server, "POST", "/text", host=host, token=TOKEN,
                           content_type="application/json",
                           body=json.dumps({"word": "a\nb"}))

    assert status == 400
    assert device.calls == []


def test_a_route_that_raises_answers_with_a_generic_500(server, monkeypatch):
    def boom():
        raise RuntimeError("secret admin password hunter2")

    monkeypatch.setattr(view_service, "guest_status", boom)
    host = host_for(server)

    status, body = request(server, "GET", "/guests", host=host, token=TOKEN)

    assert status == 500
    assert body == "internal error, see the service log"
    assert "secret" not in body


def test_lifecycle_lock_refuses_a_second_call_for_the_same_guest(server, monkeypatch):
    release = threading.Event()

    def fake_guest_action(name, action):
        release.wait(timeout=5)

    monkeypatch.setattr(view_service, "guest_action", fake_guest_action)
    host = host_for(server)
    results = {}

    def call(name, key):
        status, _ = request(server, "POST", "/lifecycle", host=host, token=TOKEN,
                            content_type="application/json",
                            body=json.dumps({"name": name, "action": "start"}))
        results[key] = status

    first = threading.Thread(target=call, args=("g1", "g1"))
    first.start()

    deadline = time.time() + 5
    while "g1" not in server.busy and time.time() < deadline:
        time.sleep(0.01)
    assert "g1" in server.busy

    status, _ = request(server, "POST", "/lifecycle", host=host, token=TOKEN,
                        content_type="application/json",
                        body=json.dumps({"name": "g1", "action": "start"}))
    assert status == 409

    second = threading.Thread(target=call, args=("g2", "g2"))
    second.start()

    deadline = time.time() + 5
    while "g2" not in server.busy and time.time() < deadline:
        time.sleep(0.01)
    assert "g2" in server.busy

    release.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert results["g1"] == 200
    assert results["g2"] == 200
    assert server.busy == set()


def test_lifecycle_passes_abgals_reason_to_the_page(server, monkeypatch):
    def refuse(name, action):
        raise view_service.GuestActionError("not enough free memory to start g1")

    monkeypatch.setattr(view_service, "guest_action", refuse)
    status, body = request(server, "POST", "/lifecycle", host=host_for(server),
                           token=TOKEN, content_type="application/json",
                           body=json.dumps({"name": "g1", "action": "start"}))

    assert status == 409
    assert body == "not enough free memory to start g1"
    assert server.busy == set()


def test_each_refusal_says_what_to_do(server, monkeypatch):
    monkeypatch.setattr(view_service, "guest_status",
                        lambda: {"guests": [], "free_mb": 1})
    host = host_for(server)

    _, body = request(server, "GET", "/guests", host=host, token="old")
    assert "reload the page" in body

    _, body = request(server, "GET", "/guests",
                      host="box:%d" % server.server_port, token=TOKEN)
    assert "--allow-host box" in body

    _, body = request(server, "GET", "/guests", host=host, token=TOKEN,
                      origin="http://evil.example")
    assert "address the service printed" in body

    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        conn.putrequest("GET", "/guests", skip_host=True)
        conn.putheader("X-AbGal-Token", TOKEN)
        conn.endheaders()
        resp = conn.getresponse()
        assert resp.status == 403
        assert "address the service printed" in resp.read().decode("utf-8")
    finally:
        conn.close()


def test_host_names_compare_without_case(monkeypatch):
    monkeypatch.setattr(view_service, "guest_status",
                        lambda: {"guests": [], "free_mb": 1})
    with running_server(TOKEN, allow_hosts=("MyBox",)) as srv:
        for name in ("mybox", "MyBox", "LOCALHOST"):
            host = "%s:%d" % (name, srv.server_port)
            status, _ = request(srv, "GET", "/guests", host=host, token=TOKEN)
            assert status == 200, name


@pytest.mark.parametrize("name", [None, "", ["g1"], 5])
def test_lifecycle_refuses_a_name_that_is_not_a_string(server, monkeypatch, name):
    monkeypatch.setattr(view_service, "guest_action",
                        lambda n, a: pytest.fail("guest_action must not run"))
    status, _ = request(server, "POST", "/lifecycle", host=host_for(server),
                        token=TOKEN, content_type="application/json",
                        body=json.dumps({"name": name, "action": "start"}))
    assert status == 400


def test_a_content_length_that_is_not_a_number_is_a_bad_request(server):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        conn.putrequest("POST", "/tap", skip_host=True)
        conn.putheader("Host", host_for(server))
        conn.putheader("X-AbGal-Token", TOKEN)
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", "abc")
        conn.endheaders()
        assert conn.getresponse().status == 400
    finally:
        conn.close()
