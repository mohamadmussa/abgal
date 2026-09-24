#!/bin/sh
# Environment for the emulator work. Created 2026-09-20.
#
# One source for all shells. Read by ~/.bashrc for interactive shells and by
# ~/.profile for login sessions. A service or a CI runner reads neither of
# those, it gets this file later through EnvironmentFile or an explicit
# "source". See attempt V10.
#
# Why this file exists at all: ~/.bashrc stops at line 8 with the Debian
# standard guard "case $- in *i*) ;; *) return;; esac". Nothing after that
# line ever reaches a non interactive shell. Measured on 2026-09-20 with
# "bash -lc", ANDROID_HOME, PATH and maestro were missing there.
#
# Reading this file more than once is harmless, the path is not filled twice.

# Where this project lives. Derived from this file's own location, so a clone
# works anywhere without editing a line.
#
# Only bash knows the path of a file it is sourcing. Measured on 2026-09-22:
# dash cannot read BASH_SOURCE at all and would leave the root at "/", which
# would then point ANDROID_HOME at /sdk. So other shells are told to say it.
if [ -z "${ABGAL_HOME:-}" ]; then
  if [ -n "${BASH_VERSION:-}" ]; then
    ABGAL_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  else
    echo "env.sh: this is not bash and ABGAL_HOME is not set." >&2
    echo "Set it by hand: export ABGAL_HOME=/path/to/abgal" >&2
    return 1 2>/dev/null || exit 1
  fi
fi
export ABGAL_HOME

# Android SDK. Own SDK inside the project folder, not the Debian build.
# Debian ships adb 29.0.6 from 2020, here it is 37.0.1. Mixed versions make
# one build kill the other's service without any message.
# The Debian package stays installed, but it is neither ANDROID_HOME nor on
# the path.
#
# It lives inside the project folder and not under $HOME, so that everything
# belonging to this project can be found in one place. sdk/ and avd/ are in
# .gitignore, so a few gigabytes of SDK never reach a commit.
ANDROID_HOME="$ABGAL_HOME/sdk"
ANDROID_SDK_ROOT="$ANDROID_HOME"
export ANDROID_HOME ANDROID_SDK_ROOT

# The virtual devices also live inside the project folder instead of under
# ~/.android/avd.
ANDROID_AVD_HOME="$ABGAL_HOME/avd"
export ANDROID_AVD_HOME

# User files of the SDK tools, also inside the project folder. avdmanager and
# the Android CLI read the first name, the emulator only the second. adb
# reads neither and keeps its key in ~/.android on purpose.
ANDROID_USER_HOME="$ABGAL_HOME/android-home"
ANDROID_EMULATOR_HOME="$ABGAL_HOME/android-home"
export ANDROID_USER_HOME ANDROID_EMULATOR_HOME

case ":$PATH:" in
  *":$ANDROID_HOME/platform-tools:"*) ;;
  *) PATH="$ANDROID_HOME/platform-tools:$PATH" ;;
esac

case ":$PATH:" in
  *":$ANDROID_HOME/emulator:"*) ;;
  *) PATH="$ANDROID_HOME/emulator:$PATH" ;;
esac

# Maestro. Lives outside the SDK.
case ":$PATH:" in
  *":$HOME/.maestro/bin:"*) ;;
  *) PATH="$PATH:$HOME/.maestro/bin" ;;
esac

export PATH

# k3s without sudo. /etc/rancher/k3s/k3s.yaml belongs to root with 0600, this
# copy belongs to you. The k3s service itself is not changed.
if [ -r "$HOME/.kube/config" ]; then
  KUBECONFIG="$HOME/.kube/config"
  export KUBECONFIG
fi

# Local values that never get committed, for example ABGAL_PACKAGE. Optional.
if [ -r "$ABGAL_HOME/env.local.sh" ]; then
  . "$ABGAL_HOME/env.local.sh"
fi
