# View and control from a browser

*[Auf Deutsch](view-service.de.md)*

`view/view-service.py` shows every guest `abgal` knows about in a browser,
lets a viewer switch which one is on screen, control it with the mouse and
keyboard, and start, stop or restart it without touching a terminal.

## Starting it

```bash
./abgal webui
```

`abgal webui` starts `view/view-service.py` and passes `--address`,
`--port`, `--guest` and `--allow-host` through. It listens on `0.0.0.0`,
every interface, so the page opens from another machine on the network, and
it prints a warning at every start that says so, see
[Security](#security). `./abgal webui --address 127.0.0.1` keeps it on this
machine.

The script can also be started directly, and then listens on loopback:

```bash
python3 view/view-service.py
```

| Flag | Default | What it does |
|---|---|---|
| `--guest <name>` | none | Preselects a guest that is already running. Without it, the page opens with nothing selected |
| `--address` | `127.0.0.1` | The interface to bind to. Loopback only by default, pass this to reach it from another machine |
| `--port` | `8099` | The port to listen on |
| `--step` | `2` | The default screen downscale, 1 is full size, higher is smaller and faster |
| `--allow-host <name>` | none | An extra host name the service accepts in the Host header, repeatable. Needed only when the page is reached through a DNS name other than localhost, a literal IP address is always accepted |

Open `http://127.0.0.1:8099/` (or whatever address and port you chose) in a
browser. The service prints its own URL on startup.

## The page

Three columns: a guest list on the left, the live screen in the middle, and
a control panel on the right. Both side columns can be resized by dragging
the thin bar next to them. The left column itself splits into the guest
list above and a DEBUG panel below, resized the same way along the bar
between them.

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

The list also shows every device `adb devices` sees that `abgal` does not
know about, a phone or tablet on USB or over `adb connect`. Such a row can
be selected and driven the same way as a guest once it reports `device`,
but carries no Start, Stop or Restart, real hardware is not `abgal`'s to
switch on or off.

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

**KEYS** has one button each for BACK, HOME, APP_SWITCH, ENTER, DEL, TAB,
SEARCH, VOLUME_UP and VOLUME_DOWN. The set is fixed on purpose so the page
cannot send POWER or SLEEP mid test.

**SWIPE** sends a swipe from the middle of the screen toward one edge.

**TEXT** types a line into whatever has focus on the guest, up to 200
characters, on Enter.

A DEBUG panel, collapsed by default, can show every request the page made
and how it answered, useful when something on screen does not match what
was clicked.

## Security

Every request except loading the page itself needs a token. The service
creates a fresh token at every start and puts it into the page, the page
sends that token in a header on each request.

A foreign web page cannot add that header without the browser first asking
the service for permission, and the service never grants it, so only the
page itself can produce a request that carries the token.

The Host header on every request must be localhost, a literal IP address,
or a name given with `--allow-host`. This stops DNS rebinding, since a
literal address cannot be rebound and a name has to be allowed on purpose.
An Origin header, when sent, must match the Host header.

POST bodies must be `application/json`. Text sent from TEXT reaches the
guest as one quoted word, control characters are refused. Unexpected
errors reach the page only as a generic message, the details stay in the
service's own log output. When `abgal` refuses a start, stop or restart,
for example for lack of memory, the page shows `abgal`'s own reason with
409. Only one start, stop or restart per guest runs at a time, a second
one gets 409.

Every 403 says what to do. A tab left open across a restart of the
service holds an old token and is told to reload the page. Opening the
page through a host name names the `--allow-host` call it needs. Host
names are compared without regard to case.

This does not protect against everything. Anyone who can open the page can
use it, the token is not a login and there is no user account. Traffic is
plain HTTP without encryption, so another machine on the path in the same
network can read it, including the token. Binding to another interface
with `--address` therefore gives everyone who can reach that address full
control of every guest. `abgal webui` does exactly that by default.

Use `abgal webui` on a network where everyone who can reach the machine may
control its guests. Anywhere else, pass `--address 127.0.0.1`, or start the
script directly, and reach the service through an SSH tunnel instead.

## What it needs

`abgal` itself, called as a subprocess for the guest list and for start,
stop and restart, and `adb` for everything that touches a selected guest's
screen or input. The service keeps no guest state of its own beyond which
one is currently selected, `abgal status --json` is asked again on every
guest list refresh.
