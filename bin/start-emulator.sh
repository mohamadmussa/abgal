#!/usr/bin/env bash
#
# Starts one guest, without a screen.
#
# This takes a guest, not a template. A template describes a class of device
# and has no state; a guest has a disk, a name and, while it runs, a port.
# Everything this script needs it reads from the guest itself, so a guest
# created months ago still starts the way it was built.
#
# Usage:
#   bash start-emulator.sh                         shows the guests on disk
#   bash start-emulator.sh <guest>                 the emulator picks its port
#   ABGAL_PORT=5556 bash start-emulator.sh <g>     a port of your choosing
#   ABGAL_GPU=host bash start-emulator.sh <g>      with a graphics card
#   ABGAL_LOCALE=ar-SA bash start-emulator.sh <g>  a different system language
#   ABGAL_WIPE=1 bash start-emulator.sh <g>        wipe user data, first boot again
#
# Normally called through "abgal start", which handles logs and locking.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/env.sh"

# Lists what is actually on disk, with the template each guest came from.
# Templates are deliberately not listed here: you cannot start a template.
list_guests() {
  local folder guest template found=0
  for folder in "$ANDROID_AVD_HOME"/*.avd; do
    [ -d "$folder" ] || continue
    guest="$(basename "$folder" .avd)"
    template="$(cat "$folder/abgal-template" 2>/dev/null || echo "unknown")"
    printf "  %-24s from %s\n" "$guest" "$template"
    found=1
  done
  if [ "$found" = "0" ]; then
    echo "  none yet. Create one with: bash create-avd.sh <template> <guest>"
  fi
}

# config.ini is written twice in two styles: avdmanager writes "key=value",
# the emulator rewrites the same line as "key = value" at every start. Both
# have to be read here, so the spacing is part of the pattern.
ini_value() {
  sed -n -E "s/^$2[[:space:]]*=[[:space:]]*(.*)$/\1/p" "$1" | head -1
}

if [ $# -eq 0 ]; then
  echo "Usage: bash start-emulator.sh <guest>"
  echo
  echo "Guests on disk:"
  list_guests
  exit 0
fi

GUEST="$1"
CONFIG="$ANDROID_AVD_HOME/$GUEST.avd/config.ini"

if [ ! -f "$CONFIG" ]; then
  echo "ERROR: there is no guest called '$GUEST'." >&2
  echo "Guests on disk:" >&2
  list_guests >&2
  exit 1
fi

# The emulator refuses a second instance of the same guest itself, but only
# after it has already started, and by then this script has started a second
# temperature watch that writes into the same log. Measured on 2026-09-22:
# two watches, one log, the first generation rotated out from under the other.
# Checking here stops the whole sequence before anything is started.
for pid in $(pgrep -x qemu-system-x86 2>/dev/null); do
  if tr '\0' '\n' < "/proc/$pid/cmdline" 2>/dev/null | grep -qx -- "$GUEST"; then
    echo "ERROR: $GUEST is already running as pid $pid." >&2
    exit 1
  fi
done

GPU="${ABGAL_GPU:-software}"
LOCALE="${ABGAL_LOCALE:-en-US}"

ARGS=(
  "$ANDROID_HOME/emulator/emulator"
  -avd "$GUEST"
)

# Without -port the emulator searches upwards from 5554 in steps of two and
# binds the first free pair itself, in one step. Any check we could do here
# would be a separate step before the start, and the port could be taken in
# between. So the default is to say nothing and let it choose.
if [ -n "${ABGAL_PORT:-}" ]; then
  PORT="$ABGAL_PORT"
  case "$PORT" in
    ''|*[!0-9]*) echo "ERROR: ABGAL_PORT='$PORT' is not a number." >&2; exit 1 ;;
  esac
  # The emulator's own rule, from "emulator -help-port": an even number from
  # 5554 to 5584, because the next number up is taken by adb. Outside that
  # range adb no longer finds the guest on its own.
  if [ "$PORT" -lt 5554 ] || [ "$PORT" -gt 5584 ] || [ $((PORT % 2)) -ne 0 ]; then
    echo "ERROR: $PORT is not usable. Even numbers from 5554 to 5584 only." >&2
    exit 1
  fi
  ARGS+=(-port "$PORT")
else
  PORT="chosen by the emulator"
fi

ARGS+=(
  -no-window            # no screen on this machine
  -no-audio             # no audio device present, one less source of errors
  -no-boot-anim
  # Without this flag the emulator warns on every start. Its own message says
  # a future version turns this into a blocking prompt, which would stall a
  # CI run that nobody is sitting at.
  -no-metrics
  -gpu "$GPU"
  -no-snapshot-load     # every run starts cold, or it hangs on the previous one
  -no-snapshot-save
  -prop "persist.sys.locale=$LOCALE"
  -prop "persist.sys.timezone=Europe/Berlin"
)

if [ "${ABGAL_WIPE:-0}" = "1" ]; then
  ARGS+=(-wipe-data)
fi

echo "Guest     $GUEST"
echo "Template  $(cat "$ANDROID_AVD_HOME/$GUEST.avd/abgal-template" 2>/dev/null || echo unknown)"
echo "Device    $(ini_value "$CONFIG" hw.device.name), $(ini_value "$CONFIG" tag.id)"
echo "Screen    $(ini_value "$CONFIG" hw.lcd.width)x$(ini_value "$CONFIG" hw.lcd.height) at $(ini_value "$CONFIG" hw.lcd.density) dpi"
echo "Memory    $(ini_value "$CONFIG" hw.ramSize) MB"
echo "Graphics  $GPU"
echo "Language  $LOCALE"
echo "Port      $PORT"
echo

# The watch runs alongside the emulator and stops it before the machine
# reaches the critical range. Can be disabled with ABGAL_TEMP_WATCH=0, for
# example on a machine without readable sensors.
if [ "${ABGAL_TEMP_WATCH:-1}" = "1" ]; then
  setsid bash "$HERE/temperature-watch.sh" "$GUEST" > /dev/null 2>&1 &
  echo "Temperature watch running. Log: $ABGAL_HOME/logs/$GUEST/watch.log"
  echo
fi

# The kvm group is in the group database but not in a session that logged in
# before the usermod. "sg kvm" bridges that without a fresh login.
if id -nG | tr ' ' '\n' | grep -qx kvm; then
  exec "${ARGS[@]}"
else
  echo "Note: the running session does not know the kvm group, starting via sg kvm."
  exec sg kvm -c "$(printf '%q ' "${ARGS[@]}")"
fi
