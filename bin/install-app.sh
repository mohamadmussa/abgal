#!/usr/bin/env bash
#
# Installs a fixed set of package files onto a device.
#
# This is the half that runs in CI. No store, no login, no network: only
# files whose version is in app.conf. That way every run installs the same
# test subject, today and in three months. See finding B15.
#
# Usage:
#   bash install-app.sh                          shows the existing sets
#   bash install-app.sh rig-01                   the version from app.conf
#   bash install-app.sh rig-01 1.0.9             exactly this version
#   ABGAL_ABI=arm64-v8a bash ...                 different architecture, e.g. for the S21

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/env.sh"

TARGET_BASE="${ABGAL_APP_DIR:-$ABGAL_HOME/apk}"

list_sets() {
  local d
  for d in "$TARGET_BASE"/splits-v*/; do
    [ -d "$d" ] || continue
    printf '  %-28s %s\n' "$(basename "$d")" \
      "$(grep -m1 '^Fetched at' "$d/PROVENANCE.txt" 2>/dev/null || echo 'no PROVENANCE.txt')"
  done
}

if [ $# -eq 0 ]; then
  echo "Usage: bash install-app.sh <guest|id> [version]"
  echo
  echo "Sets under $TARGET_BASE:"
  list_sets
  exit 0
fi

# Which app this run installs. No default on purpose: AbGal is a tool, not
# a test suite for one app. Set it in env.local.sh, which is never
# committed, or export it before the call.
PACKAGE="${ABGAL_PACKAGE:-}"
if [ -z "$PACKAGE" ]; then
  echo "ERROR: ABGAL_PACKAGE is not set." >&2
  echo "Example: export ABGAL_PACKAGE=com.example.app" >&2
  exit 1
fi

# --- Determine device ----------------------------------------------------------

DEVICE="$1"
if ! adb devices | grep -qw "^$DEVICE"; then
  # Not an id already on the adb list, so try it as a guest name. A
  # template no longer maps to a port, only a running guest does, and
  # "abgal status" is the one place that mapping is kept.
  read -r serial template <<< "$("$ABGAL_HOME/abgal" status --json | python3 -c '
import json, sys
for g in json.load(sys.stdin)["guests"]:
    if g["name"] == sys.argv[1]:
        print(g["serial"] or "-", g["template"])
        break
' "$DEVICE")"
  if [ -n "${serial:-}" ] && [ "$serial" != "-" ]; then
    if grep -qE "^[[:space:]]*${template}[[:space:]]*\|[^|]*\|[^|]*\|[[:space:]]*google_apis_playstore[[:space:]]*\|" \
         "$ABGAL_HOME/devices.conf"; then
      echo "Note: $DEVICE runs google_apis_playstore. The test rig is the one without."
    fi
    DEVICE="$serial"
  fi
fi

if ! adb devices | grep -qw "^$DEVICE"; then
  echo "ERROR: $DEVICE is not connected." >&2
  adb devices >&2
  exit 1
fi

# --- Determine version --------------------------------------------------------

if [ -n "${2:-}" ]; then
  VERSION="$2"
  ABI="${ABGAL_ABI:-x86_64}"
  source="command line"
else
  if [ ! -f "$ABGAL_HOME/app.conf" ]; then
    echo "ERROR: $ABGAL_HOME/app.conf does not exist." >&2
    echo "It is gitignored, a fresh clone starts without it. Create one," >&2
    echo "see the comment in app.conf, or pass a version on the command line." >&2
    exit 1
  fi
  line="$(grep -v '^[[:space:]]*#' "$ABGAL_HOME/app.conf" \
           | grep -v '^[[:space:]]*$' | head -1)"
  VERSION="$(echo "${line%%|*}" | tr -d ' ')"
  ABI="${ABGAL_ABI:-$(echo "${line##*|}" | tr -d ' ')}"
  source="app.conf"
fi

SET="$TARGET_BASE/splits-v$VERSION-$ABI"

echo "Device    $DEVICE"
echo "Version   $VERSION ($ABI), from $source"
echo "Set       $SET"
echo

if [ ! -d "$SET" ]; then
  echo "ERROR: this set does not exist." >&2
  echo "Available:" >&2
  list_sets >&2
  echo >&2
  echo "Fetch with: bash fetch-app.sh store-01" >&2
  exit 1
fi

mapfile -t FILES < <(find "$SET" -maxdepth 1 -name '*.apk' | sort)

if [ "${#FILES[@]}" -eq 0 ] || [ ! -f "$SET/base.apk" ]; then
  echo "ERROR: the set does not contain a base.apk." >&2
  exit 1
fi

# --- Install --------------------------------------------------------------
#
# Remove first, then install. Installing over an existing version inherits
# its data, so the run would not start in the same state.

if adb -s "$DEVICE" shell pm path "$PACKAGE" 2>/dev/null | grep -q package:; then
  echo "Removing the existing installation."
  adb -s "$DEVICE" uninstall "$PACKAGE" > /dev/null
fi

echo "Installing ${#FILES[@]} files."
adb -s "$DEVICE" install-multiple "${FILES[@]}"

# --- Cross check ---------------------------------------------------------------

echo
dumpsys="$(adb -s "$DEVICE" shell dumpsys package "$PACKAGE" 2>/dev/null || true)"
read_field() { echo "$dumpsys" | grep -oE "$1=[^ ]+" | head -1 | cut -d= -f2-; }

actual_version="$(read_field versionName)"
actual_abi="$(read_field primaryCpuAbi)"

echo "Cross check on the device:"
printf '  %-14s %s\n' "versionName" "${actual_version:-nothing}"
printf '  %-14s %s\n' "primaryCpuAbi" "${actual_abi:-nothing}"

if [ "$actual_version" != "$VERSION" ]; then
  echo
  echo "ERROR: installed is $actual_version, wanted was $VERSION." >&2
  exit 1
fi

echo
echo "$PACKAGE $actual_version is on $DEVICE."
