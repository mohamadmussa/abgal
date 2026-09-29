#!/usr/bin/env python3
"""View and control for the Android emulator, as a small HTTP service.

It listens on loopback by default, 127.0.0.1, so it is only reachable from
the same machine. Pass --address to bind to a different interface if the
service needs to be reached from elsewhere.

  python3 view-service.py [--guest name] [--address 127.0.0.1]
                          [--port 8099] [--step 2] [--allow-host name]

The page lists every guest abgal knows about and a viewer can switch
between them without restarting this service. --guest only preselects one
that is already running, it does not have to be given. Every request past
the page itself needs a per run token that the page reads from its own
head and sends back in a header.

The image is fetched raw and resized and packed here. Measured on 2026-09-21:
the PNG from the device costs 1.34 s per frame, fetching raw and halving it
costs 0.73 s. No extra library is needed for that, zlib is enough.
"""
import argparse
import hmac
import ipaddress
import json
import logging
import secrets
import struct
import subprocess
import threading
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

log = logging.getLogger("view-service")

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
        for ch in word:
            if ord(ch) < 32 or ord(ch) == 127:
                raise ValueError("control character in text")
        s = word.replace(" ", "%s")
        # adb shell hands its arguments to a shell on the device, so the
        # text has to arrive there as a single quoted word.
        quoted = "'" + s.replace("'", "'\\''") + "'"
        self.adb("shell", "input", "text", quoted)

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


