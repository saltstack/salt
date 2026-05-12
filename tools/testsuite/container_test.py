"""
These commands are related to running tests in CI containers.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import logging
import shutil
from typing import TYPE_CHECKING

from ptscripts import Context, command_group

import tools.utils

log = logging.getLogger(__name__)

# Define the command group
container_test = command_group(
    name="container-test",
    help="CI container test execution commands",
    description=__doc__,
    parent="ts",
)

# Platform to container image mapping
PLATFORM_IMAGES = {
    "debian-11": "ghcr.io/saltstack/salt-ci-containers/testing:debian-11",
    "debian-12": "ghcr.io/saltstack/salt-ci-containers/testing:debian-12",
    "ubuntu-20.04": "ghcr.io/saltstack/salt-ci-containers/testing:ubuntu-20.04",
    "ubuntu-22.04": "ghcr.io/saltstack/salt-ci-containers/testing:ubuntu-22.04",
    "ubuntu-24.04": "ghcr.io/saltstack/salt-ci-containers/testing:ubuntu-24.04",
    "rockylinux-8": "ghcr.io/saltstack/salt-ci-containers/testing:rockylinux-8",
    "rockylinux-9": "ghcr.io/saltstack/salt-ci-containers/testing:rockylinux-9",
    "amazonlinux-2": "ghcr.io/saltstack/salt-ci-containers/testing:amazonlinux-2",
    "amazonlinux-2023": "ghcr.io/saltstack/salt-ci-containers/testing:amazonlinux-2023",
    "photon-5": "ghcr.io/saltstack/salt-ci-containers/testing:photon-5",
    "fedora-40": "ghcr.io/saltstack/salt-ci-containers/testing:fedora-40",
    "opensuse-15": "ghcr.io/saltstack/salt-ci-containers/testing:opensuse-15",
    "archlinux-lts": "ghcr.io/saltstack/salt-ci-containers/testing:archlinux-lts",
}


def check_docker(ctx: Context) -> bool:
    """
    Check if docker is available and running.
    """
    docker = shutil.which("docker")
    if not docker:
        ctx.error("docker command not found in PATH")
        return False

    # Check if docker daemon is running
    ret = ctx.run("docker", "info", capture=True, check=False)
    if ret.returncode != 0:
        ctx.error("docker daemon is not running")
        return False

    return True


@container_test.command(
    name="setup",
    arguments={
        "container_name": {
            "help": "Container name to setup",
        },
        "arch": {
            "help": "Architecture (x86_64 or arm64)",
        },
        "python": {
            "help": "Python version (e.g., 3.11) - determines if relenv symlink is needed",
        },
    },
)
def setup_container(
    ctx: Context,
    container_name: str,
    arch: str = "x86_64",
    python: str = None,
):
    """
    Setup a CI container environment for testing.

    This command:
    1. Decompresses nox dependencies
    2. Creates relenv toolchain symlink (for Python 3.11+)
    3. Verifies the setup

    Examples:

     * Setup debian-11 container:

         tools ts container-test setup salt-test-debian-11

     * Setup with Python 3.11 (creates relenv symlink):

         tools ts container-test setup salt-test-debian-11 --python 3.11

     * Setup arm64 container:

         tools ts container-test setup salt-test-rocky9-arm64 --arch arm64
    """
    if TYPE_CHECKING:
        assert container_name is not None

    if not check_docker(ctx):
        ctx.exit(1)

    ctx.info(f"Setting up container: {container_name}")

    # Check if container exists
    ret = ctx.run(
        "docker",
        "ps",
        "-a",
        "--filter",
        f"name={container_name}",
        "--format",
        "{{.Names}}",
        capture=True,
        check=False,
    )
    if ret.returncode != 0 or container_name not in ret.stdout.decode():
        ctx.error(f"Container '{container_name}' not found")
        ctx.info("Create the container first using 'tools container create'")
        ctx.exit(1)

    # Step 1: Decompress dependencies
    ctx.info("Step 1/3: Decompressing nox dependencies...")
    ret = ctx.run(
        "docker",
        "exec",
        container_name,
        "python3",
        "-m",
        "nox",
        "--force-color",
        "-e",
        "decompress-dependencies",
        "--",
        "linux",
        arch,
        check=False,
    )
    if ret.returncode != 0:
        ctx.error("Failed to decompress dependencies")
        ctx.exit(1)

    ctx.info("✓ Dependencies decompressed")

    # Step 2: Create relenv toolchain symlink (Python 3.11+)
    needs_symlink = False
    if python:
        try:
            major, minor = python.split(".")[:2]
            if int(major) >= 3 and int(minor) >= 11:
                needs_symlink = True
        except (ValueError, IndexError):
            ctx.warn(f"Could not parse Python version: {python}")

    if needs_symlink:
        ctx.info("Step 2/3: Creating relenv toolchain symlink (Python 3.11+)...")
        ret = ctx.run(
            "docker",
            "exec",
            container_name,
            "bash",
            "-c",
            "mkdir -p /root/.local/relenv && ln -sf /root/.cache/relenv/toolchains /root/.local/relenv/toolchain",
            check=False,
        )
        if ret.returncode != 0:
            ctx.warn("Failed to create relenv symlink (non-fatal)")
        else:
            # Verify symlink
            ret = ctx.run(
                "docker",
                "exec",
                container_name,
                "bash",
                "-c",
                f"test -f /root/.local/relenv/toolchain/{arch}-linux-gnu/bin/{arch}-linux-gnu-gcc && echo 'OK' || echo 'FAILED'",
                capture=True,
                check=False,
            )
            if "OK" in ret.stdout.decode():
                ctx.info("✓ Relenv toolchain symlink created and verified")
            else:
                ctx.warn("✗ Relenv toolchain symlink verification failed")
    else:
        ctx.info("Step 2/3: Skipping relenv symlink (Python < 3.11 or not specified)")

    # Step 3: Verify setup
    ctx.info("Step 3/3: Verifying setup...")
    ret = ctx.run(
        "docker",
        "exec",
        container_name,
        "python3",
        "-c",
        "import sys; print(f'Python {sys.version}')",
        capture=True,
        check=False,
    )
    if ret.returncode == 0:
        python_version = ret.stdout.decode().strip()
        ctx.info(f"✓ {python_version}")
    else:
        ctx.warn("Could not verify Python version")

    ctx.info(f"\n✓ Container '{container_name}' is ready for testing!")
    ctx.exit(0)


@container_test.command(
    name="run",
    arguments={
        "container_name": {
            "help": "Container name to run test in",
        },
        "test_path": {
            "help": "Test path to run (file, directory, or specific test)",
        },
        "args": {
            "help": "Additional pytest/nox arguments (e.g., '--run-slow -x -v')",
            "nargs": "*",
        },
    },
)
def run_test(
    ctx: Context,
    container_name: str,
    test_path: str,
    args: list[str] = None,
):
    """
    Run a test in a CI container.

    Examples:

     * Run a specific test:

         tools ts container-test run salt-test-debian-11 \\
             tests/pytests/functional/test_version.py::test_salt_extensions_in_versions_report \\
             --args --run-slow -x -v

     * Run all tests in a file:

         tools ts container-test run salt-test-debian-11 \\
             tests/pytests/functional/test_version.py \\
             --args --run-slow -x

     * Run tests in a directory:

         tools ts container-test run salt-test-debian-11 \\
             tests/pytests/unit/ \\
             --args -v
    """
    if TYPE_CHECKING:
        assert container_name is not None
        assert test_path is not None

    if not check_docker(ctx):
        ctx.exit(1)

    ctx.info(f"Running test in container: {container_name}")
    ctx.info(f"Test path: {test_path}")

    # Build command
    cmd = [
        "docker",
        "exec",
        container_name,
        "python3",
        "-m",
        "nox",
        "--force-color",
        "-e",
        "ci-test-onedir",
        "--",
        test_path,
    ]

    if args:
        cmd.extend(args)

    ctx.info(f"Running: {' '.join(cmd)}\n")

    # Run test and stream output
    ret = ctx.run(*cmd, check=False)

    if ret.returncode == 0:
        ctx.info("\n✓ Tests passed!")
    else:
        ctx.warn(f"\n✗ Tests failed with exit code {ret.returncode}")

    ctx.exit(ret.returncode)


@container_test.command(
    name="cleanup",
    arguments={
        "artifacts": {
            "help": "Clean up downloaded artifacts",
        },
        "containers": {
            "help": "Pattern to match container names to remove (e.g., 'salt-test-*')",
        },
    },
)
def cleanup(
    ctx: Context,
    artifacts: bool = False,
    containers: str = None,
):
    """
    Clean up artifacts and/or containers.

    Examples:

     * Clean up artifacts only:

         tools ts container-test cleanup --artifacts

     * Remove containers matching pattern:

         tools ts container-test cleanup --containers 'salt-test-*'

     * Clean up everything:

         tools ts container-test cleanup --artifacts --containers 'salt-test-*'
    """
    if not artifacts and not containers:
        ctx.error("Specify --artifacts and/or --containers")
        ctx.exit(1)

    if artifacts:
        ctx.info("Cleaning up artifacts...")

        # Remove artifacts directory
        artifacts_path = tools.utils.REPO_ROOT / "artifacts"
        if artifacts_path.exists():
            shutil.rmtree(artifacts_path)
            ctx.info(f"  ✓ Removed {artifacts_path}")

        # Remove nox artifacts
        for pattern in ["nox-*.zip", "nox.*.tar.*"]:
            for path in tools.utils.REPO_ROOT.glob(pattern):
                path.unlink()
                ctx.info(f"  ✓ Removed {path.name}")

        ctx.info("✓ Artifacts cleaned up")

    if containers:
        if not check_docker(ctx):
            ctx.exit(1)

        ctx.info(f"Finding containers matching: {containers}")

        # List matching containers
        ret = ctx.run(
            "docker",
            "ps",
            "-a",
            "--filter",
            f"name={containers}",
            "--format",
            "{{.Names}}",
            capture=True,
            check=False,
        )

        if ret.returncode != 0:
            ctx.error("Failed to list containers")
            ctx.exit(1)

        container_names = ret.stdout.decode().strip().split("\n")
        container_names = [name for name in container_names if name]

        if not container_names:
            ctx.info(f"No containers found matching '{containers}'")
        else:
            ctx.info(f"Found {len(container_names)} container(s) to remove:")
            for name in container_names:
                ctx.print(f"  - {name}")

            # Remove each container
            for name in container_names:
                ctx.info(f"Removing {name}...")
                # Stop container first
                ctx.run("docker", "stop", name, capture=True, check=False)
                # Remove container
                ret = ctx.run("docker", "rm", name, capture=True, check=False)
                if ret.returncode == 0:
                    ctx.info(f"  ✓ Removed {name}")
                else:
                    ctx.warn(f"  ✗ Failed to remove {name}")

            ctx.info("✓ Containers cleaned up")

    ctx.exit(0)


@container_test.command(
    name="list-platforms",
)
def list_platforms(ctx: Context):
    """
    List available CI container platform images.

    Example:

     * List all platforms:

         tools ts container-test list-platforms
    """
    ctx.info("Available CI Container Platforms:\n")

    for platform, image in sorted(PLATFORM_IMAGES.items()):
        ctx.print(f"  {platform:20s} → {image}")

    ctx.print(f"\nTotal: {len(PLATFORM_IMAGES)} platforms")
    ctx.print("\nUsage:")
    ctx.print("  tools container create <IMAGE> --name <NAME>")
    ctx.print(
        "  Example: tools container create ghcr.io/saltstack/salt-ci-containers/testing:debian-11 --name salt-test-debian-11"
    )

    ctx.exit(0)
