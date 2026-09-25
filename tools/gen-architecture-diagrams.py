#!/usr/bin/env python3
"""Generate the animated and static SVG diagrams for docs/architecture.md.

Every diagram is built from a small flow description, a list of steps and
the edges between them, taken straight from the real numbers in `abgal`.
The renderer turns that description into markup once, then a light and a
dark `<style>` block are laid over the same markup, so the two palettes of
one diagram can never drift apart in layout, only in color.

    tools/gen-architecture-diagrams.py

Running it with no arguments regenerates all eighteen files, nine
diagrams in light and dark, deterministically: the same flow always
produces the same bytes. Which renderer draws which diagram, and the
fact-by-fact derivation behind each flow, is tracked in issue #39, not
repeated here.
"""

import os
import sys
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The whole point of compressing wait/poll animations: a flow whose real
# waits add up to 40 s and one whose waits add up to 4 minutes both loop in
# about the same, watchable amount of real time.
TARGET_LOOP_SECONDS = 8.0

# A floor on top of that same compression, not a second invented fact: when
# one step's real wait is tiny next to the others in its flow (FLOW_START's
# 2 s wait-settle beside two 300 s polls), the shared scale alone divides it
# down to an imperceptible flicker. The caption still shows the true,
# uncompressed seconds; only the animation's own speed is floored.
MIN_BAR_SECONDS = 0.4

# watch-states only: a poll step whose real loop has no cap at all (the
# main watch loop runs until stopped or aborted, unlike start's bounded
# --timeout) gets `cap="loop"` instead of True/False. Its bar plays its
# real interval MAX_BLIPS times, then holds, rather than looping forever
# the way a bounded poll's bar does: a fixed small number standing in for
# "keeps going", not a real count read from anywhere in abgal.
MAX_BLIPS = 4


