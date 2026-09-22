#!/usr/bin/env bash
#
# Temperature watch. Monitors the processor package and stops the emulator,
# before the machine runs into the critical range.
#
# The thresholds are a decision from 2026-09-20 and not the values of the
# manufacturer. The chip itself reports high = 84 C and crit = 100 C.
#
#   from 88 C   warning into the log, the run continues
#   from 96 C   abort, the emulator is stopped
#
# Both are deliberately between the two values of the chip. The 88 is above
# its warning threshold, because idle in V1 already reached 86 C, without
# a single throttle event being counted. The 96 is below its critical
# value, so the watch can act before the hardware does. See finding B14.
#
# Usage:
#   bash temperature-watch.sh                 watches every emulator
#   bash temperature-watch.sh <guest>         watches only this one guest
#   ABGAL_TEMP_WARN=85 bash ...               other warning threshold
#   ABGAL_TEMP_STOP=88 bash ...               other abort value

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/env.sh"

# Without a name it watches everything. With a name only this guest, and
# that is the way once several guests run side by side: a hot package
# applies to the whole socket, but it must not clear out all runs at once.
GUEST="${1:-}"

# The process name is searched for, not the command line. "pkill -f qemu-system"
# also matches every shell whose line contains the word. On 2026-09-20 a
# test killed itself this way. The kernel truncates the name to 15 characters.
PROCESS="${ABGAL_TEMP_PROCESS:-qemu-system-x86}"

WARN="${ABGAL_TEMP_WARN:-88}"
STOP="${ABGAL_TEMP_STOP:-96}"

# A threshold that is meant to trigger needs sampling that is fast enough.
# A case without a screen gains double digit Kelvin in fifteen seconds, and
# in that gap the abort value would already be exceeded.
INTERVAL="${ABGAL_TEMP_INTERVAL:-2}"
GRACE="${ABGAL_TEMP_GRACE:-20}"
# One log per guest. A single shared file would interleave the lines of
# several guests and lose the one thing the log is for, namely which run got
# hot. A watch without a guest name watches all of them and writes one level
# up, where no guest folder can ever land.
if [ -n "$GUEST" ]; then
  LOG="${ABGAL_TEMP_LOG:-$ABGAL_HOME/logs/$GUEST/watch.log}"
else
  LOG="${ABGAL_TEMP_LOG:-$ABGAL_HOME/logs/watch.log}"
fi

mkdir -p "$(dirname "$LOG")"

# The previous run is kept as .1 and the one before that is dropped. Two
# generations answer the only question asked after an abort, namely whether
# the run before it was already running hot.
if [ -f "$LOG" ]; then
  mv -f "$LOG" "$LOG.1"
fi

note() {
  printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" | tee -a "$LOG"
}

# The zone is determined once via its type file. A glob over all zones
# would also match acpitz, which does not deliver a usable value on this
# hardware.
ZONE=""
for z in /sys/class/thermal/thermal_zone*; do
  [ -r "$z/type" ] || continue
  if [ "$(cat "$z/type" 2>/dev/null)" = "x86_pkg_temp" ]; then
    ZONE="$z/temp"
    break
  fi
done

# First the file, then sensors. The file costs no subprocess and has no
# output format that can change. Both paths checked against each other on
# 2026-09-20, they agree except for rounding.
temperature() {
  local t=""
  if [ -n "$ZONE" ] && [ -r "$ZONE" ]; then
    t=$(( $(cat "$ZONE" 2>/dev/null || echo 0) / 1000 ))
    [ "$t" = "0" ] && t=""
  fi
  if [ -z "$t" ]; then
    t="$(sensors 2>/dev/null | awk '/Package id 0/{gsub(/[+C]/,"",$4); print int($4); exit}')"
  fi
  echo "${t:-}"
}

# The PIDs that are watched. Without a name all of them, with a name only
# those whose command line runs exactly this guest.
emulator_pids() {
  local pid
  for pid in $(pgrep -x "$PROCESS" 2>/dev/null); do
    if [ -z "$GUEST" ]; then
      echo "$pid"
    elif tr '\0' '\n' < "/proc/$pid/cmdline" 2>/dev/null | grep -qx -- "$GUEST"; then
      echo "$pid"
    fi
  done
}

# First the orderly path via adb, then SIGTERM, only lastly SIGKILL. A hard
# kill can damage the device image, and rebuilding it costs more than the
# event the watch was meant to prevent.
stop_emulator() {
  local pid port
  for pid in $(emulator_pids); do
    port="$(tr '\0' '\n' < "/proc/$pid/cmdline" 2>/dev/null | grep -A1 -x -- '-port' | tail -1)"
    if [ -n "$port" ]; then
      note "Stopping port $port in an orderly way, via adb."
      adb -s "emulator-$port" emu kill > /dev/null 2>&1
    fi
  done
  sleep "$GRACE"

  for pid in $(emulator_pids); do
    note "Not responding, SIGTERM to $pid."
    kill "$pid" 2>/dev/null
  done
  sleep 10

  for pid in $(emulator_pids); do
    note "SIGKILL to $pid. This device's image may be damaged."
    kill -9 "$pid" 2>/dev/null
  done
}

note "Watch on. Warning from ${WARN} C, abort from ${STOP} C, every ${INTERVAL} s.${GUEST:+ Guest: $GUEST.}"
[ -z "$ZONE" ] && note "Note: no x86_pkg_temp zone found, only sensors counts."

if [ -z "$(temperature)" ]; then
  note "WATCH ABORTED: no temperature measurable. Neither sensors nor x86_pkg_temp."
  exit 2
fi

# At startup, alongside the emulator, the qemu process is not there yet.
# Without this warmup time the watch would exit again immediately.
waittime=0
while [ -z "$(emulator_pids)" ]; do
  if [ "$waittime" -ge "${ABGAL_TEMP_WARMUP:-120}" ]; then
    note "After ${waittime} s no emulator has appeared. Watch off."
    exit 0
  fi
  waittime=$((waittime + 5))
  sleep 5
done

warned=0
highest=0
blind=0

while true; do
  if [ -z "$(emulator_pids)" ]; then
    note "No emulator left. Watch off. Highest value was ${highest} C."
    exit 0
  fi

  T="$(temperature)"

  # A watch that no longer measures anything and keeps running anyway
  # fakes safety. After four failed attempts it exits audibly.
  if [ -z "$T" ]; then
    blind=$((blind + 1))
    if [ "$blind" -ge 4 ]; then
      note "WATCH ABORTED: no temperature measurable four times in a row. No longer watching."
      exit 2
    fi
    note "Warning: temperature not readable (${blind} of 4)."
    sleep "$INTERVAL"
    continue
  fi
  blind=0

  [ "$T" -gt "$highest" ] && highest="$T"

  if [ "$T" -ge "$STOP" ]; then
    note "ABORT at ${T} C, threshold ${STOP}. Stopping the emulator."
    stop_emulator
    note "Stopped. Highest value was ${highest} C."
    exit 1
  fi

  if [ "$T" -ge "$WARN" ]; then
    # Only report when crossing the threshold, not on every measurement again.
    if [ "$warned" = "0" ]; then
      note "WARNING at ${T} C, threshold ${WARN}. Run continues."
      warned=1
    fi
  elif [ "$warned" = "1" ] && [ "$T" -lt $((WARN - 3)) ]; then
    # All clear only three degrees below the threshold, otherwise the message flaps.
    note "All clear at ${T} C."
    warned=0
  fi

  sleep "$INTERVAL"
done
