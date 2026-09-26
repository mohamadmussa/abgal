#!/usr/bin/env python3
"""View and control for the Android emulator, as a small HTTP service.

It listens on loopback by default, 127.0.0.1, so it is only reachable from
the same machine. Pass --address to bind to a different interface if the
service needs to be reached from elsewhere.

  python3 view-service.py [--guest name] [--address 127.0.0.1]
                          [--port 8099] [--step 2]

The page lists every guest abgal knows about and a viewer can switch
between them without restarting this service. --guest only preselects one
that is already running, it does not have to be given.

The image is fetched raw and resized and packed here. Measured on 2026-09-21:
the PNG from the device costs 1.34 s per frame, fetching raw and halving it
costs 0.73 s. No extra library is needed for that, zlib is enough.
"""
import argparse
import json
import struct
import subprocess
import threading
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# abgal sits one folder up from this file, and is the one place guest state
# is read from, see docs/architecture.md. This script never reads avd/ or
# /proc for a guest itself, it only asks abgal.
ABGAL = Path(__file__).resolve().parent.parent / "abgal"

# Keys the page is allowed to trigger. Without this list any keyevent would
# be possible, even POWER or SLEEP in the middle of a run.
KEYS = {
    "BACK": "KEYCODE_BACK",
    "HOME": "KEYCODE_HOME",
    "APP_SWITCH": "KEYCODE_APP_SWITCH",
    "ENTER": "KEYCODE_ENTER",
    "DEL": "KEYCODE_DEL",
    "TAB": "KEYCODE_TAB",
    "SEARCH": "KEYCODE_SEARCH",
    "VOLUME_UP": "KEYCODE_VOLUME_UP",
    "VOLUME_DOWN": "KEYCODE_VOLUME_DOWN",
}

camera = threading.Lock()


class Device:
    def __init__(self, serial, step):
        self.serial = serial
        self.step = step
        self.width = 0
        self.height = 0

    def adb(self, *args, binary=False):
        result = subprocess.run(
            ["adb", "-s", self.serial, *args],
            capture_output=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
        return result.stdout if binary else result.stdout.decode("utf-8", "replace")

    def screenshot(self, step=None):
        """Fetches the screen raw, shrinks it, and packs it as a PNG."""
        step = step or self.step
        with camera:
            raw = self.adb("exec-out", "screencap", binary=True)
        width, height = struct.unpack("<II", raw[:8])
        if len(raw) < 16 + width * height * 4:
            raise RuntimeError("capture incomplete")
        self.width, self.height = width, height

        pixels = memoryview(raw)[16:]
        out_w, out_h = width // step, height // step
        rows = bytearray()
        for y in range(out_h):
            start = y * step * width * 4
            row = pixels[start:start + width * 4]
            rows.append(0)                        # filter byte per row
            for x in range(out_w):
                i = x * step * 4
                rows += row[i:i + 3]              # RGBA to RGB
        return png(out_w, out_h, bytes(rows))

    def tap(self, x, y):
        self.adb("shell", "input", "tap", str(x), str(y))

    def swipe(self, x1, y1, x2, y2, duration):
        self.adb("shell", "input", "swipe",
                 str(x1), str(y1), str(x2), str(y2), str(duration))

    def press_key(self, name):
        self.adb("shell", "input", "keyevent", KEYS[name])

    def type_text(self, word):
        # input text does not understand spaces, %s stands in for one.
        self.adb("shell", "input", "text", word.replace(" ", "%s"))

    def size(self):
        if not self.width:
            self.screenshot()
        return self.width, self.height


def guest_status():
    """The whole "abgal status --json" payload: free_mb plus every guest.

    Guest listing, pid, adb state and free_mb live in abgal, see
    docs/architecture.md, this only parses what it already computed.
    """
    result = subprocess.run(
        [str(ABGAL), "status", "--json"],
        capture_output=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return json.loads(result.stdout)


def guest_rows():
    return guest_status()["guests"]


def png(width, height, rows):
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)   # 2 means RGB
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(rows, 1))
            + chunk(b"IEND", b""))


PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>Emulator</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root { color-scheme: dark; --bg:#16181d; --field:#20242c; --border:#333944;
          --text:#e6e9ef; --muted:#9aa3b2; --accent:#5b9cf8;
          --ok:#4caf7d; --warn:#d9a441; --off:#6b7280; }
  * { box-sizing:border-box; }
  html, body { height:100%; }
  body { margin:0; background:var(--bg); color:var(--text);
         font:14px/1.5 system-ui,sans-serif; display:grid; gap:16px; padding:16px;
         grid-template-columns:260px minmax(0,1fr) 260px;
         grid-template-rows:auto minmax(0,1fr);
         grid-template-areas:"header header header" "guests screen controls"; }
  #topbar { grid-area:header; display:flex; justify-content:space-between;
            background:var(--field); border:1px solid var(--border);
            border-radius:10px; padding:8px 14px; color:var(--muted);
            font-size:13px; font-variant-numeric:tabular-nums; }
  nav#guests { grid-area:guests; min-width:0; overflow-y:auto;
               display:flex; flex-direction:column; gap:14px; }
  aside { grid-area:controls; min-width:0; overflow-y:auto;
          display:flex; flex-direction:column; gap:14px; }
  #screen-wrap { grid-area:screen; position:relative; min-width:0; min-height:0;
                 display:flex; align-items:flex-start; justify-content:center; }
  #screen { border:1px solid var(--border); border-radius:10px; cursor:crosshair;
          max-width:100%; max-height:100%; background:#000; display:block; }
  #placeholder { position:absolute; inset:0; display:none; align-items:center;
          justify-content:center; color:var(--muted); border:1px dashed var(--border);
          border-radius:10px; text-align:center; padding:20px; }
  #placeholder.visible { display:flex; }
  fieldset { border:1px solid var(--border); border-radius:10px; padding:12px;
             margin:0; }
  legend { color:var(--muted); padding:0 6px; font-size:12px;
           text-transform:uppercase; letter-spacing:.06em; }
  .row { display:flex; gap:8px; flex-wrap:wrap; }
  button { background:var(--field); color:var(--text); border:1px solid var(--border);
           border-radius:8px; padding:8px 12px; cursor:pointer; font-size:13px; }
  button:hover { border-color:var(--accent); }
  input[type=text] { flex:1; min-width:0; background:var(--field);
                     color:var(--text); border:1px solid var(--border);
                     border-radius:8px; padding:8px; }
  label { color:var(--muted); display:flex; align-items:center; gap:8px; }
  #status { color:var(--muted); font-size:12px; min-height:1.4em; }
  .guest { display:flex; flex-direction:column; gap:4px; min-width:0;
           background:var(--field); border:1px solid var(--border); border-radius:8px;
           padding:8px 10px; }
  .guest.selected { border-color:var(--accent); background:#1c2636; }
  .guest .top { display:flex; justify-content:space-between; gap:6px; align-items:center;
                min-width:0; }
  .device-btn { flex:1; min-width:0; text-align:left; overflow:hidden;
                text-overflow:ellipsis; white-space:nowrap; font-weight:600;
                padding:4px 8px; }
  .device-btn:disabled { cursor:not-allowed; opacity:.55; }
  .expand { flex:none; padding:4px 6px; color:var(--muted); font-size:11px; line-height:1; }
  .expand.open { color:var(--text); }
  .details { display:none; flex-direction:column; gap:2px; color:var(--muted);
             font-size:12px; padding:2px 8px 4px; }
  .details.open { display:flex; }
  .pill { flex:none; font-size:11px; padding:1px 7px; border-radius:99px; white-space:nowrap; }
  .pill.running { background:rgba(76,175,125,.18); color:var(--ok); }
  .pill.booting { background:rgba(217,164,65,.18); color:var(--warn); }
  .pill.stopped, .pill.unknown { background:rgba(107,114,128,.2); color:var(--off); }
</style>

<header id="topbar">
  <span id="frame-time">- ms per frame</span>
  <span id="free-mem">free: - MB</span>
</header>

<nav id="guests">
  <fieldset>
    <legend>GUESTS</legend>
    <div id="guest-list" style="display:flex; flex-direction:column; gap:8px"></div>
  </fieldset>
</nav>

<div id="screen-wrap">
  <img id="screen" alt="emulator screen" hidden>
  <div id="placeholder" class="visible">Select a guest from the list on the left.</div>
</div>

<aside>
  <fieldset>
    <legend>SCREEN</legend>
    <label><input type="checkbox" id="auto-refresh" checked> auto refresh</label>
    <div class="row" style="margin-top:8px">
      <button data-step="1">FULL</button>
      <button data-step="2">HALF</button>
      <button data-step="3">SMALL</button>
      <button id="now">NOW</button>
    </div>
  </fieldset>

  <fieldset>
    <legend>KEYS</legend>
    <div class="row">
      <button data-key="BACK">BACK</button>
      <button data-key="HOME">HOME</button>
      <button data-key="APP_SWITCH">APP_SWITCH</button>
      <button data-key="ENTER">ENTER</button>
      <button data-key="DEL">DEL</button>
      <button data-key="TAB">TAB</button>
    </div>
  </fieldset>

  <fieldset>
    <legend>SWIPE</legend>
    <div class="row">
      <button data-swipe="up">UP</button>
      <button data-swipe="down">DOWN</button>
      <button data-swipe="left">LEFT</button>
      <button data-swipe="right">RIGHT</button>
    </div>
  </fieldset>

  <fieldset>
    <legend>TEXT</legend>
    <div class="row">
      <input type="text" id="word" placeholder="type, then Enter">
    </div>
  </fieldset>

  <div id="status"></div>
</aside>

<script>
const img = document.getElementById("screen");
const placeholder = document.getElementById("placeholder");
const guestList = document.getElementById("guest-list");
const statusEl = document.getElementById("status");
const frameTimeEl = document.getElementById("frame-time");
const freeMemEl = document.getElementById("free-mem");
const autoRefresh = document.getElementById("auto-refresh");
let step = 2, loading = false, lastMs = 0, selected = null;
let lastRows = [], expanded = new Set();

function report(t) { statusEl.textContent = t; }

function pillState(g) {
  if (!g.pid) return "stopped";
  if (g.adb === "device") return "running";
  if (g.adb === "unauthorized") return "unknown";
  return "booting";
}

function renderGuests(rows) {
  lastRows = rows;
  guestList.innerHTML = "";
  for (const g of rows) {
    const state = pillState(g);
    const row = document.createElement("div");
    row.className = "guest" + (g.name === selected ? " selected" : "");

    const top = document.createElement("div");
    top.className = "top";

    const deviceBtn = document.createElement("button");
    deviceBtn.className = "device-btn";
    deviceBtn.disabled = state !== "running";
    deviceBtn.textContent = g.serial || g.name;
    deviceBtn.title = g.name;
    deviceBtn.onclick = () => selectGuest(g.name);

    const pill = document.createElement("span");
    pill.className = "pill " + state;
    pill.textContent = state;

    const arrow = document.createElement("button");
    arrow.className = "expand" + (expanded.has(g.name) ? " open" : "");
    arrow.textContent = expanded.has(g.name) ? "v" : ">";
    arrow.setAttribute("aria-label", "details for " + g.name);
    arrow.onclick = () => {
      if (expanded.has(g.name)) expanded.delete(g.name);
      else expanded.add(g.name);
      renderGuests(lastRows);
    };

    top.append(deviceBtn, pill, arrow);

    const details = document.createElement("div");
    details.className = "details" + (expanded.has(g.name) ? " open" : "");
    for (const [k, v] of [
      ["name", g.name],
      ["template", g.template],
      ["id", g.id],
      ["adb", g.adb ?? "-"],
      ["memory", g.stats ? g.stats.mem_mb + " MB" : "-"],
      ["cpu", g.stats ? g.stats.cpu_percent + "%" : "-"],
    ]) {
      const line = document.createElement("div");
      line.textContent = k + ": " + v;
      details.appendChild(line);
    }

    row.append(top, details);
    guestList.appendChild(row);
  }
}

async function refreshGuests() {
  try {
    const a = await fetch("guests?t=" + Date.now());
    if (!a.ok) throw new Error(await a.text());
    const data = await a.json();
    selected = data.selected;
    img.hidden = !selected;
    placeholder.classList.toggle("visible", !selected);
    freeMemEl.textContent = "free: " + data.free_mb + " MB";
    renderGuests(data.guests);
  } catch (e) {
    report("error: " + e.message);
  }
}

async function selectGuest(name) {
  try {
    const a = await fetch("switch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name })
    });
    if (!a.ok) throw new Error(await a.text());
    await refreshGuests();
    fetchFrame();
  } catch (e) {
    report("error: " + e.message);
  }
}