def fail(message):
    print("ERROR: " + message, file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------- flows


# A step's kind decides how the renderer draws it: "instant" and "action"
# are a single event, "poll" and "wait" get the looping animation, exactly
# one "decision" per branch point, "terminal" ends the ladder.
FIELDS = ("id", "actor", "label", "kind", "seconds", "cap", "outcome")


def step(*values):
    """One box in a diagram, as a dict of the seven FIELDS columns.

    Values not given default to None, the same way a short call site like
    step("kill", "abgal", "...", "action") only ever names the columns it
    needs.
    """
    padded = values + (None,) * (len(FIELDS) - len(values))
    return dict(zip(FIELDS, padded))


def edge(from_id, to_id, label=None):
    """One arrow from step to step, in the order the renderer connects them."""
    return {"from_id": from_id, "to_id": to_id, "label": label}


def flow(steps, edges):
    return {"steps": steps, "edges": edges}


# ---------------------------------------------------------------- stop-ladder


# Mirrors stop_one() in abgal (abgal:1034-1067): adb kill, then an
# escalation through SIGTERM and SIGKILL, a fixed wait after each, ending
# in "stopped" or the hard failure abgal:1066 reports. Full derivation,
# fact by fact against the source, is tracked in issue #39.
FLOW_STOP = flow(
    steps=[
        step("kill", "abgal",
             "adb emu kill sent to the guest's serial", "action"),
        step("poll", "abgal",
             "poll every 1 s for the process to end (--grace, overridable)",
             "poll", 20, True),
        step("decision-grace", "abgal",
             "still running after the grace window?", "decision"),
        step("sigterm", "abgal", "SIGTERM sent to the pid", "action"),
        step("wait-term", "abgal",
             "wait for the process to end", "wait", 10, False),
        step("decision-term", "abgal",
             "still running after SIGTERM?", "decision"),
        step("sigkill", "abgal", "SIGKILL sent to the pid", "action"),
        step("wait-kill", "abgal",
             "wait for the process to end", "wait", 10, False),
        step("decision-kill", "abgal",
             "still running after SIGKILL?", "decision"),
        step("stopped", "abgal", "stopped", "terminal", None, None,
             "stopped"),
        step("running", "abgal",
             "still running. Nothing else this program can do.",
             "terminal", None, None, "still running"),
    ],
    edges=[
        edge("kill", "poll"),
        edge("poll", "decision-grace"),
        edge("decision-grace", "sigterm", "yes"),
        edge("decision-grace", "stopped", "no"),
        edge("sigterm", "wait-term"),
        edge("wait-term", "decision-term"),
        edge("decision-term", "sigkill", "yes"),
        edge("decision-term", "stopped", "no"),
        edge("sigkill", "wait-kill"),
        edge("wait-kill", "decision-kill"),
        edge("decision-kill", "running", "yes"),
        edge("decision-kill", "stopped", "no"),
    ],
)


# ------------------------------------------------------------ pieces-topology


# From docs/how-it-works.md, "The pieces" and "Where things live": abgal is
# the hub, bin/env.sh is the one deliberate non-relationship the page calls
# out. actor and outcome are repurposed here, the piece's own name and
# bin/env.sh's note, not who acts or a terminal's outcome, since there is
# only one actor in this flow.
FLOW_PIECES = flow(
    steps=[
        step("abgal", "abgal",
             "one file, standard library only. Every command.", "instant"),
        step("devices-conf", "devices.conf",
             "text, one line per template. What a guest is made from.",
             "instant"),
        step("versions-conf", "versions.conf",
             "text, one line per SDK part. What setup fetches.", "instant"),
        step("devices-xml", "devices.xml",
             "XML, the screens the templates refer to.", "instant"),
        step("avd", "avd/",
             "config.ini, abgal-template, abgal-id, per guest.", "instant"),
        step("logs", "logs/",
             "emulator.log and watch.log, per guest.", "instant"),
        step("sdk", "sdk/", "the Android SDK. Gitignored.", "instant"),
        step("android-home", "android-home/",
             "user files of the SDK tools. Gitignored.", "instant"),
        step("bin-env", "bin/env.sh",
             "bash, sourced for the SDK paths in your own shell.",
             "instant", None, None, "not read by abgal"),
    ],
    edges=[
        edge("abgal", "devices-conf", "reads"),
        edge("abgal", "versions-conf", "reads"),
        edge("abgal", "devices-xml", "links"),
        edge("abgal", "avd", "creates"),
        edge("abgal", "logs", "writes"),
        edge("abgal", "sdk", "fetches into"),
        edge("abgal", "android-home", "fetches into"),
    ],
)


# --------------------------------------------------------------- create-flow


# From docs/how-it-works.md, "## Create" (lines 69-98): the nine steps
# `abgal create <template> --as <guest>` takes, one straight column, no
# decisions. No step carries a `seconds` value, because create_one() has
# no documented per-step timing, and this project animates only a real,
# measured wait, never an invented one.
FLOW_CREATE = flow(
    steps=[
        step("refuse-name", "abgal",
             "refuses a name outside letters, digits, dot, underscore, "
             "dash", "action"),
        step("check-screen", "abgal",
             "checks the screen is listed by avdmanager list device",
             "action"),
        step("fetch-image", "abgal",
             "fetches the system image, unless sdk/system-images/ has it",
             "action"),
        step("refuse-running", "abgal",
             "refuses a running guest, since a start rewrites config.ini",
             "action"),
        step("recreate-or-keep", "abgal",
             "with --recreate, deletes the guest first. Otherwise keeps "
             "its disk", "action"),
        step("create-avd", "abgal",
             "creates avd/, calls avdmanager create avd", "action"),
        step("write-template", "abgal",
             "writes abgal-template next to config.ini", "action"),
        step("pin-values", "abgal",
             "pins five values in config.ini, a sixth for the store "
             "template", "action"),
        step("verify-values", "abgal",
             "reads config.ini back, compares thirteen values it asked "
             "for", "action"),
    ],
    edges=[
        edge("refuse-name", "check-screen"),
        edge("check-screen", "fetch-image"),
        edge("fetch-image", "refuse-running"),
        edge("refuse-running", "recreate-or-keep"),
        edge("recreate-or-keep", "create-avd"),
        edge("create-avd", "write-template"),
        edge("write-template", "pin-values"),
        edge("pin-values", "verify-values"),
    ],
)


# -------------------------------------------------------------- start-states


# Mirrors wait_for_console()/wait_for_boot()/start_one() (abgal:742-952)
# and the actor vocabulary of the sequenceDiagram already in
# docs/how-it-works.md. The three ways this can end badly (console never
# answers, watch dies at once, boot never completes) stay three distinct
# terminals, never merged into one, because each means something
# different for the guest. Fact-by-fact derivation (poll intervals,
# timeouts, thresholds) is tracked in issue #39, not repeated here.
FLOW_START = flow(
    steps=[
        step("preflight", "abgal",
             "refuses a running guest, or memory under ramSize + 900 + "
             "1024 MB", "instant"),
        step("launch", "abgal",
             "starts the emulator, detached, logs to "
             "logs/<guest>/emulator.log", "action"),
        step("poll-console", "abgal",
             "asks adb every 2 s who this is, up to --timeout, unless "
             "gone by 15 s", "poll", 300, True),
        step("decision-console", "abgal", "console answered?", "decision"),
        step("fail-console", "abgal",
             "did not come up. Last log lines are printed.",
             "terminal", None, None, "fail"),
        step("start-watch", "abgal",
             "starts abgal watch as a subprocess, unless --no-watch",
             "action"),
        step("wait-settle", "abgal",
             "waits for the watch to settle, then checks it is alive",
             "wait", 2, False),
        step("decision-watch", "abgal", "watch still alive?", "decision"),
        step("fail-watch", "abgal",
             "watch died at once. Guest keeps running without it.",
             "terminal", None, None, "fail"),
        step("poll-boot", "abgal",
             "asks adb every 3 s for boot_completed, up to --timeout",
             "poll", 300, True),
        step("decision-boot", "abgal", "booted in time?", "decision"),
        step("fail-boot", "abgal",
             "did not report a completed boot in --timeout s.",
             "terminal", None, None, "fail"),
        step("ready", "abgal", "ready", "terminal", None, None, "ready"),
    ],
    edges=[
        edge("preflight", "launch"),
        edge("launch", "poll-console"),
        edge("poll-console", "decision-console"),
        edge("decision-console", "start-watch", "yes"),
        edge("decision-console", "fail-console", "no"),
        edge("start-watch", "wait-settle"),
        edge("wait-settle", "decision-watch"),
        edge("decision-watch", "poll-boot", "yes"),
        edge("decision-watch", "fail-watch", "no"),
        edge("poll-boot", "decision-boot"),
        edge("decision-boot", "ready", "yes"),
        edge("decision-boot", "fail-boot", "no"),
    ],
)


# Which other actor each FLOW_START step talks to, if any, re-read against
# abgal:773-952. Swimlane/circuit only: draw_states and FLOW_STOP/CREATE/
# PIECES never look at this, so it stays out of FIELDS rather than
# rippling a column those flows have no use for into all of them.
START_CHANNELS = {
    "preflight": "kernel",      # running_pid(), available_mb(): both /proc
    "launch": "emulator",       # subprocess.Popen of the emulator binary
    "poll-console": "adb",      # serial_of(), which asks adb who this is
    "start-watch": "watch",     # subprocess.Popen of "abgal watch"
    "wait-settle": "watch",     # watch.poll(), is that subprocess alive
    "poll-boot": "adb",         # adb shell getprop sys.boot_completed
    # decision-*, fail-*, ready: abgal's own branching, no message sent.
}


# -------------------------------------------------------------- watch-states


# Mirrors cmd_watch() (abgal:1254-1330): a temperature reading that must
# succeed once, a warmup poll, then an unbounded main loop, ending in one
# of several terminals or an escalation via the same stop_one() cascade
# stop-ladder already draws, shown here as a labelled pointer rather than
# redrawn. The real loop's back edge (unreadable, retry) is drawn as a
# plain box stating the eventual consequence instead of a literal arrow
# back up the column, the same proven pattern FLOW_START's own history
# established. Fact-by-fact derivation (thresholds, intervals, exit
# codes) is tracked in issue #39.
FLOW_WATCH = flow(
    steps=[
        step("temp-check", "abgal",
             "reads the temperature once, from x86_pkg_temp or sensors",
             "instant"),
        step("decision-temp", "abgal", "temperature measurable?",
             "decision"),
        step("abort-no-temp", "abgal",
             "aborted. No temperature measurable at all.",
             "terminal", None, None, "fail"),
        step("warmup-poll", "abgal",
             "polls every 5 s for a guest to appear, up to --warmup",
             "poll", 120, True),
        step("decision-warmup", "abgal", "guest appeared within warmup?",
             "decision"),
        step("warmup-timeout", "abgal",
             "no emulator appeared. Watch off.",
             "terminal", None, None, "ok"),
        step("main-poll", "abgal",
             "polls every 2 s (--interval), no limit, until stopped or "
             "aborted", "poll", 2, "loop"),
        step("decision-guests", "abgal", "guests still present?",
             "decision"),
        step("watch-off", "abgal",
             "no guests left. Watch off, highest value logged.",
             "terminal", None, None, "ok"),
        step("decision-readable", "abgal", "temperature readable?",
             "decision"),
        step("unreadable", "abgal",
             "unreadable. Retries, aborts at 4 in a row.", "instant"),
        step("decision-stop", "abgal", "at or above stop (96 C default)?",
             "decision"),
        step("retry", "abgal",
             "below stop. Waits --interval, polls again.", "instant"),
        step("ref-stop-ladder", "abgal",
             "stop cascade for every guest. See stop-ladder.",
             "terminal", None, None, "ok"),
    ],
    edges=[
        edge("temp-check", "decision-temp"),
        edge("decision-temp", "warmup-poll", "yes"),
        edge("decision-temp", "abort-no-temp", "no"),
        edge("warmup-poll", "decision-warmup"),
        edge("decision-warmup", "main-poll", "yes"),
        edge("decision-warmup", "warmup-timeout", "no"),
        edge("main-poll", "decision-guests"),
        edge("decision-guests", "decision-readable", "yes"),
        edge("decision-guests", "watch-off", "no"),
        edge("decision-readable", "decision-stop", "yes"),
        edge("decision-readable", "unreadable", "no"),
        edge("decision-stop", "ref-stop-ladder", "yes"),
        edge("decision-stop", "retry", "no"),
    ],
)


# --------------------------------------------------------------- ports-scale


# --port only ever appends "-port N" to the emulator command when given
# (abgal:843); the automatic case is entirely the emulator's own doing,
# and an explicit --port must be even, 5554 to 5584, the same range
# port_of() parses a guest's adb serial back out of (abgal:351-354). Which
# of the 16 is free at any moment is runtime state, not a source value,
# so unlike every other flow here the guest claims below the slot row are
# illustrative, not measured, stated as such on the diagram itself. Full
# derivation is tracked in issue #39.
PORT_LO, PORT_HI, PORT_STEP = 5554, 5584, 2

# The three ports this illustrative sequence ends with claimed, and which
# guest event claims each. The other 13 (5554 through 5578) are the
# "already busy" starting condition; none of the 16 stays free.
PORT_CLAIMS = {5580: "guest-auto-1", 5582: "guest-auto-2", 5584: "guest-explicit"}


def _port_slot_steps():
    """The sixteen port slots, id and label both the real port number."""
    found = []
    for port in range(PORT_LO, PORT_HI + 1, PORT_STEP):
        found.append(step("slot-%d" % port, None, str(port), "instant"))
    return found


FLOW_PORTS = flow(
    steps=_port_slot_steps() + [
        step("guest-auto-1", None,
             "guest (example): auto picks the first free slot",
             "instant"),
        step("guest-explicit", None,
             "guest (example): --port 5584 claims it directly",
             "instant"),
        step("guest-auto-2", None,
             "guest (example): auto picks the first free slot",
             "instant"),
        step("guest-auto-3", None,
             "guest (example): automatic port, nothing free left",
             "instant"),
        step("dead-end", None,
             "no free port. No code here; a generic failure.",
             "terminal", None, None, "fail"),
    ],
    edges=[
        edge("guest-auto-1", "slot-5580"),
        edge("guest-explicit", "slot-5584"),
        edge("guest-auto-2", "slot-5582"),
        edge("guest-auto-3", "dead-end"),
    ],
)


# ----------------------------------------------------------- readme-lifecycle


# The eight transitions README.md#lifecycle names, minus the memory-refusal
# self-loop (no equivalent shape in this renderer, drawn as a note beside
# "stopped" instead by draw_lifecycle_note) and with "abgal stop" and the
# temperature watch folded into one edge (both are real, separate causes,
# but both name the same source and the same target, and this renderer
# draws one curve per src/dst pair, not one per label). "booting" is the
# only real wait in the whole lifecycle, so it is the only step that gets
# a seconds value, the same 300 s FLOW_START's own poll-boot already uses,
# never a second, invented timeout for the same real --timeout.
FLOW_LIFECYCLE = flow(
    steps=[
        step("template", None, "template", "instant"),
        step("stopped", None, "stopped", "instant"),
        step("booting", None, "booting", "wait", 300, True),
        step("running", None, "running", "instant"),
        step("deleted", None, "deleted", "terminal", None, None, "ok"),
    ],
    edges=[
        edge("template", "stopped", "abgal create"),
        edge("stopped", "booting", "abgal start"),
        edge("booting", "running", "boot completed"),
        edge("booting", "stopped", "did not come up"),
        edge("running", "stopped", "abgal stop, or temperature watch at 96 C"),
        edge("stopped", "deleted", "abgal delete"),
    ],
)


# -------------------------------------------------------------------- layout


MARGIN = 30.0
BOX_W = 260.0
BOX_H = 68.0
ROW_GAP = 28.0
PITCH = BOX_H + ROW_GAP
SIDE_GAP = 60.0
SIDE_W = 200.0
SIDE_H = 68.0
BAR_W = 220.0
BAR_H = 6.0
BAR_PAD = (BOX_W - BAR_W) / 2.0


def _layout(flow_):
    """Where every step sits, and the canvas size that holds them all.

    A step reached by more than one edge (stop-ladder's shared "stopped"
    box) is drawn once, off to the side, at the average height of the
    steps that point to it, which for a single source reduces to "level
    with that one step". So is a step reached by exactly one edge labelled
    "no": a decision only ever gives one of its two children the main
    column's next slot, and a failure exit is never that one, whatever
    order the steps happen to be listed in. Everything else runs straight
    down the main column, top to bottom, in flow_["steps"] order.
    """
    incoming = {}
    for e in flow_["edges"]:
        incoming.setdefault(e["to_id"], []).append(e)

    def wants_side(step_id):
        edges_in = incoming.get(step_id, [])
        if len(edges_in) > 1:
            return True
        return len(edges_in) == 1 and edges_in[0]["label"] == "no"

    side_ids = [s["id"] for s in flow_["steps"] if wants_side(s["id"])]
    main_steps = [s for s in flow_["steps"] if s["id"] not in side_ids]
    side_steps = [s for s in flow_["steps"] if s["id"] in side_ids]

    positions = {}
    for i, s in enumerate(main_steps):
        positions[s["id"]] = {"x": MARGIN, "y": MARGIN + i * PITCH,
                               "w": BOX_W, "h": BOX_H, "step": s}

    x_side = MARGIN + BOX_W + SIDE_GAP
    for s in side_steps:
        sources_y = [positions[e["from_id"]]["y"] + positions[e["from_id"]]["h"] / 2
                     for e in flow_["edges"]
                     if e["to_id"] == s["id"] and e["from_id"] in positions]
        cy = sum(sources_y) / len(sources_y) if sources_y else MARGIN
        positions[s["id"]] = {"x": x_side, "y": cy - SIDE_H / 2,
                               "w": SIDE_W, "h": SIDE_H, "step": s}

    height = MARGIN + max(0, len(main_steps) - 1) * PITCH + BOX_H + MARGIN
    width = x_side + SIDE_W + MARGIN
    return {"positions": positions, "width": width, "height": height,
            "main_order": [s["id"] for s in main_steps]}


LINEAR_COLS = 3
LINEAR_COL_GAP = 60.0
LINEAR_ROW_GAP = 70.0
LINEAR_BADGE_R = 11.0


def _layout_linear(flow_):
    """A boustrophedon grid: reads left to right, then wraps like a
    checklist, instead of one tall column.

    create-flow has no decision and no side branch, nine plain actions in
    a fixed order. Read as _layout's usual single column, nine identical
    boxes give no visual cue that this is a checklist rather than a state
    machine. Wrapping the column into a snake keeps every consecutive
    step adjacent, row-mates side by side, a row wrap stacked at the same
    x, so every edge stays a straight line, only its direction
    alternates.
    """
    steps = flow_["steps"]
    positions = {}
    for i, s in enumerate(steps):
        row, col = divmod(i, LINEAR_COLS)
        if row % 2 == 1:
            col = LINEAR_COLS - 1 - col
        x = MARGIN + col * (BOX_W + LINEAR_COL_GAP)
        y = MARGIN + row * (BOX_H + LINEAR_ROW_GAP)
        positions[s["id"]] = {"x": x, "y": y, "w": BOX_W, "h": BOX_H,
                              "step": s, "number": i + 1}
    rows = -(-len(steps) // LINEAR_COLS)
    width = MARGIN + LINEAR_COLS * BOX_W + (LINEAR_COLS - 1) * LINEAR_COL_GAP + MARGIN
    height = MARGIN + rows * BOX_H + (rows - 1) * LINEAR_ROW_GAP + MARGIN
    return {"positions": positions, "width": width, "height": height}


STAIR_STEPS_PER_RUNG = 3
STAIR_DX = 90.0


def _layout_stairs(flow_):
    """A staircase: three steps per escalation tier, each tier shifted
    right of the last, so kill/SIGTERM/SIGKILL reads as a real descent
    instead of the one flat column every other state ladder already is.

    Built for stop-ladder specifically, not a general-purpose engine:
    the count of three steps per rung and the assumption that exactly
    one step (the "still running" terminal) follows the last rung are
    both stop-ladder's own shape, not read from the flow. The shared
    "stopped" exit is laid out exactly like _layout already places a
    side box, off to the side at the average height of what points to
    it, just computed here by hand since the staircase has no single
    main column _layout's own math can reuse directly.
    """
    incoming = {}
    for e in flow_["edges"]:
        incoming.setdefault(e["to_id"], []).append(e)

    side_ids = [s["id"] for s in flow_["steps"]
                if len(incoming.get(s["id"], [])) > 1]
    main_steps = [s for s in flow_["steps"] if s["id"] not in side_ids]
    side_steps = [s for s in flow_["steps"] if s["id"] in side_ids]

    # The escalation tiers proper, minus the trailing "still running"
    # terminal, rounded up to whole rungs of three.
    rungs = -(-(len(main_steps) - 1) // STAIR_STEPS_PER_RUNG)

    positions = {}
    for i, s in enumerate(main_steps):
        rung = min(i // STAIR_STEPS_PER_RUNG, rungs - 1)
        x = MARGIN + rung * STAIR_DX
        y = MARGIN + i * PITCH
        positions[s["id"]] = {"x": x, "y": y, "w": BOX_W, "h": BOX_H,
                              "step": s}

    x_side = MARGIN + rungs * STAIR_DX + BOX_W + SIDE_GAP
    for s in side_steps:
        sources_y = [positions[e["from_id"]]["y"] + positions[e["from_id"]]["h"] / 2
                     for e in flow_["edges"]
                     if e["to_id"] == s["id"] and e["from_id"] in positions]
        cy = sum(sources_y) / len(sources_y) if sources_y else MARGIN
        positions[s["id"]] = {"x": x_side, "y": cy - SIDE_H / 2,
                              "w": SIDE_W, "h": SIDE_H, "step": s}

    height = MARGIN + max(0, len(main_steps) - 1) * PITCH + BOX_H + MARGIN
    width = x_side + SIDE_W + MARGIN
    return {"positions": positions, "width": width, "height": height,
            "main_order": [s["id"] for s in main_steps]}


LIFECYCLE_MAIN_ORDER = ("template", "stopped", "booting", "running")
LIFECYCLE_LOOP_1 = 55.0
LIFECYCLE_LOOP_2 = 100.0
LIFECYCLE_NOTE_TEXT = "abgal start, not enough memory: stays stopped"


def _layout_lifecycle(flow_):
    """template, stopped, booting, running in one column in that order,
    "deleted" a side box off "stopped" the same way stop-ladder's shared
    exit sits beside its own column, and the two edges that return to an
    earlier state (booting failing, running stopping) as loops bulging
    out to the left, deeper for the one that skips further back.

    Built for FLOW_LIFECYCLE specifically, not a general engine: _layout's
    generic side box only ever receives, but "stopped" here also sends
    two edges of its own, template's create and its own delete, which a
    plain side box has no sane way to draw, it would have to reach back
    across the whole column.
    """
    by_id = dict((s["id"], s) for s in flow_["steps"])
    main_order = list(LIFECYCLE_MAIN_ORDER)

    back_labels = [e["label"] for e in flow_["edges"] if e["label"]
                   and e["from_id"] in main_order and e["to_id"] in main_order
                   and main_order.index(e["to_id"]) < main_order.index(e["from_id"])]
    back_labels.append(LIFECYCLE_NOTE_TEXT)
    label_room = max([len(t) * 6.0 for t in back_labels] + [0.0]) + 30.0

    x_main = MARGIN + label_room + LIFECYCLE_LOOP_2
    positions = {}
    for i, sid in enumerate(main_order):
        positions[sid] = {"x": x_main, "y": MARGIN + i * PITCH,
                          "w": BOX_W, "h": BOX_H, "step": by_id[sid]}

    stopped = positions["stopped"]
    x_side = x_main + BOX_W + SIDE_GAP
    positions["deleted"] = {
        "x": x_side,
        "y": stopped["y"] + stopped["h"] / 2.0 - SIDE_H / 2.0,
        "w": SIDE_W, "h": SIDE_H, "step": by_id["deleted"]}

    height = MARGIN + (len(main_order) - 1) * PITCH + BOX_H + MARGIN
    width = x_side + SIDE_W + MARGIN
    return {"positions": positions, "width": width, "height": height,
            "main_order": main_order}


TOPO_NODE_W = 220.0
TOPO_COL_GAP = 30.0
TOPO_ROW_GAP = 70.0
TOPO_DETACH_GAP = 50.0
# An edge with one of these verbs is drawn above the hub, "what it takes
# in"; anything else is drawn below, "what it makes". Not stop-ladder's
# concern, so it lives next to the layout it actually shapes.
TOPO_INPUT_VERBS = ("reads", "links")


def _hub_id(flow_):
    """The step id the most edges start from, first in step order on a tie."""
    out_counts = {}
    for e in flow_["edges"]:
        out_counts[e["from_id"]] = out_counts.get(e["from_id"], 0) + 1
    best = max(out_counts.values()) if out_counts else 0
    for s in flow_["steps"]:
        if best and out_counts.get(s["id"], 0) == best:
            return s["id"]
    return flow_["steps"][0]["id"]


def _topo_row_width(n):
    return n * TOPO_NODE_W + max(0, n - 1) * TOPO_COL_GAP


def _layout_topology(flow_):
    """One hub, its spokes split into an input row above and an output
    row below by their edge's verb, and anything with no edge to the hub
    set off to the side instead of left dangling at (0, 0).

    Nothing here is ladder-specific: it only looks at who points at whom
    and what the edge is called, so any hub-shaped flow can reuse it.
    """
    hub_id = _hub_id(flow_)
    verbs = dict((e["to_id"], e["label"]) for e in flow_["edges"]
                 if e["from_id"] == hub_id)
    connected = [s["id"] for s in flow_["steps"] if s["id"] in verbs]
    inputs = [sid for sid in connected if verbs[sid] in TOPO_INPUT_VERBS]
    outputs = [sid for sid in connected if sid not in inputs]
    detached = [s["id"] for s in flow_["steps"]
                if s["id"] != hub_id and s["id"] not in verbs]

    by_id = dict((s["id"], s) for s in flow_["steps"])
    main_w = max(_topo_row_width(len(inputs)), _topo_row_width(len(outputs)),
                 TOPO_NODE_W)
    positions = {}

    def place_row(ids, y):
        x = MARGIN + (main_w - _topo_row_width(len(ids))) / 2.0
        for sid in ids:
            positions[sid] = {"x": x, "y": y, "w": TOPO_NODE_W, "h": BOX_H,
                              "step": by_id[sid]}
            x += TOPO_NODE_W + TOPO_COL_GAP

    y_inputs = MARGIN
    y_hub = y_inputs + BOX_H + TOPO_ROW_GAP
    y_outputs = y_hub + BOX_H + TOPO_ROW_GAP
    place_row(inputs, y_inputs)
    place_row([hub_id], y_hub)
    place_row(outputs, y_outputs)

    x_detached = MARGIN + main_w + TOPO_DETACH_GAP
    for sid in detached:
        positions[sid] = {"x": x_detached, "y": y_hub, "w": TOPO_NODE_W,
                          "h": BOX_H, "step": by_id[sid]}

    width = MARGIN + main_w + MARGIN
    if detached:
        width = x_detached + TOPO_NODE_W + MARGIN
    height = y_outputs + BOX_H + MARGIN
    return {"positions": positions, "width": width, "height": height,
            "hub_id": hub_id, "detached": detached}


# abgal first, then the order how-it-works.md's own sequenceDiagram
# (lines 118-122) already declares its participants in: kernel, emulator,
# adb, temperature watch.
LANE_ORDER = ("abgal", "kernel", "emulator", "adb", "watch")
LANE_LABELS = {
    "abgal": "abgal start", "kernel": "kernel", "emulator": "emulator",
    "adb": "adb", "watch": "temperature watch",
}

SWIM_HEADER_H = BOX_H
SWIM_HEADER_GAP = 30.0
SWIM_OTHER_W = 130.0
SWIM_LANE_GAP = 50.0


def _layout_swimlane(flow_):
    """Lane x-positions, and each step's row y down one shared time axis.

    Five fixed columns, not _layout's single main column with a side box
    for a shared target: that shape does not fit a swimlane, so this is
    its own small layout, the same way pieces-topology got
    _layout_topology instead of bending _layout to fit a hub.
    """
    lane_x, lane_w = {}, {}
    x = MARGIN
    for lane in LANE_ORDER:
        w = BOX_W if lane == "abgal" else SWIM_OTHER_W
        lane_x[lane], lane_w[lane] = x, w
        x += w + SWIM_LANE_GAP
    width = x - SWIM_LANE_GAP + MARGIN

    header_y = MARGIN
    first_row_y = header_y + SWIM_HEADER_H + SWIM_HEADER_GAP
    rows = {}
    for i, s in enumerate(flow_["steps"]):
        rows[s["id"]] = {"y": first_row_y + i * PITCH, "index": i}

    height = (first_row_y + max(0, len(flow_["steps"]) - 1) * PITCH
             + BOX_H + MARGIN)
    return {"lane_x": lane_x, "lane_w": lane_w, "rows": rows,
            "header_y": header_y, "width": width, "height": height}


# start-sequence: a literal sequence diagram, one block per real exchange
# in main_order. A one-shot step (preflight, launch, start-watch) is a
# plain request/response pair. A poll with a real decision after it
# (poll-console, poll-boot) gets a shaded rect around its note, its
# request, and a nested alt frame for the two branches. wait-settle sends
# no message at all (abgal_start:wait_for_console sleeps, then reads its
# own child process handle), so its rect holds only a note and a wait bar,
# and the alt frame for its decision stays unshaded and narrow, both
# branches self-referential. Swimlane's own lane_x/lane_w carries over
# unchanged; only the row rhythm is new.
SEQ_NOTE_GAP = 18.0
SEQ_ROW_GAP = 22.0
SEQ_RECT_PAD = 14.0
SEQ_BLOCK_GAP = 26.0
SEQ_BAR_ROW_H = 24.0
SEQ_LOOP_W = 44.0
# An alt frame's own inner rhythm: [header] text, a gap, up to two
# wrapped lines of content, a gap before the next header. SEQ_CONTENT_H
# is sized for the self-loop branch's real fail-* text (the longest
# content either branch ever holds), so the divider never lands inside a
# wrapped second line the way a tighter guess once did.
SEQ_ALT_TOP_PAD = 16.0
SEQ_ALT_BRANCH_GAP = 14.0
SEQ_ALT_CONTENT_H = 28.0
SEQ_ALT_BOTTOM_PAD = 16.0


def _alt_geometry(top):
    header1_y = top + SEQ_ALT_TOP_PAD
    branch1_y = header1_y + SEQ_ALT_BRANCH_GAP
    divider_y = branch1_y + SEQ_ALT_CONTENT_H
    header2_y = divider_y + SEQ_ALT_TOP_PAD
    branch2_y = header2_y + SEQ_ALT_BRANCH_GAP
    bottom = branch2_y + SEQ_ALT_BOTTOM_PAD
    return {"alt_top": top, "header1_y": header1_y, "branch1_y": branch1_y,
            "divider_y": divider_y, "header2_y": header2_y,
            "branch2_y": branch2_y, "alt_bottom": bottom}


def _layout_sequence(flow_):
    """One block per real exchange, walking main_order. A poll or wait
    step immediately followed by a decision consumes that decision too,
    folding its alt frame into the same block, since a decision step
    never gets a row of its own, only ever the branch that follows the
    exchange it judges. Every y an alt frame needs is computed once,
    here, by _alt_geometry, so draw_sequence never re-derives a divider
    or header position from a different formula than the one that
    reserved the space for it.
    """
    swim = _layout_swimlane(flow_)
    main_order = _layout(flow_)["main_order"]
    by_id = dict((s["id"], s) for s in flow_["steps"])

    blocks = []
    y = swim["header_y"] + SWIM_HEADER_H + 40.0
    i = 0
    while i < len(main_order):
        sid = main_order[i]
        s = by_id[sid]
        nxt_id = main_order[i + 1] if i + 1 < len(main_order) else None
        nxt = by_id[nxt_id] if nxt_id else None
        alt_id = nxt_id if nxt is not None and nxt["kind"] == "decision" else None

        if s["kind"] == "terminal":
            block = {"type": "ready", "id": sid, "y": y}
            y += BOX_H + 20.0
        elif s["kind"] == "poll" and s["seconds"]:
            note_y = y
            req_y = note_y + SEQ_NOTE_GAP + 14.0
            alt = _alt_geometry(req_y + SEQ_ROW_GAP)
            block = dict(alt, type="poll", id=sid, alt_id=alt_id,
                        rect_top=note_y - SEQ_RECT_PAD, note_y=note_y,
                        req_y=req_y,
                        rect_bottom=alt["alt_bottom"] + SEQ_RECT_PAD)
            y = block["rect_bottom"] + SEQ_BLOCK_GAP
        elif s["kind"] == "wait" and s["seconds"]:
            note_y = y
            bar_y = note_y + SEQ_NOTE_GAP + 10.0
            rect_bottom = bar_y + SEQ_BAR_ROW_H + SEQ_RECT_PAD
            alt = _alt_geometry(rect_bottom + 16.0)
            block = dict(alt, type="wait", id=sid, alt_id=alt_id,
                        rect_top=note_y - SEQ_RECT_PAD, note_y=note_y,
                        bar_y=bar_y, rect_bottom=rect_bottom)
            y = alt["alt_bottom"] + SEQ_BLOCK_GAP
        else:
            req_y = y
            resp_y = req_y + 22.0
            block = {"type": "pair", "id": sid, "req_y": req_y,
                     "resp_y": resp_y}
            y = resp_y + SEQ_BLOCK_GAP

        blocks.append(block)
        i += 2 if alt_id else 1

    layout = dict(swim, blocks=blocks, height=y + MARGIN)
    layout["width"] += 20.0
    return layout


# ports-scale only: a row of fixed slots above a row of illustrative
# claims, not a ladder or a hub. Reusing _layout/_layout_topology's box
# rhythm (BOX_H, the .box/.box-terminal styling) for every box so it
# still reads as the same document, but the two-row shape is its own,
# the same way swimlane's fixed lanes and circuit's fixed satellites
# each needed a layout _layout/_layout_topology do not offer.
PORT_SLOT_W = 70.0
PORT_SLOT_GAP = 8.0
PORT_GUEST_W = SIDE_W
PORT_GUEST_GAP = 30.0
PORT_ROW_GAP = 90.0
PORT_CAPTION_GAP = 46.0


def _layout_ports(flow_):
    """One row of 16 real port slots, a second row of illustrative guest
    events below it. A guest box sits level with none of its target in
    particular (the row is centred as a whole under the slots); what
    keeps its connecting line safe is not alignment, it is that the line
    only ever travels the gap between the two rows (see draw_ports),
    which it cannot do without clipping a box regardless of the offset.
    """
    by_id = dict((s["id"], s) for s in flow_["steps"])
    ports = list(range(PORT_LO, PORT_HI + 1, PORT_STEP))
    positions = {}

    slot_y = MARGIN + PORT_CAPTION_GAP
    for i, port in enumerate(ports):
        sid = "slot-%d" % port
        positions[sid] = {"x": MARGIN + i * (PORT_SLOT_W + PORT_SLOT_GAP),
                          "y": slot_y, "w": PORT_SLOT_W, "h": BOX_H,
                          "step": by_id[sid]}
    slot_row_w = len(ports) * PORT_SLOT_W + (len(ports) - 1) * PORT_SLOT_GAP

    guest_ids = ("guest-auto-1", "guest-explicit", "guest-auto-2",
                "guest-auto-3", "dead-end")
    guest_row_w = (len(guest_ids) * PORT_GUEST_W
                  + (len(guest_ids) - 1) * PORT_GUEST_GAP)
    x = MARGIN + (slot_row_w - guest_row_w) / 2.0
    guest_y = slot_y + BOX_H + PORT_ROW_GAP
    for gid in guest_ids:
        positions[gid] = {"x": x, "y": guest_y, "w": PORT_GUEST_W,
                          "h": BOX_H, "step": by_id[gid]}
        x += PORT_GUEST_W + PORT_GUEST_GAP

    width = MARGIN + slot_row_w + MARGIN
    height = guest_y + BOX_H + MARGIN
    return {"positions": positions, "width": width, "height": height,
            "slot_y": slot_y}


# ------------------------------------------------------------------ renderer


DEFS_MARKUP = (
    '<defs>\n'
    '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
    'markerWidth="7" markerHeight="7" orient="auto-start-reverse">\n'
    '<path class="arrowhead" d="M 0 0 L 10 5 L 0 10 z"/>\n'
    '</marker>\n'
    '</defs>'
)


def fnum(value):
    """Any coordinate or duration, formatted to exactly two decimal places.

    check-private.py's own "long digit run" pattern scans generated SVGs
    the same as everything else, so this is what keeps the output free of
    the long, unrounded digit runs that pattern looks for.
    """
    return "%.2f" % value


def _esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _wrap(text, box_w):
    lines = textwrap.wrap(text, width=max(10, int(box_w / 7.5)))
    return lines or [text]


# A terminal's outcome is never shown as text (the box's own label already
# says "stopped" or "ready" or whatever it is), it only picks the CSS
# class: one of these values draws green, anything else draws red. Kept
# as one shared list instead of one flow's word, "stopped", hardcoded, so
# a second flow's good outcome does not draw as a failure by accident.
# "ok" is watch-states' generic clean exit (nothing left to watch, or
# warmup ran out before a guest appeared), neither a ladder's specific
# "stopped" nor a start's specific "ready".
GOOD_OUTCOMES = ("stopped", "ready", "ok")


def _box_markup(pos):
    s = pos["step"]
    x, y, w, h = pos["x"], pos["y"], pos["w"], pos["h"]
    kind = s["kind"]
    rx = h / 2.0 if kind == "terminal" else 8.0
    box_class = "box box-%s" % kind
    if kind == "terminal":
        box_class += " box-%s" % ("ok" if s["outcome"] in GOOD_OUTCOMES else "bad")
    cx = x + w / 2.0

    parts = ['<g id="step-%s">' % s["id"]]
    parts.append('<rect class="%s" x="%s" y="%s" width="%s" height="%s" '
                 'rx="%s" ry="%s"/>'
                 % (box_class, fnum(x), fnum(y), fnum(w), fnum(h),
                    fnum(rx), fnum(rx)))
    if s["actor"]:
        parts.append('<text class="label-actor" x="%s" y="%s" '
                     'text-anchor="middle">%s</text>'
                     % (fnum(cx), fnum(y + 14), _esc(s["actor"])))
    for i, line in enumerate(_wrap(s["label"], w)[:2]):
        parts.append('<text class="label-main" x="%s" y="%s" '
                     'text-anchor="middle">%s</text>'
                     % (fnum(cx), fnum(y + 28 + i * 12), _esc(line)))
    caption = _duration_caption(s)
    if caption:
        parts.append('<text class="label-duration" x="%s" y="%s" '
                     'text-anchor="middle">%s</text>'
                     % (fnum(cx), fnum(y + 54), _esc(caption)))
    if kind in ("poll", "wait"):
        bar_x, bar_y = x + BAR_PAD, y + 60.0
        parts.append('<rect class="bar-track" x="%s" y="%s" width="%s" '
                     'height="%s" rx="3" ry="3"/>'
                     % (fnum(bar_x), fnum(bar_y), fnum(BAR_W), fnum(BAR_H)))
        parts.append('<rect id="bar-fill-%s" class="bar-fill" x="%s" y="%s" '
                     'width="0" height="%s" rx="3" ry="3"/>'
                     % (s["id"], fnum(bar_x), fnum(bar_y), fnum(BAR_H)))
    parts.append('</g>')
    return "\n".join(parts)


def _edge_markup(e, positions, main_order):
    src, dst = positions[e["from_id"]], positions[e["to_id"]]
    src_i = main_order.index(e["from_id"]) if e["from_id"] in main_order else None
    dst_i = main_order.index(e["to_id"]) if e["to_id"] in main_order else None

    if src_i is not None and dst_i is not None and dst_i == src_i + 1:
        # Consecutive down the main column: a straight drop.
        x1, y1 = src["x"] + src["w"] / 2.0, src["y"] + src["h"]
        x2, y2 = dst["x"] + dst["w"] / 2.0, dst["y"]
        path = ('<line class="edge" x1="%s" y1="%s" x2="%s" y2="%s" '
               'marker-end="url(#arrow)"/>'
               % (fnum(x1), fnum(y1), fnum(x2), fnum(y2)))
        # x1 is the same for every consecutive edge in one main column, but
        # (y1 + y2) / 2 is not: each row pitch is unique, so this only
        # collides if a future diagram puts two main columns at the same x.
        label_x, label_y = x1 + 10.0, (y1 + y2) / 2.0
    else:
        # An early exit to a side box: an S-curve out to the right.
        x1, y1 = src["x"] + src["w"], src["y"] + src["h"] / 2.0
        x2, y2 = dst["x"], dst["y"] + dst["h"] / 2.0
        c1x, c2x = x1 + SIDE_GAP / 2.0, x2 - SIDE_GAP / 2.0
        path = ('<path class="edge" d="M %s %s C %s %s, %s %s, %s %s" '
               'marker-end="url(#arrow)"/>'
               % (fnum(x1), fnum(y1), fnum(c1x), fnum(y1),
                  fnum(c2x), fnum(y2), fnum(x2), fnum(y2)))
        # Anchored at the source end, not the target: every side edge in
        # this flow lands on the same shared "stopped" box, so a label
        # placed near that shared end collides with every other one that
        # lands there too. The source end is what tells the branches
        # apart.
        label_x, label_y = x1 + 10.0, y1 - 8.0

    out = [path]
    if e["label"]:
        out.append('<text class="label-edge" x="%s" y="%s" '
                   'text-anchor="middle">%s</text>'
                   % (fnum(label_x), fnum(label_y), _esc(e["label"])))
    return "\n".join(out)


def draw_states(flow_):
    """The body markup of a state-ladder diagram: boxes, arrows, bars.

    One string, the same for every palette a caller later wraps it in;
    only css_for's colors and keyframe durations tell two renders of the
    same flow apart.
    """
    layout = _layout(flow_)
    positions, main_order = layout["positions"], layout["main_order"]
    parts = [DEFS_MARKUP]
    for s in flow_["steps"]:
        parts.append(_box_markup(positions[s["id"]]))
    for e in flow_["edges"]:
        parts.append(_edge_markup(e, positions, main_order))
    return "\n".join(parts)


def draw_lifecycle_note(layout):
    """The memory-refusal self-loop, as a note beside "stopped" instead of
    a drawn arrow back onto itself.

    _edge_markup only ever connects two different boxes; one box that is
    both the source and the target of the same curve would need a shape
    nothing else in this file draws, for one edge that is not a step to a
    different state anyway, it is "start refused, nothing changed".
    """
    pos = layout["positions"]["stopped"]
    note_x = pos["x"] - LIFECYCLE_LOOP_2 - 20.0
    note_y = pos["y"] + pos["h"] / 2.0 + 4.0
    return ('<text class="label-note" x="%s" y="%s" text-anchor="end">'
           '%s</text>'
           % (fnum(note_x), fnum(note_y), _esc(LIFECYCLE_NOTE_TEXT)))


def _linear_badge_markup(pos):
    """The small numbered circle at a box's top-left corner, create-flow's
    own cue that this diagram reads as an ordered checklist."""
    cx, cy, number = pos["x"], pos["y"], pos["number"]
    parts = ['<circle class="linear-badge" cx="%s" cy="%s" r="%s"/>'
            % (fnum(cx), fnum(cy), fnum(LINEAR_BADGE_R))]
    parts.append('<text class="linear-badge-text" x="%s" y="%s" '
                 'text-anchor="middle">%s</text>'
                 % (fnum(cx), fnum(cy + 4.0), number))
    return "\n".join(parts)


def _linear_edge_markup(e, positions):
    """One arrow of the checklist: sideways within a row, straight down
    where the snake wraps to the next one."""
    src, dst = positions[e["from_id"]], positions[e["to_id"]]
    if src["y"] == dst["y"]:
        if dst["x"] >= src["x"]:
            x1, x2 = src["x"] + src["w"], dst["x"]
        else:
            x1, x2 = src["x"], dst["x"] + dst["w"]
        y1 = y2 = src["y"] + src["h"] / 2.0
    else:
        x1 = x2 = src["x"] + src["w"] / 2.0
        y1, y2 = src["y"] + src["h"], dst["y"]
    path = ('<line class="edge" x1="%s" y1="%s" x2="%s" y2="%s" '
           'marker-end="url(#arrow)"/>'
           % (fnum(x1), fnum(y1), fnum(x2), fnum(y2)))
    out = [path]
    if e["label"]:
        label_x, label_y = (x1 + x2) / 2.0, y1 - 6.0
        out.append('<text class="label-edge" x="%s" y="%s" '
                   'text-anchor="middle">%s</text>'
                   % (fnum(label_x), fnum(label_y), _esc(e["label"])))
    return "\n".join(out)


def draw_linear(flow_):
    """The body markup of a boustrophedon checklist diagram.

    Reuses _box_markup for every box unchanged, a plain action step needs
    nothing _box_markup does not already draw; only the grid position and
    a numbered badge are new.
    """
    layout = _layout_linear(flow_)
    positions = layout["positions"]
    parts = [DEFS_MARKUP]
    for s in flow_["steps"]:
        parts.append(_box_markup(positions[s["id"]]))
        parts.append(_linear_badge_markup(positions[s["id"]]))
    for e in flow_["edges"]:
        parts.append(_linear_edge_markup(e, positions))
    return "\n".join(parts)


def _stairs_edge_markup(e, positions, main_order):
    """One arrow of the staircase: straight from one step to the next,
    vertical inside a rung and diagonal where the rung changes, or an
    S-curve out to the shared "stopped" box."""
    src, dst = positions[e["from_id"]], positions[e["to_id"]]
    if e["to_id"] in main_order:
        x1, y1 = src["x"] + src["w"] / 2.0, src["y"] + src["h"]
        x2, y2 = dst["x"] + dst["w"] / 2.0, dst["y"]
        path = ('<line class="edge" x1="%s" y1="%s" x2="%s" y2="%s" '
               'marker-end="url(#arrow)"/>'
               % (fnum(x1), fnum(y1), fnum(x2), fnum(y2)))
        label_x, label_y = x1 + 10.0, (y1 + y2) / 2.0
    else:
        x1, y1 = src["x"] + src["w"], src["y"] + src["h"] / 2.0
        x2, y2 = dst["x"], dst["y"] + dst["h"] / 2.0
        gap = (x2 - x1) / 2.0
        c1x, c2x = x1 + gap, x2 - gap
        path = ('<path class="edge" d="M %s %s C %s %s, %s %s, %s %s" '
               'marker-end="url(#arrow)"/>'
               % (fnum(x1), fnum(y1), fnum(c1x), fnum(y1),
                  fnum(c2x), fnum(y2), fnum(x2), fnum(y2)))
        label_x, label_y = x1 + 10.0, y1 - 8.0

    out = [path]
    if e["label"]:
        out.append('<text class="label-edge" x="%s" y="%s" '
                   'text-anchor="middle">%s</text>'
                   % (fnum(label_x), fnum(label_y), _esc(e["label"])))
    return "\n".join(out)


def draw_stairs(flow_):
    """The body markup of the stop-ladder staircase: boxes, bars, arrows."""
    layout = _layout_stairs(flow_)
    positions, main_order = layout["positions"], layout["main_order"]
    parts = [DEFS_MARKUP]
    for s in flow_["steps"]:
        parts.append(_box_markup(positions[s["id"]]))
    for e in flow_["edges"]:
        parts.append(_stairs_edge_markup(e, positions, main_order))
    return "\n".join(parts)


def _lifecycle_edge_markup(e, positions, main_order):
    """One arrow of the lifecycle column: a straight drop for a forward
    step, a loop bulging out to the left for a step back onto an earlier
    state, or an S-curve out to the "deleted" side box.

    The loop is what _edge_markup has no shape for: two of this flow's
    edges land back on "stopped" from further down the same column, not
    from a side box, so they need their own curve out and back rather
    than the generic side-box S.
    """
    src, dst = positions[e["from_id"]], positions[e["to_id"]]
    src_i = main_order.index(e["from_id"]) if e["from_id"] in main_order else None
    dst_i = main_order.index(e["to_id"]) if e["to_id"] in main_order else None

    if src_i is not None and dst_i is not None and dst_i == src_i + 1:
        x1, y1 = src["x"] + src["w"] / 2.0, src["y"] + src["h"]
        x2, y2 = dst["x"] + dst["w"] / 2.0, dst["y"]
        path = ('<line class="edge" x1="%s" y1="%s" x2="%s" y2="%s" '
               'marker-end="url(#arrow)"/>'
               % (fnum(x1), fnum(y1), fnum(x2), fnum(y2)))
        label_x, label_y = x1 + 10.0, (y1 + y2) / 2.0
        anchor = "middle"
    elif src_i is not None and dst_i is not None and dst_i < src_i:
        depth = LIFECYCLE_LOOP_1 if src_i - dst_i == 1 else LIFECYCLE_LOOP_2
        x1, y1 = src["x"], src["y"] + src["h"] / 2.0
        x2, y2 = dst["x"], dst["y"] + dst["h"] / 2.0
        c1x, c2x = x1 - depth, x2 - depth
        path = ('<path class="edge" d="M %s %s C %s %s, %s %s, %s %s" '
               'marker-end="url(#arrow)"/>'
               % (fnum(x1), fnum(y1), fnum(c1x), fnum(y1),
                  fnum(c2x), fnum(y2), fnum(x2), fnum(y2)))
        label_x, label_y = x1 - depth - 8.0, (y1 + y2) / 2.0
        anchor = "end"
    else:
        x1, y1 = src["x"] + src["w"], src["y"] + src["h"] / 2.0
        x2, y2 = dst["x"], dst["y"] + dst["h"] / 2.0
        gap = SIDE_GAP / 2.0
        c1x, c2x = x1 + gap, x2 - gap
        path = ('<path class="edge" d="M %s %s C %s %s, %s %s, %s %s" '
               'marker-end="url(#arrow)"/>'
               % (fnum(x1), fnum(y1), fnum(c1x), fnum(y1),
                  fnum(c2x), fnum(y2), fnum(x2), fnum(y2)))
        label_x, label_y = x1 + 10.0, y1 - 8.0
        anchor = "middle"

    out = [path]
    if e["label"]:
        out.append('<text class="label-edge" x="%s" y="%s" '
                   'text-anchor="%s">%s</text>'
                   % (fnum(label_x), fnum(label_y), anchor, _esc(e["label"])))
    return "\n".join(out)


def draw_lifecycle(flow_):
    """The body markup of the README lifecycle column: boxes, arrows, the
    memory-refusal note beside "stopped"."""
    layout = _layout_lifecycle(flow_)
    positions, main_order = layout["positions"], layout["main_order"]
    parts = [DEFS_MARKUP]
    for s in flow_["steps"]:
        parts.append(_box_markup(positions[s["id"]]))
    for e in flow_["edges"]:
        parts.append(_lifecycle_edge_markup(e, positions, main_order))
    parts.append(draw_lifecycle_note(layout))
    return "\n".join(parts)


def _topology_edge_markup(e, positions):
    """One spoke: a straight line from the hub to a connected step.

    A topology has no main column to be consecutive down, so this is
    simpler than _edge_markup: every edge starts at the hub, and the only
    question is which of the hub's two free edges, top or bottom, faces
    the step it goes to.
    """
    src, dst = positions[e["from_id"]], positions[e["to_id"]]
    src_cx, dst_cx = src["x"] + src["w"] / 2.0, dst["x"] + dst["w"] / 2.0
    if dst["y"] < src["y"]:
        x1, y1 = src_cx, src["y"]
        x2, y2 = dst_cx, dst["y"] + dst["h"]
    else:
        x1, y1 = src_cx, src["y"] + src["h"]
        x2, y2 = dst_cx, dst["y"]
    path = ('<line class="edge" x1="%s" y1="%s" x2="%s" y2="%s" '
           'marker-end="url(#arrow)"/>'
           % (fnum(x1), fnum(y1), fnum(x2), fnum(y2)))
    # Offset past the line's own midpoint: with one hub, every spoke's
    # start point (x1, y1) is the same, so anchoring there the way the
    # side-curve fix in _edge_markup does would collide again. The far
    # end differs per step, and so does this midpoint, because x2 does.
    label_x, label_y = (x1 + x2) / 2.0 + 6.0, (y1 + y2) / 2.0

    out = [path]
    if e["label"]:
        out.append('<text class="label-edge" x="%s" y="%s" '
                   'text-anchor="middle">%s</text>'
                   % (fnum(label_x), fnum(label_y), _esc(e["label"])))
    return "\n".join(out)


def draw_topology(flow_):
    """The body markup of a hub-and-spoke topology diagram.

    Static, no animation: a "what relates to what" diagram has no time
    dimension for a bar to fill. Reuses _box_markup as is, since an
    instant-kind box with no seconds needs nothing draw_states's boxes
    do not already draw.
    """
    layout = _layout_topology(flow_)
    positions = layout["positions"]
    parts = [DEFS_MARKUP]
    for s in flow_["steps"]:
        parts.append(_box_markup(positions[s["id"]]))
    for e in flow_["edges"]:
        parts.append(_topology_edge_markup(e, positions))
    for sid in layout["detached"]:
        note = positions[sid]["step"]["outcome"]
        if note:
            pos = positions[sid]
            note_x, note_y = pos["x"] + pos["w"] / 2.0, pos["y"] + pos["h"] + 16.0
            parts.append('<text class="label-note" x="%s" y="%s" '
                         'text-anchor="middle">%s</text>'
                         % (fnum(note_x), fnum(note_y), _esc(note)))
    return "\n".join(parts)


def draw_swimlane(flow_, channels):
    """The body markup of a swimlane diagram: one column per actor.

    abgal's column holds the real step boxes, reusing _box_markup exactly
    as draw_states does. A step named in `channels` gets a straight line
    across to that actor's lane, an arrow for a one-shot instant/action
    step. A poll/wait step gets a dashed line instead of an arrowhead,
    because it is an exchange repeated for a while, not a single message;
    _swimlane_extra_css puts a small circle on that line that ping-pongs
    for the same, already-established duration draw_states's bars use.
    """
    layout = _layout_swimlane(flow_)
    lane_x, lane_w, rows = layout["lane_x"], layout["lane_w"], layout["rows"]
    parts = [DEFS_MARKUP]

    for lane in LANE_ORDER:
        header = step("lane-header-%s" % lane, None, LANE_LABELS[lane],
                      "instant")
        parts.append(_box_markup({"x": lane_x[lane], "y": layout["header_y"],
                                  "w": lane_w[lane], "h": SWIM_HEADER_H,
                                  "step": header}))

    rail_top = layout["header_y"] + SWIM_HEADER_H
    rail_bottom = layout["height"] - MARGIN
    for lane in LANE_ORDER:
        if lane == "abgal":
            continue
        cx = lane_x[lane] + lane_w[lane] / 2.0
        parts.append('<line class="lane-rail" x1="%s" y1="%s" x2="%s" y2="%s"/>'
                     % (fnum(cx), fnum(rail_top), fnum(cx), fnum(rail_bottom)))

    abgal_right = lane_x["abgal"] + lane_w["abgal"]
    for s in flow_["steps"]:
        row = rows[s["id"]]
        parts.append(_box_markup({"x": lane_x["abgal"], "y": row["y"],
                                  "w": lane_w["abgal"], "h": BOX_H, "step": s}))

        target = channels.get(s["id"])
        if not target:
            continue
        y_mid = row["y"] + BOX_H / 2.0
        x2 = lane_x[target] + lane_w[target] / 2.0
        if s["kind"] in ("poll", "wait") and s["seconds"]:
            parts.append('<line class="lane-edge-poll" x1="%s" y1="%s" '
                         'x2="%s" y2="%s"/>'
                         % (fnum(abgal_right), fnum(y_mid), fnum(x2), fnum(y_mid)))
            parts.append('<circle id="ping-%s" class="ping" cx="%s" cy="%s" '
                         'r="4.00"/>'
                         % (s["id"], fnum(abgal_right), fnum(y_mid)))
        else:
            parts.append('<line class="lane-edge" x1="%s" y1="%s" x2="%s" '
                         'y2="%s" marker-end="url(#arrow)"/>'
                         % (fnum(abgal_right), fnum(y_mid), fnum(x2), fnum(y_mid)))

    return "\n".join(parts)


def _duration_caption(s):
    """The real-seconds text a poll or wait step carries, factored out of
    _box_markup so draw_sequence's self-loops can show the same words.
    """
    if s["seconds"] is None:
        return None
    if s["cap"] == "loop":
        return "%d s, no limit ..." % s["seconds"]
    if s["cap"]:
        return "up to %d s" % s["seconds"]
    return "%d s" % s["seconds"]


# The message text on each request/response arrow: real vocabulary from
# FLOW_START's own step labels and abgal_start:773-952, condensed to what
# fits on one line the way a real sequenceDiagram's message text does.
SEQ_REQUEST_LABEL = {
    "preflight": "preflight, refuse a running guest or too little memory",
    "launch": "launch, detached, logs to emulator.log",
    "poll-console": "who is this, every 2 s",
    "start-watch": "start abgal watch as a subprocess",
    "poll-boot": "boot_completed, every 3 s",
}
SEQ_RESPONSE_LABEL = {
    "preflight": "ok", "launch": "launched", "poll-console": "answered",
    "start-watch": "started", "poll-boot": "booted",
}
SEQ_POLL_NOTE = {
    "poll-console": "poll console, up to 300 s",
    "poll-boot": "poll boot, up to 300 s",
}
SEQ_WAIT_NOTE = {
    "wait-settle": "wait settle, fixed 2 s, then abgal checks its own "
                   "child process",
}
# The alt frame's two condition headers, the only wording in this engine
# with no FIELDS column of its own to read from; the "no" branch's own
# message still comes straight from the matching fail-* step's real
# label, never invented here.
SEQ_ALT_HEADERS = {
    "decision-console": ("no answer in time", "console answered"),
    "decision-watch": ("watch died at once", "watch still alive"),
    "decision-boot": ("not booted in time", "booted in time"),
}


def _seq_fail_id(flow_, decision_id):
    for e in flow_["edges"]:
        if e["from_id"] == decision_id and e["label"] == "no":
            return e["to_id"]
    return None


def draw_sequence(flow_, channels):
    """The body markup of a literal sequence diagram: a lifeline per
    actor, solid request and dotted response arrows with real message
    text, a shaded rect around a poll's note and its alt branches, an
    unshaded, narrow alt alone for wait-settle's decision since that step
    itself sends no message for a rect to hold.
    """
    layout = _layout_sequence(flow_)
    lane_x, lane_w = layout["lane_x"], layout["lane_w"]
    by_id = dict((s["id"], s) for s in flow_["steps"])
    parts = [DEFS_MARKUP]

    for lane in LANE_ORDER:
        header = step("lane-header-%s" % lane, None, LANE_LABELS[lane],
                      "instant")
        parts.append(_box_markup({"x": lane_x[lane], "y": layout["header_y"],
                                  "w": lane_w[lane], "h": SWIM_HEADER_H,
                                  "step": header}))

    rail_top = layout["header_y"] + SWIM_HEADER_H
    rail_bottom = layout["height"] - MARGIN
    for lane in LANE_ORDER:
        cx = lane_x[lane] + lane_w[lane] / 2.0
        parts.append('<line class="lane-rail" x1="%s" y1="%s" x2="%s" y2="%s"/>'
                     % (fnum(cx), fnum(rail_top), fnum(cx), fnum(rail_bottom)))

    abgal_cx = lane_x["abgal"] + lane_w["abgal"] / 2.0
    # Every alt frame shares one width, wide enough for the poll blocks'
    # real message to adb, so the wait-settle decision's frame (no other
    # participant involved) is not left too narrow for its own longest
    # fail-* text to wrap into, the bug an earlier, narrower guess had.
    adb_right = lane_x["adb"] + lane_w["adb"]
    alt_frame_x = abgal_cx - BOX_W / 2.0 - 6.0
    alt_frame_w = adb_right - alt_frame_x + 16.0
    number = [0]

    def request(x2, y, cls, label):
        number[0] += 1
        parts.append('<line class="%s" x1="%s" y1="%s" x2="%s" y2="%s" '
                     'marker-end="url(#arrow)"/>'
                     % (cls, fnum(abgal_cx), fnum(y), fnum(x2), fnum(y)))
        parts.append('<text class="label-edge" x="%s" y="%s" '
                     'text-anchor="middle">%d. %s</text>'
                     % (fnum((abgal_cx + x2) / 2.0), fnum(y - 6), number[0],
                        _esc(label)))

    def response(x2, y, label):
        number[0] += 1
        parts.append('<line class="seq-edge-resp" x1="%s" y1="%s" x2="%s" '
                     'y2="%s" marker-end="url(#arrow)"/>'
                     % (fnum(x2), fnum(y), fnum(abgal_cx), fnum(y)))
        parts.append('<text class="label-edge" x="%s" y="%s" '
                     'text-anchor="middle">%d. %s</text>'
                     % (fnum((abgal_cx + x2) / 2.0), fnum(y - 6), number[0],
                        _esc(label)))

    def self_fail(y, label, max_w):
        number[0] += 1
        x = abgal_cx + 10.0
        loop = ('M %s %s C %s %s, %s %s, %s %s'
               % (fnum(x), fnum(y), fnum(x + SEQ_LOOP_W), fnum(y),
                  fnum(x + SEQ_LOOP_W), fnum(y + 16), fnum(x), fnum(y + 16)))
        parts.append('<path class="seq-edge-fail" d="%s" '
                     'marker-end="url(#arrow)"/>' % loop)
        text_x = x + SEQ_LOOP_W + 8
        for i, line in enumerate(_wrap(label, max_w)[:2]):
            parts.append('<text class="label-edge" x="%s" y="%s">%s</text>'
                         % (fnum(text_x), fnum(y + 4 + i * 12),
                            ("%d. %s" % (number[0], _esc(line))) if i == 0
                            else _esc(line)))

    for block in layout["blocks"]:
        sid = block["id"]
        s = by_id[sid]
        btype = block["type"]

        if btype == "ready":
            ready_w = layout["width"] - 2 * MARGIN - 20.0
            parts.append(_box_markup({"x": MARGIN, "y": block["y"],
                                      "w": ready_w, "h": BOX_H, "step": s}))
            continue

        if btype == "pair":
            target = channels[sid]
            x2 = lane_x[target] + lane_w[target] / 2.0
            request(x2, block["req_y"], "seq-edge-req", SEQ_REQUEST_LABEL[sid])
            response(x2, block["resp_y"],
                    "%s (instant)" % SEQ_RESPONSE_LABEL[sid])
            continue

        alt_id = block.get("alt_id")
        headers = SEQ_ALT_HEADERS.get(alt_id, ("", ""))
        fail_id = _seq_fail_id(flow_, alt_id) if alt_id else None
        fail_label = by_id[fail_id]["label"] if fail_id else ""

        if btype == "poll":
            target = channels[sid]
            x2 = lane_x[target] + lane_w[target] / 2.0
            rect_x, rect_w = alt_frame_x, alt_frame_w
            parts.append('<rect class="seq-rect-poll" x="%s" y="%s" '
                         'width="%s" height="%s" rx="6" ry="6"/>'
                         % (fnum(rect_x), fnum(block["rect_top"]),
                            fnum(rect_w),
                            fnum(block["rect_bottom"] - block["rect_top"])))
            parts.append('<text class="label-note" x="%s" y="%s">%s</text>'
                         % (fnum(rect_x + 8), fnum(block["note_y"]),
                            _esc(SEQ_POLL_NOTE[sid])))
            request(x2, block["req_y"], "seq-edge-poll", SEQ_REQUEST_LABEL[sid])
            parts.append('<circle id="seq-ping-%s" class="ping" cx="%s" '
                         'cy="%s" r="3.5"/>'
                         % (sid, fnum(abgal_cx), fnum(block["req_y"])))
        else:
            rect_x = abgal_cx - BOX_W / 2.0
            rect_w = BOX_W
            parts.append('<rect class="seq-rect-wait" x="%s" y="%s" '
                         'width="%s" height="%s" rx="6" ry="6"/>'
                         % (fnum(rect_x), fnum(block["rect_top"]),
                            fnum(rect_w),
                            fnum(block["rect_bottom"] - block["rect_top"])))
            for i, line in enumerate(_wrap(SEQ_WAIT_NOTE[sid], rect_w - 16)):
                parts.append('<text class="label-note" x="%s" y="%s">%s'
                             '</text>' % (fnum(rect_x + 8),
                                         fnum(block["note_y"] + i * 12),
                                         _esc(line)))
            bar_x = abgal_cx - BAR_W / 2.0
            parts.append('<rect class="bar-track" x="%s" y="%s" width="%s" '
                         'height="%s" rx="3" ry="3"/>'
                         % (fnum(bar_x), fnum(block["bar_y"]), fnum(BAR_W),
                            fnum(BAR_H)))
            parts.append('<rect id="bar-fill-%s" class="bar-fill" x="%s" '
                         'y="%s" width="0" height="%s" rx="3" ry="3"/>'
                         % (sid, fnum(bar_x), fnum(block["bar_y"]),
                            fnum(BAR_H)))
            parts.append('<text class="label-duration" x="%s" y="%s" '
                         'text-anchor="middle">2 s</text>'
                         % (fnum(abgal_cx), fnum(block["bar_y"] + BAR_H + 14.0)))

        if not alt_id:
            continue

        parts.append('<rect class="alt-frame" x="%s" y="%s" width="%s" '
                     'height="%s" rx="4" ry="4"/>'
                     % (fnum(alt_frame_x), fnum(block["alt_top"]),
                        fnum(alt_frame_w),
                        fnum(block["alt_bottom"] - block["alt_top"])))
        parts.append('<line class="alt-divider" x1="%s" y1="%s" x2="%s" '
                     'y2="%s"/>'
                     % (fnum(alt_frame_x), fnum(block["divider_y"]),
                        fnum(alt_frame_x + alt_frame_w),
                        fnum(block["divider_y"])))
        parts.append('<text class="label-alt" x="%s" y="%s">[%s]</text>'
                     % (fnum(alt_frame_x + 6), fnum(block["header1_y"]),
                        _esc(headers[0])))
        parts.append('<text class="label-alt" x="%s" y="%s">[%s]</text>'
                     % (fnum(alt_frame_x + 6), fnum(block["header2_y"]),
                        _esc(headers[1])))
        self_fail(block["branch1_y"], fail_label,
                 alt_frame_x + alt_frame_w
                 - (abgal_cx + 10.0 + SEQ_LOOP_W + 8) - 6.0)
        if btype == "poll":
            response(x2, block["branch2_y"], SEQ_RESPONSE_LABEL[sid])
        else:
            parts.append('<text class="label-note" x="%s" y="%s">alive'
                         '</text>' % (fnum(abgal_cx + 10.0),
                                     fnum(block["branch2_y"] + 4)))

    return "\n".join(parts)


def _port_edge_markup(src, dst):
    """One claim, a straight line from a guest box to its port slot.

    When the target sits in the row above (every real slot does), the
    line runs from the guest box's own top edge to the slot's own bottom
    edge, its y never leaving that gap, so it cannot clip a box no matter
    how far left or right the two boxes sit from each other (the same
    proof FLOW_WATCH's retry/unreadable boxes rely on, applied to a
    diagonal instead of a vertical). guest-auto-3 to dead-end sits in the
    same row instead, so it is a plain horizontal line between them, with
    nothing else in that row between the two to clip.
    """
    if dst["y"] < src["y"]:
        x1, y1 = src["x"] + src["w"] / 2.0, src["y"]
        x2, y2 = dst["x"] + dst["w"] / 2.0, dst["y"] + dst["h"]
    else:
        x1, y1 = src["x"] + src["w"], src["y"] + src["h"] / 2.0
        x2, y2 = dst["x"], dst["y"] + dst["h"] / 2.0
    return ('<line class="edge" x1="%s" y1="%s" x2="%s" y2="%s" '
           'marker-end="url(#arrow)"/>'
           % (fnum(x1), fnum(y1), fnum(x2), fnum(y2)))


def draw_ports(flow_):
    """The body markup of the port-slots diagram: a row of 16 real slots,
    a row of illustrative claims below it.

    Every box reuses _box_markup unchanged, so it reads as the same
    document as every other diagram; nothing new was needed there. Two
    captions above the slots carry the fact/illustration split this
    diagram is built around: a plain label-main line states the real
    rule (16 slots, the range, why it matters to adb), a label-note line
    right under it says outright that the fill sequence below is an
    example, not a measured run, the same distinction pieces-topology's
    detached-node note already draws with the same two classes.
    """
    layout = _layout_ports(flow_)
    positions = layout["positions"]
    parts = [DEFS_MARKUP]

    cx = layout["width"] / 2.0
    parts.append('<text class="label-main" x="%s" y="%s" '
                 'text-anchor="middle">abgal --port: 16 slots, 5554 to '
                 '5584, even only. Outside that, adb cannot find the '
                 'guest.</text>' % (fnum(cx), fnum(MARGIN + 14)))
    parts.append('<text class="label-note" x="%s" y="%s" '
                 'text-anchor="middle">Illustrative fill sequence below, '
                 'not a measured run. Which ports are actually busy is '
                 'runtime state; abgal does not track it.</text>'
                 % (fnum(cx), fnum(MARGIN + 30)))

    for s in flow_["steps"]:
        parts.append(_box_markup(positions[s["id"]]))

    busy_lo, busy_hi = PORT_LO, PORT_LO + 12 * PORT_STEP
    busy_cx = (positions["slot-%d" % busy_lo]["x"]
              + positions["slot-%d" % busy_hi]["x"]
              + PORT_SLOT_W) / 2.0
    busy_y = layout["slot_y"] + BOX_H + (PORT_ROW_GAP / 2.0)
    parts.append('<text class="label-note" x="%s" y="%s" '
                 'text-anchor="middle">13 more, already running '
                 '(example)</text>' % (fnum(busy_cx), fnum(busy_y)))

    for e in flow_["edges"]:
        parts.append(_port_edge_markup(positions[e["from_id"]],
                                       positions[e["to_id"]]))
    return "\n".join(parts)


# ---------------------------------------------------------- palettes and css


PALETTE_FIELDS = ("bg", "fg", "muted", "box-fill", "box-stroke",
                  "decision-fill", "track", "accent", "ok-fill", "ok-stroke",
                  "bad-fill", "bad-stroke", "arrow")

PALETTES = {
    "light": {
        "bg": "#ffffff", "fg": "#1a1a1a", "muted": "#5b5b63",
        "box-fill": "#f4f4f6", "box-stroke": "#33333d",
        "decision-fill": "#eef1fb", "track": "#dcdce2", "accent": "#2f5fd6",
        "ok-fill": "#e8f7ee", "ok-stroke": "#1a7f37",
        "bad-fill": "#fbeaea", "bad-stroke": "#b42318", "arrow": "#33333d",
    },
    "dark": {
        "bg": "#1b1b1f", "fg": "#e9e9ee", "muted": "#a3a3ad",
        "box-fill": "#2a2a30", "box-stroke": "#c7c7d1",
        "decision-fill": "#26283a", "track": "#3c3c44", "accent": "#7ea2ff",
        "ok-fill": "#173524", "ok-stroke": "#4ade80",
        "bad-fill": "#3a1c1c", "bad-stroke": "#f87171", "arrow": "#c7c7d1",
    },
}


def _scale(flow_):
    """TARGET_LOOP_SECONDS spread over this flow's real wait/poll seconds.

    Computed once per flow and applied to every animated element's own
    duration, so every bar in the diagram shares one 8 s loop without any
    of them needing to know about the others.
    """
    total = sum(s["seconds"] for s in flow_["steps"]
               if s["kind"] in ("poll", "wait") and s["seconds"])
    return TARGET_LOOP_SECONDS / total if total else 1.0


def css_for(palette, flow_):
    """The `<style>` block for one palette: custom properties plus keyframes.

    Same structure and the same keyframe timings for "light" and "dark",
    only the custom property values differ.
    """
    colors = PALETTES[palette]
    scale = _scale(flow_)
    lines = ["<style>", ":root {"]
    for name in PALETTE_FIELDS:
        lines.append("  --%s: %s;" % (name, colors[name]))
    lines.append("}")
    lines.append("svg { background: var(--bg); }")
    lines.append("text { font-family: Helvetica, Arial, sans-serif; "
                 "fill: var(--fg); }")
    lines.append(".label-actor { font-size: 10px; fill: var(--muted); "
                 "letter-spacing: .05em; text-transform: uppercase; }")
    lines.append(".label-main { font-size: 12.5px; }")
    lines.append(".label-duration { font-size: 11px; font-style: italic; "
                 "fill: var(--muted); }")
    lines.append(".label-edge { font-size: 11px; fill: var(--muted); }")
    lines.append(".label-note { font-size: 11px; font-style: italic; "
                 "fill: var(--muted); }")
    lines.append(".box, .box-instant, .box-action { fill: var(--box-fill); "
                 "stroke: var(--box-stroke); stroke-width: 1.5; }")
    lines.append(".box-decision { fill: var(--decision-fill); "
                 "stroke: var(--box-stroke); stroke-width: 1.5; "
                 "stroke-dasharray: 4 3; }")
    lines.append(".box-ok { fill: var(--ok-fill); stroke: var(--ok-stroke); "
                 "stroke-width: 2; }")
    lines.append(".box-bad { fill: var(--bad-fill); "
                 "stroke: var(--bad-stroke); stroke-width: 2; }")
    lines.append(".bar-track { fill: var(--track); }")
    lines.append(".bar-fill { fill: var(--accent); }")
    lines.append(".edge { stroke: var(--arrow); stroke-width: 1.5; "
                 "fill: none; }")
    lines.append(".arrowhead { fill: var(--arrow); }")
    lines.append("@keyframes bar-fill { from { width: 0; } "
                 "to { width: %spx; } }" % fnum(BAR_W))
    for s in flow_["steps"]:
        if s["kind"] in ("poll", "wait") and s["seconds"]:
            duration = fnum(max(s["seconds"] * scale, MIN_BAR_SECONDS))
            # An uncapped loop (cap="loop") plays its real interval a fixed
            # MAX_BLIPS times and then holds, instead of looping forever
            # the way every bounded poll/wait's bar already does: a stand-in
            # for "keeps going", not a claim that it stops after four.
            iteration = str(MAX_BLIPS) if s["cap"] == "loop" else "infinite"
            lines.append("#bar-fill-%s { animation: bar-fill %ss linear "
                         "%s; }" % (s["id"], duration, iteration))
    lines.append("</style>")
    return "\n".join(lines)


def _swimlane_extra_css(flow_, channels, layout):
    """A second, palette-independent `<style>` block, swimlane's own.

    Kept apart from css_for rather than folded into it, so stop-ladder,
    pieces-topology and create-flow never carry a lane/ping rule they
    have no boxes or ids for. Every color here is still one of css_for's
    custom properties, so it still repaints correctly for "dark" even
    though this block does not depend on palette itself.
    """
    scale = _scale(flow_)
    lane_x, lane_w = layout["lane_x"], layout["lane_w"]
    x1 = lane_x["abgal"] + lane_w["abgal"]
    lines = ["<style>"]
    lines.append(".lane-rail { stroke: var(--box-stroke); stroke-width: 1; "
                 "stroke-dasharray: 2 4; fill: none; }")
    lines.append(".lane-edge { stroke: var(--arrow); stroke-width: 1.5; "
                 "fill: none; }")
    lines.append(".lane-edge-poll { stroke: var(--accent); stroke-width: 1.5; "
                 "fill: none; stroke-dasharray: 5 4; }")
    lines.append(".ping { fill: var(--accent); }")
    for s in flow_["steps"]:
        target = channels.get(s["id"])
        if not target or s["kind"] not in ("poll", "wait") or not s["seconds"]:
            continue
        x2 = lane_x[target] + lane_w[target] / 2.0
        duration = fnum(max(s["seconds"] * scale, MIN_BAR_SECONDS))
        lines.append("@keyframes ping-%s { from { cx: %s; } to { cx: %s; } }"
                     % (s["id"], fnum(x1), fnum(x2)))
        lines.append("#ping-%s { animation: ping-%s %ss ease-in-out "
                     "infinite alternate; }" % (s["id"], s["id"], duration))
    lines.append("</style>")
    return "\n".join(lines)


def _linear_extra_css():
    """A second, palette-independent `<style>` block, create-flow's own
    numbered badges. Kept apart from css_for so no other diagram carries
    a badge class it has no circles for."""
    lines = ["<style>"]
    lines.append(".linear-badge { fill: var(--accent); }")
    lines.append(".linear-badge-text { font-size: 11px; font-weight: bold; "
                 "fill: var(--bg); }")
    lines.append("</style>")
    return "\n".join(lines)


def _sequence_extra_css(flow_, channels, layout):
    """A second, palette-independent `<style>` block, sequence's own.

    Solid, dotted and self-loop edges stay put; only a poll's request
    line gets a moving ping, the same "this repeats for a while" stand-in
    swimlane's own ping already established, scaled by the same shared
    TARGET_LOOP_SECONDS budget every animated element in this file uses.
    """
    scale = _scale(flow_)
    lane_x, lane_w = layout["lane_x"], layout["lane_w"]
    abgal_cx = lane_x["abgal"] + lane_w["abgal"] / 2.0
    lines = ["<style>"]
    lines.append(".lane-rail { stroke: var(--box-stroke); stroke-width: 1; "
                 "stroke-dasharray: 2 4; fill: none; }")
    lines.append(".seq-edge-req { stroke: var(--arrow); stroke-width: 1.5; "
                 "fill: none; }")
    lines.append(".seq-edge-resp { stroke: var(--arrow); stroke-width: 1.5; "
                 "stroke-dasharray: 5 3; fill: none; }")
    lines.append(".seq-edge-poll { stroke: var(--arrow); stroke-width: 1.5; "
                 "fill: none; }")
    lines.append(".seq-edge-fail { stroke: var(--bad-stroke); "
                 "stroke-width: 1.5; fill: none; }")
    lines.append(".seq-rect-poll { fill: var(--decision-fill); "
                 "stroke: none; }")
    lines.append(".seq-rect-wait { fill: var(--bad-fill); stroke: none; }")
    lines.append(".alt-frame { fill: none; stroke: var(--box-stroke); "
                 "stroke-width: 1; stroke-dasharray: 4 3; }")
    lines.append(".alt-divider { stroke: var(--box-stroke); "
                 "stroke-width: 1; stroke-dasharray: 4 3; }")
    lines.append(".label-alt { font-size: 9px; font-style: italic; "
                 "fill: var(--muted); }")
    lines.append(".ping { fill: var(--accent); }")
    for s in flow_["steps"]:
        target = channels.get(s["id"])
        if not target or s["kind"] != "poll" or not s["seconds"]:
            continue
        x2 = lane_x[target] + lane_w[target] / 2.0
        duration = fnum(max(s["seconds"] * scale, MIN_BAR_SECONDS))
        lines.append("@keyframes seq-ping-%s { from { cx: %s; } "
                     "to { cx: %s; } }" % (s["id"], fnum(abgal_cx), fnum(x2)))
        lines.append("#seq-ping-%s { animation: seq-ping-%s %ss ease-in-out "
                     "infinite alternate; }" % (s["id"], s["id"], duration))
    lines.append("</style>")
    return "\n".join(lines)


# -------------------------------------------------------------------- output


def _document(flow_, palette, body, layout, aria_label, extra_style=""):
    style = css_for(palette, flow_)
    if extra_style:
        # A second <style> block, appended rather than merged into
        # css_for's: only a renderer that built one (today, swimlane)
        # ever passes it, so the other three diagrams are unaffected.
        style = style + "\n" + extra_style
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %s %s" '
        'width="%s" height="%s" role="img" '
        'aria-label="%s">\n'
        '%s\n'
        '%s\n'
        '</svg>\n'
        % (fnum(layout["width"]), fnum(layout["height"]),
           fnum(layout["width"]), fnum(layout["height"]), _esc(aria_label),
           style, body)
    )


def outputs():
    """Every diagram this script writes, as (path, svg text) pairs.

    All nine diagrams this file was built for: stop-ladder,
    pieces-topology, create-flow, the FLOW_START trio (start-states,
    start-swimlane, start-sequence), watch-states, the README lifecycle
    and ports-scale, each in both palettes. A future diagram only needs
    its own FLOW_* constant and two more yields here.
    """
    stop_layout = _layout_stairs(FLOW_STOP)
    stop_body = draw_stairs(FLOW_STOP)
    for palette in ("light", "dark"):
        yield ("docs/img/stop-ladder-%s.svg" % palette,
              _document(FLOW_STOP, palette, stop_body, stop_layout,
                        "Escalation ladder for abgal stop"))

    pieces_layout = _layout_topology(FLOW_PIECES)
    pieces_body = draw_topology(FLOW_PIECES)
    for palette in ("light", "dark"):
        yield ("docs/img/pieces-topology-%s.svg" % palette,
              _document(FLOW_PIECES, palette, pieces_body, pieces_layout,
                        "The pieces of AbGal and how they relate"))

    create_layout = _layout_linear(FLOW_CREATE)
    create_body = draw_linear(FLOW_CREATE)
    create_style = _linear_extra_css()
    for palette in ("light", "dark"):
        yield ("docs/img/create-flow-%s.svg" % palette,
              _document(FLOW_CREATE, palette, create_body, create_layout,
                        "The nine steps of abgal create", create_style))

    start_layout = _layout(FLOW_START)
    start_body = draw_states(FLOW_START)
    for palette in ("light", "dark"):
        yield ("docs/img/start-states-%s.svg" % palette,
              _document(FLOW_START, palette, start_body, start_layout,
                        "States abgal start moves a guest through"))

    swim_layout = _layout_swimlane(FLOW_START)
    swim_body = draw_swimlane(FLOW_START, START_CHANNELS)
    swim_style = _swimlane_extra_css(FLOW_START, START_CHANNELS, swim_layout)
    for palette in ("light", "dark"):
        yield ("docs/img/start-swimlane-%s.svg" % palette,
              _document(FLOW_START, palette, swim_body, swim_layout,
                        "Swimlane view of abgal start", swim_style))

    seq_layout = _layout_sequence(FLOW_START)
    seq_body = draw_sequence(FLOW_START, START_CHANNELS)
    seq_style = _sequence_extra_css(FLOW_START, START_CHANNELS, seq_layout)
    for palette in ("light", "dark"):
        yield ("docs/img/start-sequence-%s.svg" % palette,
              _document(FLOW_START, palette, seq_body, seq_layout,
                        "Sequence diagram of abgal start",
                        seq_style))

    watch_layout = _layout(FLOW_WATCH)
    watch_body = draw_states(FLOW_WATCH)
    for palette in ("light", "dark"):
        yield ("docs/img/watch-states-%s.svg" % palette,
              _document(FLOW_WATCH, palette, watch_body, watch_layout,
                        "States abgal watch moves through"))

    lifecycle_layout = _layout_lifecycle(FLOW_LIFECYCLE)
    lifecycle_body = draw_lifecycle(FLOW_LIFECYCLE)
    for palette in ("light", "dark"):
        yield ("docs/img/lifecycle-%s.svg" % palette,
              _document(FLOW_LIFECYCLE, palette, lifecycle_body,
                        lifecycle_layout,
                        "A guest's life, from template to deleted"))

    ports_layout = _layout_ports(FLOW_PORTS)
    ports_body = draw_ports(FLOW_PORTS)
    for palette in ("light", "dark"):
        yield ("docs/img/ports-scale-%s.svg" % palette,
              _document(FLOW_PORTS, palette, ports_body, ports_layout,
                        "How abgal start fills the 16 emulator ports"))


# --------------------------------------------------------------------- entry


def main():
    for rel_path, text in outputs():
        full = os.path.join(ROOT, *rel_path.split("/"))
        try:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as err:
            fail("%s: %s" % (rel_path, err))
    return 0


if __name__ == "__main__":
    sys.exit(main())
