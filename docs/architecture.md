# Architecture

[README.md](../README.md) gets a guest from a fresh clone to a running
emulator in four commands. [How it works](how-it-works.md) follows one guest
through the file or function that does each step. Neither shows the whole
shape at once: which pieces wait on which, in what order, and what a wait
looks like next to a step that just runs. This page does, with the same
generated diagrams [CONTRIBUTING.md](../CONTRIBUTING.md) asks for wherever a
flow depends on waiting, polling, or more than one actor at the same time.

Three readers might open this page. Someone running AbGal, who wants to see
why a start takes as long as it does, or what a failure actually looked like
on the way there. Someone sending a pull request, who needs to know which
file a change belongs to before writing it. Someone deciding whether to
adopt AbGal at all, who wants the shape of the thing before reading a line
of Python.

## The whole shape

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/pieces-topology-dark.svg">
  <img src="img/pieces-topology-light.svg" alt="A hub and spoke diagram. abgal sits in the center. It reads devices.conf and versions.conf, links devices.xml, creates avd/, writes logs/, and fetches into sdk/ and android-home/. bin/env.sh sits apart, unconnected, labeled not read by abgal.">
</picture>

`abgal` is the one file that touches everything else in the clone. It reads
`devices.conf` and `versions.conf`, links `devices.xml` into place, creates
`avd/`, writes `logs/`, and fetches the SDK into `sdk/` and `android-home/`.
`bin/env.sh` is the one deliberate exception: it sets the SDK paths for a
shell of your own, and `abgal` never reads it, because `abgal` sets its own
environment internally. The rest of this page follows what happens inside
that one file, one command at a time.

## A guest's lifecycle

