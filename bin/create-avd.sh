#!/usr/bin/env bash
#
# Creates one guest from a template in devices.conf and pins the values that
# the tool itself sets or overwrites.
#
# Template and guest are two different names. The template describes a class
# of device and is reused; the guest is one virtual machine with its own disk
# and its own name. Many guests share one template and one system image.
#
# Why this script exists and not just devices.xml: measured on 2026-09-20,
# avdmanager silently dropped three values from the device description and
# set three more so that a run was not repeatable.
#
# Usage:
#   bash create-avd.sh                             shows the templates
#   bash create-avd.sh <template>                  guest named after the template
#   bash create-avd.sh <template> <guest>          guest with its own name
#   ABGAL_AVD_RECREATE=1 bash create-avd.sh ...    delete and recreate
#
# Normally called through "abgal create", which handles counting and
# numbering. This script always makes exactly one guest.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/env.sh"
. "$HERE/read-profile.sh"

AVDMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/avdmanager"
SDKMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"

# The device description must live where the tools read it. A symlink to the
# file in the project keeps a single source.
if [ ! -e "$HOME/.android/devices.xml" ]; then
  mkdir -p "$HOME/.android"
  ln -sfn "$ABGAL_HOME/devices.xml" "$HOME/.android/devices.xml"
  echo "Device description linked: ~/.android/devices.xml -> $ABGAL_HOME/devices.xml"
fi

# Checks whether exactly this guest is running right now. The process name is
# checked first, then the argument verbatim. "pgrep -f" would also match any
# shell that merely mentions the name, and a short name is a prefix of a
# longer one.
is_running() {
  local pid
  for pid in $(pgrep -x qemu-system-x86 2>/dev/null); do
    if tr '\0' '\n' < "/proc/$pid/cmdline" 2>/dev/null | grep -qx -- "$1"; then
      return 0
    fi
  done
  return 1
}

# avdmanager accepts a name that it cannot later find, because the name also
# becomes a directory. Checking here costs nothing and saves a guest that
# exists on disk but not in any listing.
check_name() {
  case "$1" in
    ""|*[!A-Za-z0-9._-]*)
      echo "ERROR: '$1' is not a usable guest name." >&2
      echo "Letters, digits, dot, underscore and dash only." >&2
      return 1 ;;
  esac
}

create_avd() {
  local template="$1" guest="$2"

  read_profile "$template"
  check_name "$guest"

  echo "==============================================================="
  echo "Guest     $guest"
  echo "Template  $V_NAME"
  echo "Device    $V_DEVICE"
  echo "Image     $V_IMAGE"
  echo "Memory    $V_RAM MB"
  echo "==============================================================="

  if ! "$AVDMANAGER" list device 2>/dev/null | grep -q "\"$V_DEVICE\""; then
    echo "ERROR: device $V_DEVICE is not listed in devices.xml." >&2
    return 1
  fi

  if [ ! -d "$ANDROID_HOME/system-images/android-$V_API/$V_TAG/$V_ABI" ]; then
    echo "The system image is missing. Fetching it:"
    echo "  sdkmanager \"$V_IMAGE\""
    yes | "$SDKMANAGER" "$V_IMAGE" > /dev/null
  fi

  local folder="$ANDROID_AVD_HOME/$guest.avd"
  local config="$folder/config.ini"

  # A running emulator rewrites config.ini itself at start. Whatever we write
  # now would be gone again by the next start at the latest.
  if is_running "$guest"; then
    echo "ERROR: $guest is running right now. Stop it first, or the change will be lost." >&2
    return 1
  fi

  if [ "${ABGAL_AVD_RECREATE:-0}" = "1" ] && [ -d "$folder" ]; then
    echo "Deleting existing guest $guest"
    "$AVDMANAGER" delete avd -n "$guest"
  fi

  if [ ! -d "$folder" ]; then
    echo "no" | "$AVDMANAGER" create avd -n "$guest" -k "$V_IMAGE" -d "$V_DEVICE"
  else
    echo "$guest already exists, only updating the values"
  fi

  # Which template this guest came from. config.ini is rewritten by the
  # emulator on every start, so an extra key there would not survive. A file
  # of its own does, and it is the only way a listing can name the template
  # of a guest that was created months ago.
  printf '%s\n' "$V_NAME" > "$folder/abgal-template"

  # -------------------------------------------------------------------------
  # The pinned values.
  #
  # Value                                   created  set       reason
  # hw.ramSize                              2G       from conf devices.xml is overridden here
  # hw.camera.front                         none     emulated  devices.xml describes a front camera
  # firstboot.bootFromDownloadableSnapshot  yes      no        would fetch state from the network
  # firstboot.bootFromLocalSnapshot         yes      no        a run must not depend on the previous one
  # firstboot.saveToLocalSnapshot           yes      no        same thing in the other direction
  # -------------------------------------------------------------------------

  # At start, the emulator rewrites every line as "key = value", while
  # avdmanager writes "key=value". Measured on 2026-09-20: after one start,
  # 139 of 144 lines used the other style, so normalize first and only then
  # compare, or the verification reports a false alarm.
  sed -i -E 's/^([A-Za-z0-9._]+)[[:space:]]*=[[:space:]]*/\1=/' "$config"

  echo "Updating the values:"
  # avdmanager writes "no" here even when the device is enabled in devices.xml
  # and the image includes a store. Measured on 2026-09-20, also with a
  # cleared cache.
  if [ "$V_TAG" = "google_apis_playstore" ]; then
    set_value "$config" PlayStore.enabled yes
  fi
  set_value "$config" hw.ramSize "$V_RAM"
  set_value "$config" hw.camera.front emulated
  set_value "$config" firstboot.bootFromDownloadableSnapshot no
  set_value "$config" firstboot.bootFromLocalSnapshot no
  set_value "$config" firstboot.saveToLocalSnapshot no

  verify "$config" "$guest"
}

