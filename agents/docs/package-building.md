# Package Building Guide

This guide describes how to build Salt packages (RPM, Deb, etc.) locally using the same methods as the CI/CD pipeline.

## Overview

Salt packages are built using the `tools` script (specifically `tools pkg`) running inside a CI container. This ensures the build environment matches the official release environment.

The general process is:
1.  Enter the appropriate CI container
2.  Setup the Python environment
3.  Build the source tarball
4.  Build the "Onedir" (a self-contained directory with Python and dependencies)
5.  Build the final package (RPM/Deb) using the Onedir

## Prerequisites

-   Docker installed and running
-   `python-tools-scripts` installed in your local environment (optional, but helpful for some commands)

## Reference Workflows

The instructions in this guide are derived from the official GitHub Actions workflows. If you need to verify the current build process or versions, check these files:

-   **`.github/workflows/ci.yml`**: The main entry point for CI builds. It defines the high-level orchestration.
-   **`.github/workflows/build-salt-onedir.yml`**: Defines how the "Onedir" (relocatable Python environment) is built. Check this for `relenv` and `python` versions.
-   **`.github/workflows/build-packages.yml`**: Defines how the final RPM/Deb/Windows/macOS packages are built using the Onedir.
-   **`.github/actions/build-source-tarball/action.yml`**: The steps to create the initial source distribution.

## Building RPMs (Linux)

### 1. Enter the Build Container

From the root of the Salt repository:

```bash
docker run --rm -it \
  -v "$(pwd):/salt" \
  -w /salt \
  ghcr.io/saltstack/salt-ci-containers/testing:fedora-42 \
  bash
```

*Note: Use `fedora-42` for RPM builds. For Deb builds, use `debian-11` or similar.*

### 2. Setup Python Environment (Inside Container)

Once inside the container:

```bash
# Detect python version (likely 3.10 or 3.11 depending on branch/container)
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

# Create and activate venv
python3 -m venv venv
source venv/bin/activate

# Install build dependencies
pip install --upgrade pip setuptools
pip install -r requirements/static/ci/py${PY_VER}/tools.lock
pip install -e .
```

### 3. Build Source Tarball

Create the source distribution:

```bash
python3 -m tools pkg source-tarball
```

This will create `dist/salt-<version>.tar.gz`.

### 4. Build Salt Onedir

The "Onedir" is an artifact containing Salt and all its dependencies (including Python itself) in a relocatable directory.

```bash
# Get the version from the tarball
SALT_VERSION=$(ls dist/salt-*.tar.gz | sed 's/dist\/salt-//;s/.tar.gz//')
mkdir -p artifacts

# Build the Onedir
# Note: CI uses specific pinned versions for relenv and python.
# Check .github/workflows/build-salt-onedir.yml for current versions.
python3 -m tools pkg build salt-onedir "dist/salt-${SALT_VERSION}.tar.gz" \
    --platform linux \
    --package-name artifacts/salt \
    --relenv-version 0.22.4

# Cleanup and Archive
python3 -m tools pkg pre-archive-cleanup artifacts/salt
tar -cJf "artifacts/salt-${SALT_VERSION}-onedir-linux-x86_64.tar.xz" -C artifacts salt
```

### 5. Build RPM Package

Use the Onedir artifact to build the final RPM.

```bash
python3 -m tools pkg build rpm \
    --relenv-version=0.22.4 \
    --python-version=3.10.19 \
    --onedir="salt-${SALT_VERSION}-onedir-linux-x86_64.tar.xz"
```

The RPMs will be generated in `~/rpmbuild/RPMS/x86_64/`.

### 6. Retrieve Artifacts

Before exiting the container, copy the RPMs to the mounted volume:

```bash
mkdir -p artifacts/rpm
cp -r ~/rpmbuild/RPMS/x86_64/*.rpm artifacts/rpm/
```

## Building DEBs (Linux)

The process is similar to RPMs but uses the `deb` command and a Debian container.

1.  Use `ghcr.io/saltstack/salt-ci-containers/testing:debian-11` (or newer).
2.  Follow steps 2-4 above (Source Tarball & Onedir).
3.  Run `python3 -m tools pkg build deb ...` instead of `rpm`.

## Building Windows/macOS Packages

Windows and macOS packages are typically built on their respective host OSs in CI, not in Docker containers. Refer to `.github/workflows/build-packages.yml` for the specific steps and requirements (signing certificates, etc.).
