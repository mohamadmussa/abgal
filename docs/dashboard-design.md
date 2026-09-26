# Dashboard design

`view/view-service.py` serves a small three column page today: a guest list,
a live screen, and a control panel. This page describes the target layout for
that page, a full dashboard, agreed as the picture to build towards. It is not
the plan for one pull request. Functions land one at a time, tracked by their
own issues, and a control that has no backend yet ships as a visible but
disabled placeholder rather than waiting for every piece to be ready at once.

Tracked so far: guest lifecycle control, start, stop, restart, create,
delete ([#69](https://github.com/mohamadmussa/abgal/issues/69)), a terminal
session to the host or a guest
([#70](https://github.com/mohamadmussa/abgal/issues/70)), and the overall
shape as the page grows
([#71](https://github.com/mohamadmussa/abgal/issues/71)).

## Where the reference lives

A high fidelity click through prototype, with simulated data, shows every
screen and interaction. It lives outside the tracked tree as a design
reference, next to this file's author, and is not shipped as is: the real
page stays plain HTML, CSS and JS with no build step, served by the existing
`Handler`, matching how `view-service.py` already works.

## Layout

A CSS grid fills the viewport, four rows: header, main, terminal, status bar.
The main row has three columns, a guest list, the center, and a right panel
of tabs.

| Area | Content |
|---|---|
| Header | Title and host name, a breadcrumb, a command search field, install APK, host terminal, new guest, settings |
| Guest list | One row per guest: a status dot, the name, a shell shortcut, serial or id, memory, CPU. A progress bar while a guest stops or its disk is removed |
| Center, guest view | Name, status, lifecycle buttons (start, stop, restart), a shell shortcut, delete, a toolbar (layout, image quality, auto refresh, screenshot, record), the live screen |
| Center, empty state | No guest selected or none exist: an explanation and the create guest and host terminal actions |
| Right panel | Tabs: control (keys, swipe, type text, clipboard), details (a CPU chart, memory, guest facts), logs |
| Terminal | Collapsible, tabs for host and guest sessions, opened with a keyboard shortcut or from the status bar |
| Status bar | Terminal shortcut, last message, other shortcut hints |

Guests can also show as a grid of small live tiles at once, once more than
one guest is running.

## What each part needs from the backend

| Part | Backend |
|---|---|
| Guest list | `GET /guests`, already exists |
| Select a guest | `POST /switch`, already exists |
| Tap, key, swipe, text | already exist |
| Live screen | `GET /frame.png`, already exists |
| Start, stop, restart, delete | new routes, calling `abgal start`, `stop`, `delete` |
| Create | new route, calling `abgal create`. `--ram`, `--cores` and `--dry-run` do not exist yet in the CLI |
| Templates for the create dialog | new route, reading `devices.conf` |
| Terminal | a new session channel, to the host or to `adb shell` on one guest. The service is loopback only today, and a terminal needs the same care |
| Install an APK | new route, calling `adb install` |
| Clipboard | new route, through `adb shell cmd clipboard` or a helper |
| Screenshot, recording | new routes, saving to a folder on the host |
| Temperature | the existing watch, exposed as a value |

## Settings

A separate page, changes staged and only applied on save, with a warning if
the browser tab closes first. Screen refresh interval and default image
quality, capture folders on the host, and appearance: four ready made color
themes plus a custom one, changed at runtime through CSS variables.

## Look

Two typefaces, a sans serif for the interface and a monospace face for ids,
serials, commands and numbers. A dark, low contrast palette by default, with
status colors, green for a running guest, amber for a warning or a step in
progress, red for a problem, kept separate from the accent color used for
buttons and focus. Every theme is a small set of variables, so a custom theme
only changes those, not the page itself.