set_value() {
  local file="$1" key="$2" value="$3" old
  if grep -q "^$key=" "$file"; then
    old="$(grep "^$key=" "$file" | head -1 | cut -d= -f2-)"
    [ "$old" = "$value" ] && return 0
    sed -i "s|^$key=.*|$key=$value|" "$file"
    echo "  $key: $old -> $value"
  else
    printf '%s=%s\n' "$key" "$value" >> "$file"
    echo "  $key: missing -> $value"
  fi
}

# Without this verification we would only know the script ran, not that it
# worked. Exactly that swallowed three values on the first attempt.
verify() {
  local config="$1" guest="$2" errors=0 line found

  # Width, height and density come from devices.xml. They are checked here
  # against the description, not a literal number, or a tablet would later
  # be checked against the phone's values.
  local width height density
  width="$(device_value "$V_DEVICE" x-dimension)"
  height="$(device_value "$V_DEVICE" y-dimension)"
  density="$(density_to_number "$(device_value "$V_DEVICE" pixel-density)")"

  # The store is the whole point of the second template. Without this line,
  # nobody would notice if avdmanager silently turned it off, for example
  # because the device is not enabled for it in devices.xml.
  local store=no
  [ "$V_TAG" = "google_apis_playstore" ] && store=yes

  local expected="abi.type=$V_ABI
PlayStore.enabled=$store
firstboot.bootFromDownloadableSnapshot=no
firstboot.bootFromLocalSnapshot=no
firstboot.saveToLocalSnapshot=no
hw.camera.front=emulated
hw.device.name=$V_DEVICE
hw.lcd.density=$density
hw.lcd.height=$height
hw.lcd.width=$width
hw.ramSize=$V_RAM
image.sysdir.1=system-images/android-$V_API/$V_TAG/$V_ABI/
tag.id=$V_TAG"

  echo
  echo "Verifying against config.ini:"
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    if grep -qxF "$line" "$config"; then
      echo "  ok      $line"
    else
      found="$(grep "^${line%%=*}=" "$config" | head -1 || true)"
      echo "  MISSING $line   (found: ${found:-nothing})"
      errors=$((errors + 1))
    fi
  done <<< "$expected"

  echo
  if [ "$errors" -gt 0 ]; then
    echo "$errors values do not match. $guest is not the guest we wanted."
    return 1
  fi
  echo "All values match. $guest is at $ANDROID_AVD_HOME/$guest.avd"
  echo
}

# Reads a value out of the device block in devices.xml.
device_value() {
  awk -v id="$1" -v field="$2" '
    $0 ~ "<d:id>" id "</d:id>" { inside = 1 }
    inside && $0 ~ "<d:" field ">" {
      match($0, "<d:" field ">[^<]*"); v = substr($0, RSTART, RLENGTH)
      sub("<d:" field ">", "", v); print v; exit
    }
    inside && /<\/d:device>/ { exit }
  ' "$ABGAL_HOME/devices.xml"
}

# Convert xxhdpi and its relatives into the number config.ini carries.
density_to_number() {
  case "$1" in
    ldpi) echo 120 ;; mdpi) echo 160 ;; tvdpi) echo 213 ;;
    hdpi) echo 240 ;; xhdpi) echo 320 ;; xxhdpi) echo 480 ;; xxxhdpi) echo 640 ;;
    *dpi) echo "${1%dpi}" ;;
    *) echo "$1" ;;
  esac
}

if [ $# -eq 0 ]; then
  echo "Usage: bash create-avd.sh <template> [<guest>]"
  echo
  echo "Templates in devices.conf:"
  list_profiles
  exit 0
fi

create_avd "$1" "${2:-$1}"
