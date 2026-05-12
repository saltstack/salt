#!/usr/bin/env bash
# Re-run Linux package tests the same way as .github/workflows/test-packages-action.yml
# (ghcr.io/saltstack/salt-ci-containers/testing + docker exec + nox). Requires: docker,
# gh (authenticated), curl/jq optional.
#
# Example (Ubuntu 24.04, install chunk, run 24887124652 on saltstack/salt):
#   bash cicd/repro-linux-pkg-in-ci-image.sh 24887124652 ubuntu-24.04 install
#
# Example (downgrade slice matching "Test Package / Ubuntu 24.04 downgrade 3007.13"):
#   bash cicd/repro-linux-pkg-in-ci-image.sh 24887124652 ubuntu-24.04 downgrade -- --prev-version=3007.13
#
# For RPM distros (Amazon Linux, Rocky, …) the script downloads the *-x86_64-rpm artifact
# instead of *-deb. Use slug keys matching IMAGE, e.g. amazonlinux-2023.
#
# Optional: commit upstream only if the team wants a supported reproducer.

set -euo pipefail
RUN_ID=${1:?usage: $0 <run_id> <ubuntu-24.04|debian-12|...> <install|upgrade|downgrade> [-- extra nox posargs e.g. -- --prev-version=3007.13}
SLUG=${2:?}
CHUNK=${3:?}
shift 3

declare -A IMAGE
IMAGE[ubuntu-24.04]=ghcr.io/saltstack/salt-ci-containers/testing:ubuntu-24.04
IMAGE[debian-12]=ghcr.io/saltstack/salt-ci-containers/testing:debian-12
IMAGE[amazonlinux-2023]=ghcr.io/saltstack/salt-ci-containers/testing:amazonlinux-2023
# extend IMAGE[] if you add more slugs

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"
if [[ -z ${IMAGE[$SLUG]+x} ]]; then
  echo "Unknown slug $SLUG — add it to the IMAGE[] map in this script (see cicd/shared-gh-workflows-context.yml containers)." >&2
  exit 1
fi
CONTAINER=local-salt-pkg-repro_$$

ARCH=x86_64
case "$SLUG" in
  *-arm64*) ARCH=arm64 ;;
esac

# Resolve onedir + .deb from the workflow run (same build).
mapfile -t ONEDIR_META < <(gh api "repos/saltstack/salt/actions/runs/${RUN_ID}/artifacts" --paginate \
  --jq '.artifacts[] | select(.name|test("onedir-linux-'"$ARCH"'.*\\.tar\\.xz$")) | .name' | head -1)
if [[ -z ${ONEDIR_META:-} ]]; then
  echo "Could not find onedir-linux $ARCH .tar.xz artifact in run $RUN_ID" >&2
  exit 1
fi
# strip checksum sidecars: artifact name is e.g. salt-3007.13+....-onedir-linux-x86_64.tar.xz
ONEDIR_TAR_NAME=$ONEDIR_META
VERSION_PREFIX=${ONEDIR_TAR_NAME%%-onedir-linux-*}
NOX_NAME="nox-linux-${ARCH}-ci-test-onedir"
if [[ $SLUG =~ ^amazonlinux|rockylinux|fedora|photonos ]]; then
  PKG_ZIP_NAME="${VERSION_PREFIX}-$ARCH-rpm"
else
  PKG_ZIP_NAME="${VERSION_PREFIX}-$ARCH-deb"
fi
mkdir -p "$TMP"

fetch_zip() { gh api "repos/saltstack/salt/actions/artifacts/$1/zip" > "$2"; }

NOX_ID=$(gh api "repos/saltstack/salt/actions/runs/${RUN_ID}/artifacts" --paginate --jq '.artifacts[] | select(.name=="'"$NOX_NAME"'") | .id' | head -1)
ONEDIR_ID=$(gh api "repos/saltstack/salt/actions/runs/${RUN_ID}/artifacts" --paginate --jq '.artifacts[] | select(.name=="'"$ONEDIR_TAR_NAME"'") | .id' | head -1)
PKG_ID=$(gh api "repos/saltstack/salt/actions/runs/${RUN_ID}/artifacts" --paginate --jq '.artifacts[] | select(.name=="'"$PKG_ZIP_NAME"'") | .id' | head -1)

echo "NOX_ID=$NOX_ID ONEDIR_ID=$ONEDIR_ID PKG_ZIP_NAME=$PKG_ZIP_NAME PKG_ID=$PKG_ID"
[[ -n $NOX_ID && -n $ONEDIR_ID && -n $PKG_ID ]]

rm -f "$REPO_ROOT/nox.linux.$ARCH.tar.xz"
fetch_zip "$NOX_ID" "$TMP/nox.zip"
unzip -o -j "$TMP/nox.zip" -d "$REPO_ROOT"
rm -rf "$REPO_ROOT/artifacts/pkg"/* "$REPO_ROOT/artifacts/salt"
mkdir -p "$REPO_ROOT/artifacts/pkg" "$REPO_ROOT/artifacts/logs" "$REPO_ROOT/artifacts/xml-unittests-output"
fetch_zip "$PKG_ID" "$TMP/pkgs.zip"
unzip -o -j "$TMP/pkgs.zip" -d "$REPO_ROOT/artifacts/pkg"
fetch_zip "$ONEDIR_ID" "$TMP/onedir.zip"
unzip -o -j "$TMP/onedir.zip" "$ONEDIR_TAR_NAME" -d "$REPO_ROOT/artifacts"
( cd "$REPO_ROOT/artifacts" && tar xf "$ONEDIR_TAR_NAME" )
test -d "$REPO_ROOT/artifacts/salt"

if ! docker network inspect ip6net >/dev/null 2>&1; then
  docker network create -o com.docker.network.driver.mtu=1500 --ipv6 --subnet 2001:db8::/64 ip6net
fi
docker pull "${IMAGE[$SLUG]}"
DVAR=$(mktemp -d /tmp/saltdockvar.XXXXXX)
docker rm -f "$CONTAINER" 2>/dev/null || true
docker create --name "$CONTAINER" --privileged --workdir=/salt \
  -v "$REPO_ROOT:/salt" -v "$DVAR:/var/lib/docker" \
  -e HOME=/root -e SKIP_REQUIREMENTS_INSTALL=1 -e RAISE_DEPRECATIONS_RUNTIME_ERRORS=1 -e LANG=en_US.UTF-8 \
  --network ip6net \
  --entrypoint /usr/lib/systemd/systemd \
  "${IMAGE[$SLUG]}" \
  --systemd --unit rescue.target
docker start "$CONTAINER"
sleep 3
docker exec "$CONTAINER" python3 -m nox -e decompress-dependencies -- "linux" "$ARCH"
docker exec "$CONTAINER" python3 -m nox -e ci-test-onedir-pkgs -- "$CHUNK" "$@"
docker stop "$CONTAINER" >/dev/null
docker rm "$CONTAINER" >/dev/null
echo OK