def physical_devices(known_serials):
    """Real hardware "adb devices" shows that abgal does not know about.

    abgal's own attached() only recognizes serials starting with
    "emulator-", see abgal, so a phone or tablet on USB or adb connect
    never shows up in "abgal status --json". This asks adb directly and
    keeps whatever is left once the known guest serials are excluded, in
    the same row shape guest_rows() uses so the page can treat both
    alike, with "physical": True marking the difference.
    """
    result = subprocess.run(
        ["adb", "devices"], capture_output=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    rows = []
    for line in result.stdout.decode("utf-8", "replace").splitlines()[1:]:
        line = line.strip()
        if not line or "\t" not in line:
            continue
        serial, state = line.split("\t", 1)
        if serial in known_serials:
            continue
        rows.append({
            "name": serial, "id": None, "template": "physical device",
            "pid": None, "serial": serial, "adb": state, "stats": None,
            "physical": True,
        })
    return rows


def safe_physical_devices(known_serials):
    """physical_devices(), but a failed "adb devices" never takes the
    guest list down with it, an empty list of physical rows does.
    """
    try:
        return physical_devices(known_serials)
    except Exception:
        log.exception("physical_devices")
        return []


class GuestActionError(RuntimeError):
    """abgal refused or did not finish an action, the text is meant for the page."""


def guest_action(name, action):
    """Runs abgal start, stop or restart for one guest, blocking.

    Raises with abgal's own stderr on failure, so the page can show the
    real reason instead of a generic error. abgal itself waits up to
    --timeout (default 300 s) for the console and again up to --timeout
    for boot, one after another, so a start is passed the same --timeout
    explicitly and our own subprocess timeout is set well above both
    waits combined. A stop needs far less, abgal's own steps there are a
    20 s wait for "adb emu kill" to answer, then a 20 s grace period, a
    10 s SIGTERM wait and a 10 s SIGKILL wait, 60 s in the worst case,
    see abgal's start_one() and stop_one(). A subprocess timeout is
    turned into its own message rather than passed on as is, because its
    text otherwise repeats the absolute path to abgal from argv.
    """
    def run(extra_args, timeout):
        try:
            result = subprocess.run(
                [str(ABGAL), *extra_args, "-n", name],
                capture_output=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise GuestActionError(
                "abgal %s did not answer within %d s, %s may still be under way"
                % (extra_args[0], timeout, name)
            )
        if result.returncode != 0:
            raise GuestActionError(
                result.stderr.decode("utf-8", "replace").strip()
                or result.stdout.decode("utf-8", "replace").strip()
            )

    if action == "start":
        run(["start", "--timeout", "300"], 610)
    elif action == "stop":
        run(["stop"], 75)
    elif action == "restart":
        run(["stop"], 75)
        run(["start", "--timeout", "300"], 610)
    else:
        raise ValueError("unknown action: " + action)


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
<meta name="abgal-token" content="__ABGAL_TOKEN__">
<link rel="icon" type="image/png" href="data:image/png;base64,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">
<style>
  :root { color-scheme: dark; --bg:#01121c; --field:#20242c; --border:#333944;
          --text:#e6e9ef; --muted:#9aa3b2; --accent:#5b9cf8;
          --ok:#4caf7d; --warn:#d9a441; --off:#6b7280; --bad:#e0605a;
          --left-w:260px; --right-w:260px; --guests-h:260px; }
  * { box-sizing:border-box; }
  html, body { height:100%; }
  body { margin:0; background:var(--bg); color:var(--text);
         font:14px/1.5 system-ui,sans-serif; display:grid; gap:16px; padding:16px;
         grid-template-columns:var(--left-w) 6px minmax(0,1fr) 6px var(--right-w);
         grid-template-rows:auto minmax(0,1fr);
         grid-template-areas:"header header header header header"
                              "guests lresize screen rresize controls"; }
  body::before { content:""; position:fixed; inset:0; z-index:-1;
                 pointer-events:none; opacity:.04;
                 background:url(data:image/jpeg;base64,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) center/cover; }
  .resizer { cursor:col-resize; position:relative; }
  .resizer::after { content:""; position:absolute; top:0; bottom:0; left:2px;
                     width:2px; background:var(--border); border-radius:1px; }
  .resizer:hover::after { background:var(--accent); }
  #lresize { grid-area:lresize; }
  #rresize { grid-area:rresize; }
  .vresizer { cursor:row-resize; height:12px; flex:none; }
  .vresizer::after { content:""; position:absolute; left:0; right:0; top:5px;
                      height:2px; background:var(--border); border-radius:1px; }
  .vresizer:hover::after { background:var(--accent); }
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
  .pill { flex:none; width:9px; height:9px; border-radius:50%; }
  .pill.running { background:var(--ok); }
  .pill.booting { background:var(--warn); }
  .pill.stopped, .pill.unknown { background:var(--bad); }
  .details .actions { display:flex; gap:6px; margin-top:2px; }
  .details .actions button { padding:4px 8px; font-size:11px; }
  .details .actions span { color:var(--warn); }
  #debug-log { margin:0; max-height:220px; overflow-y:auto; font:11px/1.4 ui-monospace,monospace;
               color:var(--muted); white-space:pre-wrap; word-break:break-all; }
</style>

<header id="topbar">
  <span id="frame-time">- ms per frame</span>
  <span id="free-mem">free: - MB</span>
</header>

<nav id="guests">
  <fieldset style="flex:0 0 var(--guests-h); min-height:0; display:flex; flex-direction:column">
    <legend>GUESTS</legend>
    <div id="guest-list"
         style="display:flex; flex-direction:column; gap:8px; flex:1; min-height:0; overflow-y:auto"></div>
  </fieldset>

  <div id="vresize" class="resizer vresizer"></div>

  <fieldset style="flex:1; min-height:0; display:flex; flex-direction:column">
    <legend>DEBUG</legend>
    <label><input type="checkbox" id="debug-toggle"> show debug output</label>
    <pre id="debug-log" hidden></pre>
  </fieldset>
</nav>

<div id="lresize" class="resizer"></div>

<div id="screen-wrap">
  <img id="screen" alt="" hidden>
  <div id="placeholder" class="visible">Select a guest from the list on the left.</div>
</div>

<div id="rresize" class="resizer"></div>

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
      <button data-key="SEARCH">SEARCH</button>
      <button data-key="VOLUME_UP">VOLUME_UP</button>
      <button data-key="VOLUME_DOWN">VOLUME_DOWN</button>
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
const debugToggle = document.getElementById("debug-toggle");
const debugLogEl = document.getElementById("debug-log");
let step = 2, loading = false, lastMs = 0, selected = null;
let lastRows = [], expanded = new Set(), debugLines = [];
const pending = new Map();
const TOKEN = document.querySelector('meta[name="abgal-token"]').content;

// A plain cross site form or fetch cannot set this header without a CORS
// preflight, and this server never answers a preflight with permission,
// so only the page itself can produce a request that carries it.
function api(route, opts = {}) {
  opts.headers = Object.assign({ "X-AbGal-Token": TOKEN }, opts.headers || {});
  return fetch(route, opts);
}

function report(t) { statusEl.textContent = t; }

function debugLog(line) {
  const stamp = new Date().toISOString().split("T")[1].replace("Z", "");
  debugLines.push(stamp + "  " + line);
  if (debugLines.length > 80) debugLines.shift();
  if (debugToggle.checked) debugLogEl.textContent = debugLines.join("\\n");
}

debugToggle.addEventListener("change", () => {
  debugLogEl.hidden = !debugToggle.checked;
  if (debugToggle.checked) debugLogEl.textContent = debugLines.join("\\n");
});

function pillState(g) {
  if (g.physical) return g.adb === "device" ? "running" : "unknown";
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
    pill.title = state;

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
      ["id", g.id ?? "-"],
      ["adb", g.adb ?? "-"],
      ["memory", g.stats ? g.stats.mem_mb + " MB" : "-"],
      ["cpu", g.stats ? g.stats.cpu_percent + "%" : "-"],
      ["cores", g.cores ?? "-"],
    ]) {
      const line = document.createElement("div");
      line.textContent = k + ": " + v;
      details.appendChild(line);
    }

    const actions = document.createElement("div");
    actions.className = "actions";
    const busy = pending.get(g.name);
    if (g.physical) {
      // a physical device is not abgal's to start, stop or restart
    } else if (busy) {
      const span = document.createElement("span");
      span.textContent = busy + "…";
      actions.appendChild(span);
    } else {
      const hasPid = !!g.pid;
      for (const [label, action, disabled] of [
        ["Start", "start", hasPid],
        ["Stop", "stop", !hasPid],
        ["Restart", "restart", !hasPid],
      ]) {
        const btn = document.createElement("button");
        btn.textContent = label;
        btn.disabled = disabled;
        btn.onclick = () => runLifecycle(g.name, action, label.toLowerCase());
        actions.appendChild(btn);
      }
    }
    details.appendChild(actions);

    row.append(top, details);
    guestList.appendChild(row);
  }
}

