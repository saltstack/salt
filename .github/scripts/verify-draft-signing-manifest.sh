#!/usr/bin/env bash
# Verify salt-release-signing-manifest.json on a draft release before publishing.
# Usage: verify-draft-signing-manifest.sh <owner/repo> <tag e.g. v3007.1>
set -euo pipefail

REPO="${1:?repository owner/name required}"
TAG="${2:?release tag required}"

WORKDIR=$(mktemp -d)
trap 'rm -rf "${WORKDIR}"' EXIT

echo "Fetching signing manifest for ${REPO} ${TAG} ..."
gh release download "${TAG}" -R "${REPO}" -p 'salt-release-signing-manifest.json' -D "${WORKDIR}"

MANIFEST="${WORKDIR}/salt-release-signing-manifest.json"
test -f "${MANIFEST}"

jq -e '.schema_version == 1' "${MANIFEST}" >/dev/null
jq -e --arg t "${TAG}" '.release_tag == $t' "${MANIFEST}" >/dev/null

if [[ "$(jq '.artifacts | length' "${MANIFEST}")" -lt 1 ]]; then
  echo "Signing manifest has no artifacts." >&2
  exit 1
fi

DL="${WORKDIR}/files"
mkdir -p "${DL}"

echo "Verifying digests for signed package entries ..."
while IFS=$'\t' read -r name want; do
  [[ -n "${name}" ]] || continue
  gh release download "${TAG}" -R "${REPO}" -p "${name}" -D "${DL}"
  got=$(sha256sum "${DL}/${name}" | awk '{print $1}')
  if [[ "${got}" != "${want}" ]]; then
    echo "SHA256 mismatch for ${name} (expected ${want}, got ${got})" >&2
    exit 1
  fi
done < <(jq -r '.artifacts[] | [.name, .sha256] | @tsv' "${MANIFEST}")

echo "Checking every package asset on the release is listed in the manifest ..."
mapfile -t release_assets < <(gh api "repos/${REPO}/releases/tags/${TAG}" --jq '.assets[].name')

for aname in "${release_assets[@]}"; do
  if [[ "${aname}" == salt-release-signing-manifest.json ]] || [[ "${aname}" == SHA256SUMS ]] || [[ "${aname}" == CHECKSUMS ]]; then
    continue
  fi
  if [[ "${aname}" =~ \.(deb|rpm|msi|exe|pkg)$ ]]; then
    if ! jq -e --arg n "${aname}" '.artifacts | map(.name) | index($n) != null' "${MANIFEST}" >/dev/null; then
      echo "Release contains package asset not covered by signing manifest: ${aname}" >&2
      exit 1
    fi
  fi
done

echo "Signing manifest checks passed."
