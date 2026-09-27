#!/usr/bin/env bash
#
# Installs or updates the abgal-view chart and then checks that the route
# really stands.
#
# The namespace is ours alone. Nothing from this project lands in "default" or
# in "kube-system", where k3s keeps its own objects.
#
# Usage:
#   bash apply.sh             install or update
#   bash apply.sh --dry-run   only show what would be created
#   bash apply.sh --remove    tear it down again, namespace included

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART="$HERE/abgal-view"

# Two overlays, one origin each. host.local.yaml is copied by hand from
# host.example.yaml, auth.local.yaml is written by make-auth.sh. Kept apart so
# regenerating the hash cannot overwrite the machine values.
HOST_VALUES="$HERE/host.local.yaml"
AUTH_VALUES="$HERE/auth.local.yaml"

RELEASE="${ABGAL_HELM_RELEASE:-abgal-view}"
NAMESPACE="${ABGAL_NAMESPACE:-abgal}"

export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

if [ "${1:-}" = "--remove" ]; then
  helm uninstall "$RELEASE" -n "$NAMESPACE" || true
  kubectl delete namespace "$NAMESPACE" --ignore-not-found
  echo "Removed."
  exit 0
fi

if [ ! -f "$HOST_VALUES" ]; then
  echo "ERROR: $HOST_VALUES is missing." >&2
  echo "Create it with: cp host.example.yaml host.local.yaml" >&2
  exit 1
fi

if [ ! -f "$AUTH_VALUES" ]; then
  echo "ERROR: $AUTH_VALUES is missing." >&2
  echo "Create it with: bash make-auth.sh" >&2
  exit 1
fi

# Render the templates first. A typo in the chart shows up here, and not after
# half of it already stands in the cluster.
helm lint "$CHART" -f "$HOST_VALUES" -f "$AUTH_VALUES" > /dev/null
echo "helm lint: ok"

if [ "${1:-}" = "--dry-run" ]; then
  helm template "$RELEASE" "$CHART" -n "$NAMESPACE" \
    -f "$HOST_VALUES" -f "$AUTH_VALUES"
  exit 0
fi

helm upgrade --install "$RELEASE" "$CHART" \
  --namespace "$NAMESPACE" --create-namespace \
  -f "$HOST_VALUES" -f "$AUTH_VALUES" --wait

# --- Counter check ------------------------------------------------------------
#
# Without it we would only know that Helm was happy. Whether a request actually
# arrives is something only a request can answer.

address="$(helm get values "$RELEASE" -n "$NAMESPACE" -a -o json \
           | python3 -c 'import json,sys; v=json.load(sys.stdin); print(v["route"]["hostname"] + v["route"]["path"])')"

echo
echo "Counter check:"
printf '  %-28s ' "objects in namespace"
kubectl get ingressroute,svc,endpointslice,middleware,secret -n "$NAMESPACE" \
  --no-headers 2>/dev/null | wc -l

printf '  %-28s ' "without password"
anonymous="$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "http://$address/" || echo 000)"
echo "$anonymous"

if [ "$anonymous" != "401" ]; then
  echo >&2
  echo "ERROR: without a password we got $anonymous instead of 401." >&2
  echo "The login is not in effect." >&2
  exit 1
fi

echo
echo "The view hangs under http://$address/ and asks for a login."
echo "The service behind it has to listen on the address from host.local.yaml."