async function refreshGuests() {
  try {
    const a = await api("guests?t=" + Date.now());
    if (!a.ok) throw new Error(await a.text());
    const data = await a.json();
    selected = data.selected;
    img.hidden = !selected;
    placeholder.classList.toggle("visible", !selected);
    freeMemEl.textContent = "free: " + data.free_mb + " MB";
    renderGuests(data.guests);
    debugLog("GET guests -> " + data.guests.length + " row(s), free_mb=" + data.free_mb);
  } catch (e) {
    report("error: " + e.message);
    debugLog("GET guests failed: " + e.message);
  }
}

async function selectGuest(name) {
  try {
    const a = await api("switch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name })
    });
    if (!a.ok) throw new Error(await a.text());
    debugLog("POST switch " + name + " -> ok");
    await refreshGuests();
    fetchFrame();
  } catch (e) {
    report("error: " + e.message);
    debugLog("POST switch " + name + " failed: " + e.message);
  }
}

async function runLifecycle(name, action, verb) {
  pending.set(name, verb);
  renderGuests(lastRows);
  try {
    const a = await api("lifecycle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, action })
    });
    if (!a.ok) throw new Error(await a.text());
    debugLog("POST lifecycle " + action + " " + name + " -> ok");
    report(name + ": " + action + " ok");
  } catch (e) {
    report(name + " " + action + " failed: " + e.message);
    debugLog("POST lifecycle " + action + " " + name + " failed: " + e.message);
  } finally {
    pending.delete(name);
    await refreshGuests();
  }
}

async function fetchFrame() {
  if (!selected || loading) return;
  loading = true;
  const start = performance.now();
  try {
    const a = await api("frame.png?s=" + step + "&t=" + Date.now());
    if (!a.ok) throw new Error(await a.text());
    const prev = img.src;
    img.src = URL.createObjectURL(await a.blob());
    if (prev.startsWith("blob:")) URL.revokeObjectURL(prev);
    lastMs = Math.round(performance.now() - start);
    frameTimeEl.textContent = lastMs + " ms per frame";
    debugLog("GET frame.png?s=" + step + " -> " + lastMs + " ms");
  } catch (e) {
    report("error: " + e.message);
    debugLog("GET frame.png failed: " + e.message);
  } finally {
    loading = false;
  }
}