async function fetchFrame() {
  if (!selected || loading) return;
  loading = true;
  const start = performance.now();
  try {
    const a = await fetch("frame.png?s=" + step + "&t=" + Date.now());
    if (!a.ok) throw new Error(await a.text());
    const prev = img.src;
    img.src = URL.createObjectURL(await a.blob());
    if (prev.startsWith("blob:")) URL.revokeObjectURL(prev);
    lastMs = Math.round(performance.now() - start);
    frameTimeEl.textContent = lastMs + " ms per frame";
  } catch (e) {
    report("error: " + e.message);
  } finally {
    loading = false;
  }
}

async function send(route, data) {
  try {
    const a = await fetch(route, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
    if (!a.ok) throw new Error(await a.text());
    setTimeout(fetchFrame, 350);
  } catch (e) {
    report("error: " + e.message);
  }
}

// The browser sends the fraction, not the pixel. That way the page does not
// need to know the device resolution or the downscale step. A press that
// releases close to where it started is a tap, a press that moves is a
// drag, sent as a swipe between the two fractions.
function fraction(e) {
  const r = img.getBoundingClientRect();
  return { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height };
}

let dragStart = null;

img.addEventListener("mousedown", (e) => { dragStart = fraction(e); });

img.addEventListener("mouseup", (e) => {
  if (!dragStart) return;
  const r = img.getBoundingClientRect();
  const end = fraction(e);
  const movedPx = Math.hypot((end.x - dragStart.x) * r.width,
                              (end.y - dragStart.y) * r.height);
  if (movedPx < 6) {
    send("tap", { ax: dragStart.x, ay: dragStart.y });
  } else {
    send("swipe", { ax1: dragStart.x, ay1: dragStart.y, ax2: end.x, ay2: end.y });
  }
  dragStart = null;
});

img.addEventListener("mouseleave", () => { dragStart = null; });

document.querySelectorAll("[data-key]").forEach(b =>
  b.onclick = () => send("key", { name: b.dataset.key }));

document.querySelectorAll("[data-swipe]").forEach(b =>
  b.onclick = () => send("swipe", { direction: b.dataset.swipe }));

document.querySelectorAll("[data-step]").forEach(b =>
  b.onclick = () => { step = +b.dataset.step; fetchFrame(); });

document.getElementById("now").onclick = fetchFrame;

document.getElementById("word").addEventListener("keydown", (e) => {
  if (e.key !== "Enter" || !e.target.value) return;
  send("text", { word: e.target.value });
  e.target.value = "";
});

(async function loop() {
  for (;;) {
    if (autoRefresh.checked) await fetchFrame();
    await new Promise(r => setTimeout(r, 120));
  }
})();

(async function guestLoop() {
  for (;;) {
    await refreshGuests();
    await new Promise(r => setTimeout(r, 3000));
  }
})();
</script>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "abgal-view"

    def respond(self, code, content_type, body):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def route(self):
        return self.path.split("?")[0].strip("/")

    def do_GET(self):
        p = self.route()
        try:
            if p in ("", "index.html"):
                return self.respond(200, "text/html; charset=utf-8", PAGE)
            if p == "guests":
                payload = guest_status()
                return self.respond(200, "application/json", json.dumps({
                    "selected": self.server.selected,
                    "guests": payload["guests"],
                    "free_mb": payload["free_mb"],
                }))
            if self.server.device is None:
                return self.respond(409, "text/plain; charset=utf-8", "no guest selected")
            if p == "frame.png":
                step = 2
                if "s=" in self.path:
                    raw = self.path.split("s=")[1].split("&")[0]
                    if not raw.isdigit():
                        return self.respond(400, "text/plain; charset=utf-8", "bad s")
                    step = max(1, min(6, int(raw)))
                return self.respond(200, "image/png", self.server.device.screenshot(step))
            if p == "size":
                w, h = self.server.device.size()
                return self.respond(200, "application/json",
                                    json.dumps({"width": w, "height": h}))
            self.respond(404, "text/plain; charset=utf-8", "unknown")
        except Exception as e:
            self.respond(500, "text/plain; charset=utf-8", str(e))

    def do_POST(self):
        p = self.route()
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")

            if p == "switch":
                return self.switch_guest(data.get("name"))

            if self.server.device is None:
                return self.respond(409, "text/plain; charset=utf-8", "no guest selected")
            d = self.server.device
            width, height = d.size()

            if p == "tap":
                x = int(float(data["ax"]) * width)
                y = int(float(data["ay"]) * height)
                d.tap(max(0, min(width - 1, x)), max(0, min(height - 1, y)))
            elif p == "key":
                name = data["name"]
                if name not in KEYS:
                    return self.respond(400, "text/plain; charset=utf-8", "key locked")
                d.press_key(name)
            elif p == "text":
                d.type_text(str(data["word"])[:200])
            elif p == "swipe":
                if "direction" in data:
                    mx, my = width // 2, height // 2
                    reach = height // 3
                    pairs = {
                        "up":    (mx, my + reach, mx, my - reach),
                        "down":  (mx, my - reach, mx, my + reach),
                        "left":  (mx + reach, my, mx - reach, my),
                        "right": (mx - reach, my, mx + reach, my),
                    }
                    if data["direction"] not in pairs:
                        return self.respond(400, "text/plain; charset=utf-8", "unknown")
                    d.swipe(*pairs[data["direction"]], 220)
                else:
                    x1 = max(0, min(width - 1, int(float(data["ax1"]) * width)))
                    y1 = max(0, min(height - 1, int(float(data["ay1"]) * height)))
                    x2 = max(0, min(width - 1, int(float(data["ax2"]) * width)))
                    y2 = max(0, min(height - 1, int(float(data["ay2"]) * height)))
                    d.swipe(x1, y1, x2, y2, 220)
            else:
                return self.respond(404, "text/plain; charset=utf-8", "unknown")

            self.respond(200, "application/json", '{"ok":true}')
        except Exception as e:
            self.respond(500, "text/plain; charset=utf-8", str(e))

    def switch_guest(self, name):
        """Points the server at a different guest's serial, or refuses.

        Only a guest with a live serial, adb state "device", can be shown
        and driven. A guest still booting or already stopped has nothing
        for adb to talk to yet.
        """
        try:
            rows = guest_rows()
        except Exception as e:
            return self.respond(500, "text/plain; charset=utf-8", str(e))
        found = next((g for g in rows if g["name"] == name), None)
        if found is None:
            return self.respond(404, "text/plain; charset=utf-8", "no such guest")
        if found["adb"] != "device":
            return self.respond(409, "text/plain; charset=utf-8",
                                "guest is not ready to view: " + str(found["adb"]))
        self.server.device = Device(found["serial"], self.server.step)
        self.server.selected = name
        self.respond(200, "application/json", '{"ok":true}')

    def log_message(self, *_):
        pass


def main():
    t = argparse.ArgumentParser(description="View and control for the emulator")
    t.add_argument("--guest", help="a guest to preselect, it must already be running")
    t.add_argument("--address", default="127.0.0.1")
    t.add_argument("--port", type=int, default=8099)
    t.add_argument("--step", type=int, default=2)
    a = t.parse_args()

    service = ThreadingHTTPServer((a.address, a.port), Handler)
    service.step = a.step
    service.device = None
    service.selected = None
    if a.guest:
        found = next((g for g in guest_rows() if g["name"] == a.guest), None)
        if found is None or found["adb"] != "device":
            print(f"'{a.guest}' is not visible on adb yet, starting with no guest selected.")
        else:
            service.device = Device(found["serial"], a.step)
            service.selected = a.guest

    print(f"View listens on http://{a.address}:{a.port}/")
    try:
        service.serve_forever()
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
