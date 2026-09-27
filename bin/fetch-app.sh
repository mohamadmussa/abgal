#!/usr/bin/env bash
#
# Fetches the installed package files of the app from a device and stores
# them as a fixed set.
#
# The store only runs here, not in CI. This split is the decision from
# 2026-09-20: the profile with the store fetches a new version, this script
# pulls it out, and every repeatable run afterward only installs files. A
# run that pulls from the store at runtime would get a different version
# tomorrow and would no longer be a real test. See finding B15.
#
# Usage:
#   bash fetch-app.sh                          takes the single connected device
#   bash fetch-app.sh store-01                 takes this guest's connection
#   bash fetch-app.sh emulator-5556            takes this id unchanged
#   ABGAL_APP_REFRESH=1 bash fetch-app.sh ...  replace the existing set

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/env.sh"

# Which app this run installs. No default on purpose: AbGal is a tool, not
# a test suite for one app. Set it in env.local.sh, which is never
# committed, or export it before the call.
PACKAGE="${ABGAL_PACKAGE:-}"
if [ -z "$PACKAGE" ]; then
  echo "ERROR: ABGAL_PACKAGE is not set." >&2
  echo "Example: export ABGAL_PACKAGE=com.example.app" >&2
  exit 1
fi

TARGET_BASE="${ABGAL_APP_DIR:-$ABGAL_HOME/apk}"

# --- Determine device ----------------------------------------------------------

DEVICE="${1:-}"

if [ -z "$DEVICE" ]; then
  count="$(adb devices | grep -cw 'device$' || true)"
  if [ "$count" != "1" ]; then
    echo "ERROR: $count devices connected. Name one, or a guest." >&2
    adb devices >&2
    exit 1
  fi
  DEVICE="$(adb devices | awk '/\tdevice$/{print $1; exit}')"
elif ! adb devices | grep -qw "^$DEVICE"; then
  # Not an id already on the adb list, so try it as a guest name. A
  # template no longer maps to a port, only a running guest does, and
  # "abgal status" is the one place that mapping is kept.
  serial="$("$ABGAL_HOME/abgal" status --json | python3 -c '
import json, sys
for g in json.load(sys.stdin)["guests"]:
    if g["name"] == sys.argv[1] and g["serial"]:
        print(g["serial"])
        break
' "$DEVICE")"
  [ -n "$serial" ] && DEVICE="$serial"
fi

if ! adb devices | grep -qw "^$DEVICE"; then
  echo "ERROR: $DEVICE is not connected." >&2
  adb devices >&2
  exit 1
fi

echo "Device        $DEVICE"
echo "Package       $PACKAGE"

# --- Read version and architecture -----------------------------------------------

dumpsys="$(adb -s "$DEVICE" shell dumpsys package "$PACKAGE" 2>/dev/null || true)"

if [ -z "$dumpsys" ]; then
  echo "ERROR: $PACKAGE is not installed on $DEVICE." >&2
  exit 1
fi

read_field() { echo "$dumpsys" | grep -oE "$1=[^ ]+" | head -1 | cut -d= -f2-; }

VERSION="$(read_field versionName)"
BUILD_NUMBER="$(read_field versionCode)"
ABI="$(read_field primaryCpuAbi)"
# Written as a shortcut with && this would abort the whole run under
# "set -e" as soon as the architecture is set. Spelled out instead.
if [ -z "$ABI" ] || [ "$ABI" = "null" ]; then
  ABI="no-abi"
fi

echo "Version       $VERSION (versionCode $BUILD_NUMBER)"
echo "Architecture  $ABI"
echo

TARGET="$TARGET_BASE/splits-v$VERSION-$ABI"

if [ -d "$TARGET" ] && [ "${ABGAL_APP_REFRESH:-0}" != "1" ]; then
  echo "This set already exists: $TARGET"
  echo "Set ABGAL_APP_REFRESH=1 to replace it."
  exit 0
fi

# --- Fetch files ------------------------------------------------------------

mapfile -t PATHS < <(adb -s "$DEVICE" shell pm path "$PACKAGE" \
                     | tr -d '\r' | sed -n 's/^package://p')

if [ "${#PATHS[@]}" -eq 0 ]; then
  echo "ERROR: pm path reported no file." >&2
  exit 1
fi

rm -rf "$TARGET"
mkdir -p "$TARGET"

echo "${#PATHS[@]} files:"
for p in "${PATHS[@]}"; do
  adb -s "$DEVICE" pull "$p" "$TARGET/" > /dev/null
  printf '  %-34s %s\n' "$(basename "$p")" \
    "$(du -h "$TARGET/$(basename "$p")" | cut -f1)"
done

# --- Cross check ---------------------------------------------------------------
#
# Without it we would only know that the script ran. An aborted pull leaves
# a file of length zero, and that would otherwise only surface later, during
# install.

echo
error=0
fetched="$(find "$TARGET" -maxdepth 1 -name '*.apk' | wc -l)"

[ "$fetched" = "${#PATHS[@]}" ] || {
  echo "ERROR: ${#PATHS[@]} reported, $fetched fetched." >&2; error=1; }

while IFS= read -r f; do
  [ -s "$f" ] || { echo "ERROR: $(basename "$f") is empty." >&2; error=1; }
done < <(find "$TARGET" -maxdepth 1 -name '*.apk')

[ -f "$TARGET/base.apk" ] || { echo "ERROR: base.apk is missing." >&2; error=1; }

if [ "$error" != "0" ]; then
  echo "The set is incomplete and not usable." >&2
  exit 1
fi

# --- Record provenance ------------------------------------------------------
#
# A set of binary files without provenance is worthless in three months.
# The repo does not take in the files, but this note still answers where
# they came from.

{
  echo "Package      $PACKAGE"
  echo "Version      $VERSION (versionCode $BUILD_NUMBER)"
  echo "Architecture $ABI"
  echo "Fetched at   $(date '+%d.%m.%Y %H:%M:%S %Z')"
  echo "From         $DEVICE"
  echo "With         $(basename "${BASH_SOURCE[0]}")"
  echo
  echo "Files:"
  (cd "$TARGET" && ls -l *.apk | awk '{printf "  %-34s %s\n", $9, $5}')
} > "$TARGET/PROVENANCE.txt"

echo "Set complete: $TARGET"
echo
echo "Install on the test rig:"
echo "  adb -s emulator-5554 install-multiple $TARGET/*.apk"
