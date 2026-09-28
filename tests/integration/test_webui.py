"""abgal webui against the real view-service.py, as its own process.

The unit tests only look at the command line. This one runs it, so a flag
that view-service.py does not know fails here instead of on a user's machine.
"""

import http.client
import os
import socket
import subprocess

import abgal


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_the_command_line_starts_a_view_that_serves_the_page():
    port = free_port()
    args = abgal.build_parser().parse_args(
        ["webui", "--address", "127.0.0.1", "--port", str(port), "--allow-host", "lab"])
    # Into a pipe Python buffers by the block, so the line below would wait.
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    service = subprocess.Popen(abgal.webui_command(args), stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, env=env)
    try:
        # The service prints this line once it is bound, before it serves.
        assert "View listens on http://127.0.0.1:%d/" % port in service.stdout.readline()

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/", headers={"Host": "lab:%d" % port})
        response = conn.getresponse()

        assert response.status == 200
        assert b"abgal-token" in response.read()
    finally:
        service.terminate()
        service.wait(timeout=10)
