#!/usr/bin/env bash
#
# Reads a template line from devices.conf and sets the V_* variables from it.
# Sourced by create-avd.sh, never started on its own.
#
# A template describes a class of device. The guests created from it carry
# their own names and their own state, so nothing here knows about ports or
# about anything else that only exists while a guest runs.

read_profile() {
  local wanted="$1"
  local conf="$ABGAL_HOME/devices.conf"
  local line

  # The field itself is not changed. An assignment to $1 would make awk
  # rebuild the whole line, and the pipe characters that separate the
  # fields would disappear in the process.
  line="$(grep -v '^[[:space:]]*#' "$conf" | grep -v '^[[:space:]]*$' \
          | awk -F'|' -v n="$wanted" '{k=$1; gsub(/^ +| +$/,"",k); if (k==n) print}')"

  if [ -z "$line" ]; then
    echo "ERROR: the template '$wanted' is not in devices.conf." >&2
    echo "Known templates:" >&2
    list_profiles >&2
    return 1
  fi

  IFS='|' read -r V_NAME V_DEVICE V_API V_TAG V_ABI V_RAM V_NOTE <<< "$line"
  for v in V_NAME V_DEVICE V_API V_TAG V_ABI V_RAM V_NOTE; do
    printf -v "$v" '%s' "$(echo "${!v}" | sed 's/^ *//; s/ *$//')"
  done

  V_IMAGE="system-images;android-$V_API;$V_TAG;$V_ABI"
  export V_NAME V_DEVICE V_API V_TAG V_ABI V_RAM V_NOTE V_IMAGE
}

list_profiles() {
  grep -v '^[[:space:]]*#' "$ABGAL_HOME/devices.conf" | grep -v '^[[:space:]]*$' \
    | awk -F'|' '{gsub(/^ +| +$/,"",$1); gsub(/^ +| +$/,"",$7); printf "  %-40s %s\n", $1, $7}'
}
