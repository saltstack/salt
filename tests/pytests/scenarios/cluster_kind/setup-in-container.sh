#!/usr/bin/env bash
# Bootstrap the debian-11 / debian-12 / ubuntu CI container so it can run
# tests/pytests/scenarios/cluster_kind/.  Installs:
#
#   * dockerd (already in the salt-ci-containers/testing:* images)
#   * kind   (downloaded as a static binary)
#   * kubectl (downloaded as a static binary)
#
# Then starts dockerd inside the container.  Idempotent — re-running is a
# no-op once everything is in place.
#
# Usage (from inside the container):
#
#   bash /salt/tests/pytests/scenarios/cluster_kind/setup-in-container.sh
#
# Or from the host:
#
#   docker exec <name> bash /salt/tests/pytests/scenarios/cluster_kind/setup-in-container.sh

set -euo pipefail

KIND_VERSION="${KIND_VERSION:-v0.24.0}"
KUBECTL_VERSION="${KUBECTL_VERSION:-v1.31.0}"

ARCH="$(uname -m)"
case "${ARCH}" in
    x86_64) GOARCH="amd64" ;;
    aarch64|arm64) GOARCH="arm64" ;;
    *) echo "Unsupported architecture: ${ARCH}" >&2; exit 1 ;;
esac

if ! command -v kind >/dev/null 2>&1; then
    echo "Installing kind ${KIND_VERSION} (${GOARCH})..."
    curl -sSLo /usr/local/bin/kind \
        "https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-linux-${GOARCH}"
    chmod +x /usr/local/bin/kind
else
    echo "kind already installed: $(kind version 2>&1 | head -1)"
fi

if ! command -v kubectl >/dev/null 2>&1; then
    echo "Installing kubectl ${KUBECTL_VERSION} (${GOARCH})..."
    curl -sSLo /usr/local/bin/kubectl \
        "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${GOARCH}/kubectl"
    chmod +x /usr/local/bin/kubectl
else
    echo "kubectl already installed: $(kubectl version --client 2>&1 | head -1)"
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker is not installed in this container." >&2
    echo "       Use a salt-ci-containers/testing:* image (debian-11 / 12, ubuntu, …)." >&2
    exit 1
fi

# Start dockerd if not already running.  Inside the privileged systemd
# container we'd normally `systemctl start docker`; the salt-ci images
# tend to run dockerd directly, so we tolerate either path.
if ! docker info >/dev/null 2>&1; then
    if command -v systemctl >/dev/null 2>&1 && systemctl --version >/dev/null 2>&1; then
        echo "Starting docker via systemd..."
        systemctl start docker || true
    fi
fi

if ! docker info >/dev/null 2>&1; then
    echo "Starting dockerd in the background..."
    nohup dockerd >/var/log/dockerd.log 2>&1 &
    # Wait up to 30 s for the daemon socket to appear.
    for _ in $(seq 1 30); do
        if docker info >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
fi

if ! docker info >/dev/null 2>&1; then
    echo "ERROR: dockerd failed to start. Check /var/log/dockerd.log." >&2
    tail -30 /var/log/dockerd.log >&2 || true
    exit 1
fi

echo
echo "✓ Container ready for cluster_kind scenarios."
echo "  kind    : $(kind version 2>&1 | head -1)"
echo "  kubectl : $(kubectl version --client -o yaml 2>/dev/null | grep gitVersion: | head -1 | tr -d ' ')"
echo "  docker  : $(docker version --format '{{.Server.Version}}' 2>&1)"