async function send(route, data) {
  try {
    const a = await api(route, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
    if (!a.ok) throw new Error(await a.text());
    debugLog("POST " + route + " " + JSON.stringify(data) + " -> ok");
    setTimeout(fetchFrame, 350);
  } catch (e) {
    report("error: " + e.message);
    debugLog("POST " + route + " " + JSON.stringify(data) + " failed: " + e.message);
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

// Drags a sidebar's grid track width via a CSS custom property. "left"
// widens as the pointer moves right, "right" widens as it moves left.
function makeResizer(handle, cssVar, side) {
  handle.addEventListener("mousedown", (e) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = parseInt(getComputedStyle(document.documentElement)
                            .getPropertyValue(cssVar), 10);
    function onMove(ev) {
      const delta = side === "left" ? ev.clientX - startX : startX - ev.clientX;
      const next = Math.max(160, Math.min(480, startW + delta));
      document.documentElement.style.setProperty(cssVar, next + "px");
    }
    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}
makeResizer(document.getElementById("lresize"), "--left-w", "left");
makeResizer(document.getElementById("rresize"), "--right-w", "right");

// Drags the GUESTS/DEBUG split in the left column the same way, but along
// the vertical axis and against the guest list's flex-basis height.
function makeRowResizer(handle, cssVar) {
  handle.addEventListener("mousedown", (e) => {
    e.preventDefault();
    const startY = e.clientY;
    const startH = parseInt(getComputedStyle(document.documentElement)
                            .getPropertyValue(cssVar), 10);
    function onMove(ev) {
      const delta = ev.clientY - startY;
      const next = Math.max(80, Math.min(window.innerHeight - 200, startH + delta));
      document.documentElement.style.setProperty(cssVar, next + "px");
    }
    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}
makeRowResizer(document.getElementById("vresize"), "--guests-h");

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

    def host_ok(self, hostname):
        # Browsers send the host lower case, so every side is compared so.
        hostname = hostname.lower()
        if hostname == "localhost":
            return True
        try:
            ipaddress.ip_address(hostname)
            return True
        except ValueError:
            pass
        return hostname in {h.lower() for h in self.server.allow_hosts}

    def refused(self):
        """Checks Host, Origin and the token, before any route runs.

        DNS rebinding needs a DNS name, a literal address cannot be
        rebound, so a name has to be allowed on purpose with
        --allow-host. Origin, when sent, must name the same host as the
        request itself. Absent Origin is allowed, same origin GETs and
        command line clients send none, the token still applies.
        """
        host_header = self.headers.get("Host")
        if not host_header:
            self.respond(403, "text/plain; charset=utf-8",
                         "forbidden, no Host header, open the page at the "
                         "address the service printed")
            return True
        hostname = host_header
        if hostname.startswith("["):
            hostname = hostname.split("]")[0].lstrip("[")
        else:
            hostname = hostname.split(":")[0]
        if not self.host_ok(hostname):
            self.respond(403, "text/plain; charset=utf-8",
                         "forbidden, host %r is not allowed, start the service "
                         "with --allow-host %s" % (hostname, hostname))
            return True

        origin = self.headers.get("Origin")
        if origin:
            origin_host = origin.split("://", 1)[-1]
            if origin_host.lower() != host_header.lower():
                self.respond(403, "text/plain; charset=utf-8",
                             "forbidden, Origin does not match Host, open the "
                             "page at the address the service printed")
                return True

        p = self.route()
        if self.command == "GET" and p in ("", "index.html"):
            return False
        # A plain cross site form or fetch cannot set a custom header
        # without a CORS preflight, which this server never answers with
        # permission, so this header alone proves the page itself sent it.
        # Compared as bytes, compare_digest raises on a non ASCII str.
        given = self.headers.get("X-AbGal-Token", "").encode("utf-8", "replace")
        if not hmac.compare_digest(given, self.server.token.encode()):
            # The usual cause is a tab left open across a restart of the
            # service, which made a new token.
            self.respond(403, "text/plain; charset=utf-8",
                         "forbidden, token does not match, reload the page")
            return True
        return False

    def do_GET(self):
        if self.refused():
            return
        p = self.route()
        try:
            if p in ("", "index.html"):
                page = PAGE.replace("__ABGAL_TOKEN__", self.server.token)
                return self.respond(200, "text/html; charset=utf-8", page)
            if p == "guests":
                payload = guest_status()
                known = {g["serial"] for g in payload["guests"] if g["serial"]}
                rows = payload["guests"] + safe_physical_devices(known)
                return self.respond(200, "application/json", json.dumps({
                    "selected": self.server.selected,
                    "guests": rows,
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
        except Exception:
            log.exception("do_GET %s", p)
            self.respond(500, "text/plain; charset=utf-8",
                        "internal error, see the service log")

    def do_POST(self):
        if self.refused():
            return
        p = self.route()
        try:
            media = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if media != "application/json":
                return self.respond(415, "text/plain; charset=utf-8",
                                    "expected application/json")
            raw_length = self.headers.get("Content-Length") or "0"
            if not (raw_length.isascii() and raw_length.isdecimal()):
                return self.respond(400, "text/plain; charset=utf-8", "bad request")
            length = int(raw_length)
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self.respond(400, "text/plain; charset=utf-8", "bad request")
            if not isinstance(data, dict):
                return self.respond(400, "text/plain; charset=utf-8", "bad request")

            if p == "switch":
                return self.switch_guest(data.get("name"))

            if p == "lifecycle":
                return self.lifecycle(data.get("name"), data.get("action"))

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
                try:
                    d.type_text(str(data["word"])[:200])
                except ValueError:
                    return self.respond(400, "text/plain; charset=utf-8",
                                        "text holds a control character")
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
        except Exception:
            log.exception("do_POST %s", p)
            self.respond(500, "text/plain; charset=utf-8",
                        "internal error, see the service log")

    def switch_guest(self, name):
        """Points the server at a different guest's serial, or refuses.

        Only a row with a live serial, adb state "device", can be shown
        and driven. A guest still booting or already stopped has nothing
        for adb to talk to yet. rows also holds physical devices, so one
        of those can be switched to the same way, just never started,
        stopped or restarted through it, abgal has no guest by that name.
        """
        try:
            rows = guest_rows()
            known = {g["serial"] for g in rows if g["serial"]}
            rows = rows + safe_physical_devices(known)
        except Exception:
            log.exception("switch_guest")
            return self.respond(500, "text/plain; charset=utf-8",
                                "internal error, see the service log")
        found = next((g for g in rows if g["name"] == name), None)
        if found is None:
            return self.respond(404, "text/plain; charset=utf-8", "no such guest")
        if found["adb"] != "device":
            return self.respond(409, "text/plain; charset=utf-8",
                                "guest is not ready to view: " + str(found["adb"]))
        self.server.device = Device(found["serial"], self.server.step)
        self.server.selected = name
        self.respond(200, "application/json", '{"ok":true}')

    def lifecycle(self, name, action):
        """Starts, stops or restarts one guest.

        If the guest a viewer was watching just stopped or restarted, the
        selection is cleared too, so the page falls back to the
        placeholder instead of polling a dead serial. Only one lifecycle
        action per guest runs at a time, a second request for the same
        guest is refused instead of overlapping the first.
        """
        if action not in ("start", "stop", "restart"):
            return self.respond(400, "text/plain; charset=utf-8", "unknown action")
        if not isinstance(name, str) or not name:
            return self.respond(400, "text/plain; charset=utf-8", "bad request")
        with self.server.busy_lock:
            if name in self.server.busy:
                return self.respond(409, "text/plain; charset=utf-8",
                                    "an action for this guest is already running")
            self.server.busy.add(name)
        try:
            guest_action(name, action)
        except GuestActionError as e:
            # abgal's own reason, written for the person at the page.
            return self.respond(409, "text/plain; charset=utf-8", str(e))
        except Exception:
            log.exception("lifecycle %s %r", action, name)
            return self.respond(500, "text/plain; charset=utf-8",
                                "internal error, see the service log")
        finally:
            with self.server.busy_lock:
                self.server.busy.discard(name)
        if action in ("stop", "restart") and self.server.selected == name:
            self.server.device = None
            self.server.selected = None
        self.respond(200, "application/json", '{"ok":true}')

    def log_message(self, *_):
        pass


def make_server(address, port, step, token, allow_hosts=()):
    """Builds the ThreadingHTTPServer with every attribute the handler needs.

    Split out from main so a test can start a server on its own port and
    talk to it directly, without going through argument parsing or the
    guest preselection.
    """
    service = ThreadingHTTPServer((address, port), Handler)
    service.step = step
    service.device = None
    service.selected = None
    service.token = token
    service.allow_hosts = set(allow_hosts)
    service.busy = set()
    service.busy_lock = threading.Lock()
    return service


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    t = argparse.ArgumentParser(description="View and control for the emulator")
    t.add_argument("--guest", help="a guest to preselect, it must already be running")
    t.add_argument("--address", default="127.0.0.1")
    t.add_argument("--port", type=int, default=8099)
    t.add_argument("--step", type=int, default=2)
    t.add_argument("--allow-host", action="append", dest="allow_host", default=[],
                   metavar="NAME", help="an extra Host name to accept, repeatable")
    a = t.parse_args()

    token = secrets.token_urlsafe(32)
    service = make_server(a.address, a.port, a.step, token, a.allow_host)
    if a.guest:
        found = next((g for g in guest_rows() if g["name"] == a.guest), None)
        if found is None or found["adb"] != "device":
            print(f"'{a.guest}' is not visible on adb yet, starting with no guest selected.")
        else:
            service.device = Device(found["serial"], a.step)
            service.selected = a.guest

    print(f"View listens on http://{a.address}:{a.port}/")
    print("Requests need the token from the page itself, it is not printed here.")
    try:
        service.serve_forever()
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
