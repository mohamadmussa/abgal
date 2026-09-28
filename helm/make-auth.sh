#!/usr/bin/env bash
#
# Produces the hash for the login to the view and writes it to auth.local.yaml.
#
# Why a hash and not the password: Helm stores the values it was given as a
# secret in the cluster, and "helm get values" returns them in clear. A
# password kept there is no longer a password.
#
# Usage:
#   bash make-auth.sh                      asks for the password
#   ABGAL_VIEW_PASSWORD=... bash ...       no prompt, for use inside a script

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$HERE/auth.local.yaml"
USER_NAME="${ABGAL_VIEW_USER:-admin}"

if [ -n "${ABGAL_VIEW_PASSWORD:-}" ]; then
  PASSWORD="$ABGAL_VIEW_PASSWORD"
else
  read -r -s -p "Password for user $USER_NAME: " PASSWORD; echo
  read -r -s -p "Once more to be sure: " PASSWORD2; echo
  if [ "$PASSWORD" != "$PASSWORD2" ]; then
    echo "ERROR: the two entries differ." >&2
    exit 1
  fi
fi

if [ "${#PASSWORD}" -lt 8 ]; then
  echo "ERROR: eight characters minimum. This view shows a logged in device." >&2
  exit 1
fi

# apr1, not the openssl default. For basicAuth Traefik understands only MD5 in
# apr1 format, SHA1 and bcrypt. A sha512-crypt hash would be produced without
# complaint and then rejected at every login.
HASH="$(openssl passwd -apr1 "$PASSWORD")"

umask 077
cat > "$TARGET" <<YAML
# Written by make-auth.sh on $(date +%Y-%m-%d).
# This file is never committed and stays out of the packaged chart.
auth:
  user: "$USER_NAME"
  hash: '$HASH'
YAML

echo "Written:  $TARGET"
echo "User:     $USER_NAME"
echo "Scheme:   $(echo "$HASH" | cut -d'$' -f2)"
echo
echo "Next: bash apply.sh"
