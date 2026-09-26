# View and control from a browser

`view/view-service.py` shows every guest `abgal` knows about in a browser,
lets a viewer switch which one is on screen, control it with the mouse and
keyboard, and start, stop or restart it without touching a terminal.

## Starting it

```bash
python3 view/view-service.py
```

| Flag | Default | What it does |
|---|---|---|
| `--guest <name>` | none | Preselects a guest that is already running. Without it, the page opens with nothing selected |
| `--address` | `127.0.0.1` | The interface to bind to. Loopback only by default, pass this to reach it from another machine |
| `--port` | `8099` | The port to listen on |
| `--step` | `2` | The default screen downscale, 1 is full size, higher is smaller and faster |

Open `http://127.0.0.1:8099/` (or whatever address and port you chose) in a
browser. The service prints its own URL on startup.

## The page

Three columns: a guest list on the left, the live screen in the middle, and
a control panel on the right. Both side columns can be resized by dragging
the thin bar next to them.

### Guest list

One row per guest, refreshed every few seconds. The row's own button shows
the serial once the guest is running, otherwise its name, next to a status
pill:

| Pill | Meaning |
|---|---|
| Green, `running` | `adb` reports state `device`, the row can be selected |
| Amber, `booting` | The guest has a process but `adb` has not reached it yet |
| Red, `unknown` | `adb` reports `unauthorized` |
| Red, `stopped` | No process, the guest is not running |

Only a running row can be clicked to select it. Clicking the small arrow at
the row's right end expands it, showing the guest's name, template, id,
`adb` state, memory and CPU, plus three buttons:

| Button | Enabled when | Does |
|---|---|---|
| Start | the guest has no process | `abgal start` |
| Stop | the guest has a process | `abgal stop` |
| Restart | the guest has a process | `abgal stop`, then `abgal start` |

A start can take up to ten minutes in the worst case, `abgal` waits up to
five minutes for the console and again up to five minutes for boot, one
after another. A stop or the stop half of a restart takes at most about a
minute. While one of these runs, the row shows the action's name instead of
the buttons. If the guest a viewer was watching just stopped or restarted,
the screen falls back to the placeholder rather than polling a serial that
no longer exists.

### The screen

Selecting a running guest starts fetching its screen. Clicking it without
moving the mouse taps that point, clicking and dragging swipes between the
two points. Both send the fraction of the image clicked, not a pixel
position, so it works at any downscale.

### The control panel

**SCREEN** holds auto refresh and three downscale buttons, FULL, HALF and
SMALL, plus NOW for a single fetch outside the refresh loop. The top bar
above the page shows the last frame's fetch time and the host's free
memory.

**KEYS** sends one of a fixed set of key events, BACK, HOME, APP_SWITCH,
ENTER, DEL, TAB, SEARCH, VOLUME_UP and VOLUME_DOWN. The set is fixed on
purpose so the page cannot send POWER or SLEEP mid test.

**SWIPE** sends a swipe from the middle of the screen toward one edge.

**TEXT** types a line into whatever has focus on the guest, up to 200
characters, on Enter.

A DEBUG panel, collapsed by default, can show every request the page made
and how it answered, useful when something on screen does not match what
was clicked.

## What it needs

`abgal` itself, called as a subprocess for the guest list and for start,
stop and restart, and `adb` for everything that touches a selected guest's
screen or input. The service keeps no guest state of its own beyond which
one is currently selected, `abgal status --json` is asked again on every
guest list refresh.