Every command moves a guest between the same small set of states, from a
line in `devices.conf` through `create`, `start`, running, and back to
stopped again, by either `abgal stop` or the temperature watch at 96 C.
README.md already draws this as a state diagram, see
[Lifecycle](../README.md#lifecycle), so it is not repeated here.
`docs/README.md` carries a second, slightly different copy of the same
diagram, missing the memory refusal and the exact temperature. That is a
small, existing inconsistency between two files, left as it is here rather
than fixed as a side effect of this page.

## Creating a guest

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/create-flow-dark.svg">
  <img src="img/create-flow-light.svg" alt="Nine steps in a column for abgal create: refuse an invalid name; check the screen is listed by avdmanager; fetch the system image if missing; refuse a running guest; delete and recreate, or keep the disk; create avd/ and call avdmanager create avd; write abgal-template; pin five values in config.ini, a sixth for the store template; read config.ini back and compare thirteen values against what was asked for.">
</picture>

`abgal create` takes nine steps for every guest, ending with `create`
reading `config.ini` back and checking thirteen values against what it
asked `avdmanager` for, because `avdmanager` drops or overrides several of
them without a message. See [Templates](templates.md) for what the
thirteen values are and how to add a template of your own. The diagram is
static, not animated, because `create_one()` has no measured wait anywhere
in it: every step is a check, a file write, or a call to `avdmanager`, none
of them a poll or a sleep, so there is nothing to show passing.

## Starting a guest

`abgal start` is the one flow in AbGal most worth seeing from more than one
angle, because it is the one place where several things wait on each
other: the emulator process itself, adb polling for its console, a
temperature watch subprocess, and a second poll for the boot to finish.
Three diagrams show the same real flow three different ways.

Timeline lays the same real waits out on one shared axis, one row per
actor: kernel, emulator, adb and the temperature watch. A bar is a real
wait, drawn to scale, a tick is a step that just happens with no duration
of its own. adb's row carries two bars, the console poll and the boot
poll, so the same channel used twice reads as two bars in sequence on one
row, not one wire pulsing twice.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/start-timeline-dark.svg">
  <img src="img/start-timeline-light.svg" alt="Four rows, kernel, emulator, adb and the temperature watch, on a shared time axis. A tick on kernel for the preflight check, a tick on emulator for launch, a bar on adb up to 300 seconds for the console poll, a tick then a bar on the temperature watch for starting it and the two second settle wait, and a second bar on adb up to 300 seconds for the boot poll.">
</picture>

Swimlane lays the same real sequence out against a shared time axis, one
column per actor, so the two adb moments become two separate rows instead
of two pulses sharing one wire.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/start-swimlane-dark.svg">
  <img src="img/start-swimlane-light.svg" alt="Five columns, abgal start, kernel, emulator, adb and the temperature watch, with abgal start's own steps running down its own column and a line crossing to whichever lane that step talks to, in real order from top to bottom.">
</picture>

States shows where the flow can end: ready, or one of three distinct
failure terminals, the console never answered, the temperature watch died
at once, or the guest never finished booting, each carrying the real
message `start` prints for that case.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/start-states-dark.svg">
  <img src="img/start-states-light.svg" alt="A column of states for abgal start: the memory and running checks, launching the emulator, polling adb for the console up to the timeout, starting the temperature watch and checking it survived two seconds, polling adb for the completed boot, and four terminals, ready or one of three distinct failures.">
</picture>

## Ports, and how many guests run at once

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/ports-scale-dark.svg">
  <img src="img/ports-scale-light.svg" alt="A row of the sixteen emulator ports from 5554 to 5584. Below it, an illustrative example: thirteen already busy, a guest's automatic pick taking the first free port, an explicit --port claiming one directly, a second automatic pick taking what is left, and a further guest's automatic pick finding nothing free.">
</picture>

`abgal` itself keeps no record of which port a guest uses. Without
`--port`, the choice is entirely the emulator binary's own logic, it
searches upward from 5554 for a free pair and takes it, and `abgal` only
prints "chosen by the emulator" for that case, see
[Ports](how-it-works.md#ports). An explicit `--port` must be even, from
5554 to 5584, sixteen values in all, `abgal`'s own count comment calls the
same range "the sixteen ports adb offers", because that is the range a
guest's adb serial, `emulator-<port>`, is parsed back out of. A port
outside it is a guest adb genuinely cannot find. The sixteen slots in the
diagram are that real rule. The fill sequence below them is illustrative,
not a measured run: which of the sixteen ports happens to be busy at any
moment is runtime state, not a value `abgal` tracks anywhere.

More than sixteen guests at once has no solution in AbGal today. `start`
has no implicit "all guests", so running that many would already have to
be asked for one guest at a time, and when it is, a seventeenth guest's
automatic pick finds nothing free: `abgal` has no code path for that case,
and the emulator process itself would simply fail to start, with whatever
generic error it reports for a start with no port available. That is a
deliberately open question, left for a later issue, not part of this
document.

## Stopping a guest

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/stop-ladder-dark.svg">
  <img src="img/stop-ladder-light.svg" alt="An escalation ladder for abgal stop: adb emu kill, then a poll for up to the --grace default of 20 seconds, then, if still running, SIGTERM and a fixed 10 second wait, then SIGKILL and another fixed 10 second wait, ending in stopped or, if nothing worked, still running.">
</picture>

`abgal stop` tries the orderly way first, because a hard kill can damage a
guest's disk. It sends `adb emu kill` and polls once a second for up to
the `--grace` default of 20 seconds. If the guest is still running, it
sends `SIGTERM` and waits a fixed 10 seconds, not scaled by `--grace`, then
checks again. If it is still running after that, `SIGKILL` and another
fixed 10 second wait. If the guest survives even that, `stop` says so and
ends with exit code 1: there is nothing else the program can do.

## Temperature watch

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/watch-states-dark.svg">
  <img src="img/watch-states-light.svg" alt="A column of states for abgal watch: an initial temperature reading that must succeed once, a warmup poll for a guest to appear, then an unbounded main poll. Four terminals: no temperature measurable at all, no guest appeared during warmup, no guests left to watch, or the temperature reaching the stop threshold, which hands off to the same stop cascade abgal stop uses. An unreadable sensor during the main loop retries, stated on the diagram as eventually aborting after four misses running.">
</picture>

This is the fuller, animated version of the flowchart already in
[Temperature watch](how-it-works.md#temperature-watch), not a contradiction
of it: the same warning at 88 C and abort at 96 C, drawn here together with
the warmup wait and the main poll's own lack of a limit. The diagram shows
four distinct endings. Two are clean exits, no guest appeared during
warmup, or no guests are left to watch. One is a hard failure at the very
start, if neither the thermal zone nor `sensors` can measure anything at
all. The temperature reaching the stop threshold is not drawn as its own
cascade a second time, it hands off to the same `stop_one()` escalation
the stop-ladder diagram above already draws in full. A sensor that stays
unreadable during the main loop also aborts, after four misses running,
shown on the diagram as the real consequence stated on that step rather
than as a fifth separate ending.

## For contributors

Every box in the diagrams on this page is a real file or a real function,
not an illustration of one, except where a diagram says otherwise on its
own face. `abgal` is the one Python file behind every one of them;
`devices.conf`, `devices.xml` and `versions.conf` are the files the whole
shape diagram above names; a new screen or template belongs in
[Templates](templates.md), which this page does not repeat. The diagrams
themselves are generated by `tools/gen-architecture-diagrams.py`, not drawn
by hand, so a change to `abgal` that changes one of these flows means
updating that script and regenerating the SVGs under `docs/img/`, not
editing an image directly. The house rules for branches, commits, and the
privacy gate are in [CONTRIBUTING.md](../CONTRIBUTING.md), which this page
also does not repeat.

## Deciding whether to adopt it

AbGal is one Python file using only the standard library. There is nothing
to install and nothing to package, the file is the program. Every guest
comes from a line in `devices.conf`, so the fleet a team runs is a text
file checked into git, not a set of clicks remembered by one person in a
device manager, and a second machine reaches the same fleet from the same
clone. That is what the diagrams on this page show at the mechanism level:
adopting AbGal means adopting a text file as the source of truth for the
emulators a project runs, reproducible on any machine that clones it.
