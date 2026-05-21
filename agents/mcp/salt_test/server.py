#!/usr/bin/env python3
"""
Salt Test MCP Server

Exposes Salt testing tools via Model Context Protocol (MCP).
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Add tools directory to path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError as e:
    print(
        f"Error: MCP SDK not installed. Install with: pip install mcp. Error: {e}",
        file=sys.stderr,
    )
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("salt-test-mcp")

# Initialize MCP server
app = Server("salt-test")


def run_tool_command(*args, **kwargs) -> dict[str, Any]:
    """
    Run a tools command and return the result.
    """
    cmd = [sys.executable, "-m", "ptscripts"] + list(args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=kwargs.get("timeout", 300),  # 5 minute default timeout
        )

        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "Command timed out",
        }
    except Exception as e:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
        }


@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    List available tools.
    """
    return [
        # Local pytest testing
        Tool(
            name="pytest_run",
            description="Run pytest directly with specified test path for quick local testing",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_path": {
                        "type": "string",
                        "description": "Test path (file, directory, or specific test like path/to/test.py::test_name)",
                    },
                    "venv_path": {
                        "type": "string",
                        "description": "Optional path to virtual environment (defaults to ./venv310)",
                    },
                    "extra_args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional pytest arguments (e.g., ['-v', '-x'])",
                    },
                },
                "required": ["test_path"],
            },
        ),
        Tool(
            name="pytest_last_failed",
            description="Re-run only tests that failed in the last pytest run",
            inputSchema={
                "type": "object",
                "properties": {
                    "venv_path": {
                        "type": "string",
                        "description": "Optional path to virtual environment",
                    },
                    "extra_args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional pytest arguments",
                    },
                },
            },
        ),
        Tool(
            name="pytest_pattern",
            description="Run tests matching a pattern (uses pytest -k)",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Test name pattern to match",
                    },
                    "test_path": {
                        "type": "string",
                        "description": "Optional test path to search within (defaults to tests/pytests)",
                    },
                    "venv_path": {
                        "type": "string",
                        "description": "Optional path to virtual environment",
                    },
                    "extra_args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional pytest arguments",
                    },
                },
                "required": ["pattern"],
            },
        ),
        Tool(
            name="pytest_list",
            description="List test files matching a glob pattern",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern (e.g., '**/test_loader*.py')",
                    },
                    "path": {
                        "type": "string",
                        "description": "Base path to search in (defaults to tests/pytests)",
                    },
                },
            },
        ),
        # CI failure discovery
        Tool(
            name="ci_pr_failures",
            description="Get all failing tests from a PR's CI runs in saltstack/salt repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                    },
                    "repository": {
                        "type": "string",
                        "description": "Repository (defaults to saltstack/salt)",
                    },
                    "json_output": {
                        "type": "boolean",
                        "description": "Return output as JSON",
                    },
                },
                "required": ["pr_number"],
            },
        ),
        Tool(
            name="ci_run_failures",
            description="Get failing tests from a specific CI workflow run",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "integer",
                        "description": "Workflow run ID",
                    },
                    "repository": {
                        "type": "string",
                        "description": "Repository (defaults to saltstack/salt)",
                    },
                    "json_output": {
                        "type": "boolean",
                        "description": "Return output as JSON",
                    },
                },
                "required": ["run_id"],
            },
        ),
        Tool(
            name="ci_failure_summary",
            description="Get a human-readable summary of PR test failures",
            inputSchema={
                "type": "object",
                "properties": {
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                    },
                    "repository": {
                        "type": "string",
                        "description": "Repository (defaults to saltstack/salt)",
                    },
                },
                "required": ["pr_number"],
            },
        ),
        # Container testing
        Tool(
            name="ci_setup_container",
            description="Setup a CI container environment for testing (decompress dependencies, create relenv symlink for Python 3.11+)",
            inputSchema={
                "type": "object",
                "properties": {
                    "container_name": {
                        "type": "string",
                        "description": "Container name",
                    },
                    "arch": {
                        "type": "string",
                        "description": "Architecture (x86_64 or arm64)",
                        "enum": ["x86_64", "arm64"],
                    },
                    "python_version": {
                        "type": "string",
                        "description": "Python version (e.g., '3.11') - determines if relenv symlink is needed",
                    },
                },
                "required": ["container_name"],
            },
        ),
        Tool(
            name="ci_run_test",
            description="Run a test in a CI container",
            inputSchema={
                "type": "object",
                "properties": {
                    "container_name": {
                        "type": "string",
                        "description": "Container name",
                    },
                    "test_path": {
                        "type": "string",
                        "description": "Test path (file, directory, or specific test)",
                    },
                    "extra_args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional arguments (e.g., ['--run-slow', '-x', '-v'])",
                    },
                },
                "required": ["container_name", "test_path"],
            },
        ),
        Tool(
            name="ci_cleanup",
            description="Clean up artifacts and/or containers",
            inputSchema={
                "type": "object",
                "properties": {
                    "artifacts": {
                        "type": "boolean",
                        "description": "Clean up downloaded artifacts",
                    },
                    "containers": {
                        "type": "string",
                        "description": "Pattern to match container names to remove (e.g., 'salt-test-*')",
                    },
                },
            },
        ),
        Tool(
            name="ci_list_platforms",
            description="List available CI container platform images",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        # Package building
        Tool(
            name="ci_build_pkg",
            description="Build Salt packages (RPM/Deb) using CI containers",
            inputSchema={
                "type": "object",
                "properties": {
                    "pkg_type": {
                        "type": "string",
                        "description": "Package type to build",
                        "enum": ["rpm", "deb", "windows", "macos"],
                    },
                    "distro": {
                        "type": "string",
                        "description": "Distribution to build on (e.g., 'debian-13', 'rockylinux-9'). Defaults to debian-13 for deb, rockylinux-9 for rpm.",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Target platform (e.g., 'linux', 'windows', 'macos')",
                        "enum": ["linux", "windows", "macos"],
                    },
                    "arch": {
                        "type": "string",
                        "description": "Target architecture (e.g., 'x86_64', 'aarch64')",
                        "enum": ["x86_64", "aarch64", "amd64"],
                    },
                    "relenv_version": {
                        "type": "string",
                        "description": "Relenv version to use (e.g., '0.22.4')",
                    },
                    "python_version": {
                        "type": "string",
                        "description": "Python version to use (e.g., '3.10.19')",
                    },
                },
                "required": ["pkg_type"],
            },
        ),
        Tool(
            name="ci_test_pkg",
            description="Run package tests (upgrade/install) in a CI container",
            inputSchema={
                "type": "object",
                "properties": {
                    "pkg_type": {
                        "type": "string",
                        "description": "Package type (deb/rpm)",
                        "enum": ["deb", "rpm"],
                    },
                    "distro": {
                        "type": "string",
                        "description": "Distribution to test on (e.g., 'debian-13')",
                    },
                    "test_type": {
                        "type": "string",
                        "description": "Test type (upgrade, install)",
                        "default": "upgrade",
                    },
                    "prev_version": {
                        "type": "string",
                        "description": "Previous version for upgrade tests (e.g., '3006.22')",
                    },
                    "extra_args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional arguments for nox",
                    },
                },
                "required": ["pkg_type"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """
    Handle tool calls.
    """
    logger.info(f"Tool called: {name} with arguments: {arguments}")

    try:
        # Map tool names to commands
        if name == "pytest_run":
            cmd_args = ["ts", "pytest", "run", arguments["test_path"]]
            if arguments.get("venv_path"):
                cmd_args.extend(["--venv", arguments["venv_path"]])
            if arguments.get("extra_args"):
                cmd_args.append("--args")
                cmd_args.extend(arguments["extra_args"])

        elif name == "pytest_last_failed":
            cmd_args = ["ts", "pytest", "last-failed"]
            if arguments.get("venv_path"):
                cmd_args.extend(["--venv", arguments["venv_path"]])
            if arguments.get("extra_args"):
                cmd_args.append("--args")
                cmd_args.extend(arguments["extra_args"])

        elif name == "pytest_pattern":
            cmd_args = ["ts", "pytest", "pattern", arguments["pattern"]]
            if arguments.get("test_path"):
                cmd_args.extend(["--test-path", arguments["test_path"]])
            if arguments.get("venv_path"):
                cmd_args.extend(["--venv", arguments["venv_path"]])
            if arguments.get("extra_args"):
                cmd_args.append("--args")
                cmd_args.extend(arguments["extra_args"])

        elif name == "pytest_list":
            cmd_args = ["ts", "pytest", "list"]
            if arguments.get("pattern"):
                cmd_args.extend(["--pattern", arguments["pattern"]])
            if arguments.get("path"):
                cmd_args.extend(["--path", arguments["path"]])

        elif name == "ci_pr_failures":
            cmd_args = ["ts", "ci-failure", "pr", str(arguments["pr_number"])]
            if arguments.get("repository"):
                cmd_args.extend(["--repository", arguments["repository"]])
            if arguments.get("json_output"):
                cmd_args.append("--json-output")

        elif name == "ci_run_failures":
            cmd_args = ["ts", "ci-failure", "run", str(arguments["run_id"])]
            if arguments.get("repository"):
                cmd_args.extend(["--repository", arguments["repository"]])
            if arguments.get("json_output"):
                cmd_args.append("--json-output")

        elif name == "ci_failure_summary":
            cmd_args = ["ts", "ci-failure", "summary", str(arguments["pr_number"])]
            if arguments.get("repository"):
                cmd_args.extend(["--repository", arguments["repository"]])

        elif name == "ci_setup_container":
            cmd_args = ["ts", "container-test", "setup", arguments["container_name"]]
            if arguments.get("arch"):
                cmd_args.extend(["--arch", arguments["arch"]])
            if arguments.get("python_version"):
                cmd_args.extend(["--python", arguments["python_version"]])

        elif name == "ci_run_test":
            cmd_args = [
                "ts",
                "container-test",
                "run",
                arguments["container_name"],
                arguments["test_path"],
            ]
            if arguments.get("extra_args"):
                cmd_args.append("--args")
                cmd_args.extend(arguments["extra_args"])

        elif name == "ci_cleanup":
            cmd_args = ["ts", "container-test", "cleanup"]
            if arguments.get("artifacts"):
                cmd_args.append("--artifacts")
            if arguments.get("containers"):
                cmd_args.extend(["--containers", arguments["containers"]])

        elif name == "ci_list_platforms":
            cmd_args = ["ts", "container-test", "list-platforms"]

        elif name == "ci_build_pkg":
            pkg_type = arguments["pkg_type"]
            distro = arguments.get("distro")

            # Determine image
            if not distro:
                if pkg_type == "deb":
                    distro = "debian-13"
                elif pkg_type == "rpm":
                    distro = "rockylinux-9"
                else:
                    return [
                        TextContent(
                            type="text",
                            text="Error: distro must be specified for non-linux builds or rely on defaults.",
                        )
                    ]

            # Map distro to image (simplified mapping, ideally import from tools)
            image_map = {
                "debian-13": "ghcr.io/saltstack/salt-ci-containers/testing:debian-13",
                "debian-12": "ghcr.io/saltstack/salt-ci-containers/testing:debian-12",
                "debian-11": "ghcr.io/saltstack/salt-ci-containers/testing:debian-11",
                "rockylinux-9": "ghcr.io/saltstack/salt-ci-containers/testing:rockylinux-9",
                "rockylinux-8": "ghcr.io/saltstack/salt-ci-containers/testing:rockylinux-8",
                "amazonlinux-2": "ghcr.io/saltstack/salt-ci-containers/testing:amazonlinux-2",
                "amazonlinux-2023": "ghcr.io/saltstack/salt-ci-containers/testing:amazonlinux-2023",
                "ubuntu-22.04": "ghcr.io/saltstack/salt-ci-containers/testing:ubuntu-22.04",
                "ubuntu-20.04": "ghcr.io/saltstack/salt-ci-containers/testing:ubuntu-20.04",
            }

            image = image_map.get(distro)
            if not image:
                return [
                    TextContent(
                        type="text",
                        text=f"Error: Unknown distro '{distro}'. Supported: {', '.join(image_map.keys())}",
                    )
                ]

            container_name = f"salt-build-{pkg_type}-{distro}"

            # 1. Create container
            create_cmd = ["container", "create", image, "--name", container_name]
            logger.info(f"Creating container: {' '.join(create_cmd)}")

            # Remove existing container first
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                check=False,
                stdout=sys.stderr,
                stderr=sys.stderr,
            )

            # Use tools module to create container correctly with all mounts
            # We use run_tool_command to ensure it runs with the correct python environment and cwd
            create_result = run_tool_command(*create_cmd)

            if not create_result["success"]:
                return [
                    TextContent(
                        type="text",
                        text=f"Failed to create container:\n{create_result['stderr']}",
                    )
                ]

            # 2. Start container
            start_cmd = ["docker", "start", container_name]
            subprocess.run(
                start_cmd, check=False, stdout=sys.stderr, stderr=sys.stderr
            )  # Ensure it's started

            # Disable IPv6 to prevent pip hangs
            subprocess.run(
                [
                    "docker",
                    "exec",
                    container_name,
                    "sysctl",
                    "-w",
                    "net.ipv6.conf.all.disable_ipv6=1",
                ],
                check=False,
                stdout=sys.stderr,
                stderr=sys.stderr,
            )

            # 3. Install dependencies
            if "debian" in distro or "ubuntu" in distro:
                # Install dependencies exactly as in .github/workflows/build-packages.yml
                # Plus git, rsync, procps, and basic build tools
                # Explicitly avoiding libzmq3-dev as per CI/CD
                # Also install tools requirements for ptscripts
                install_cmd = [
                    "docker",
                    "exec",
                    container_name,
                    "bash",
                    "-c",
                    "apt-get update && apt-get install -y python3.13-venv devscripts patchelf git rsync procps build-essential debhelper dh-python python3-all python3-setuptools python3-pip bash-completion && python3 -m pip install -r requirements/static/ci/py3.13/tools.lock --break-system-packages --ignore-installed",
                ]
                subprocess.run(
                    install_cmd, check=False, stdout=sys.stderr, stderr=sys.stderr
                )
            elif "rocky" in distro or "amazon" in distro or "fedora" in distro:
                install_cmd = [
                    "docker",
                    "exec",
                    container_name,
                    "dnf",
                    "install",
                    "-y",
                    "rpm-build",
                    "rpm-sign",
                    "python3-devel",
                    "python3-pip",
                    "python3-setuptools",
                    "git",
                    "bash-completion",
                    "make",
                    "gcc",
                    "gcc-c++",
                ]
                subprocess.run(
                    install_cmd, check=False, stdout=sys.stderr, stderr=sys.stderr
                )
                # Install tools requirements (assuming python3 is available)
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        container_name,
                        "python3",
                        "-m",
                        "pip",
                        "install",
                        "-r",
                        "requirements/static/ci/py3.10/tools.lock",
                    ],
                    check=False,
                    stdout=sys.stderr,
                    stderr=sys.stderr,
                )

            # 4. Run build
            # We need to ensure environment variables are passed correctly for relenv
            # SKIP_REQUIREMENTS_INSTALL=1 might be used by some tools, PIP_BREAK_SYSTEM_PACKAGES=1 allows pip to install system packages
            env_vars = [
                "-e",
                "SKIP_REQUIREMENTS_INSTALL=1",
                "-e",
                "PIP_BREAK_SYSTEM_PACKAGES=1",
            ]
            if arguments.get("relenv_version"):
                env_vars.extend(
                    ["-e", f"SALT_RELENV_VERSION={arguments['relenv_version']}"]
                )
            if arguments.get("python_version"):
                env_vars.extend(
                    ["-e", f"SALT_PYTHON_VERSION={arguments['python_version']}"]
                )
            if arguments.get("arch"):
                env_vars.extend(["-e", f"SALT_PACKAGE_ARCH={arguments['arch']}"])

            # Construct the full build command
            # Note: We are running 'python3 -m ptscripts pkg build' INSIDE the container
            build_cmd = (
                ["docker", "exec"]
                + env_vars
                + [
                    container_name,
                    "python3",
                    "-m",
                    "ptscripts",
                    "pkg",
                    "build",
                    pkg_type,
                ]
            )

            if arguments.get("platform"):
                build_cmd.extend(["--platform", arguments["platform"]])
            if arguments.get("arch"):
                build_cmd.extend(["--arch", arguments["arch"]])
            if arguments.get("relenv_version"):
                build_cmd.extend(["--relenv-version", arguments["relenv_version"]])
            if arguments.get("python_version"):
                build_cmd.extend(["--python-version", arguments["python_version"]])

            logger.info(f"Running build in container: {build_cmd}")

            # Capture output
            result = subprocess.run(
                build_cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour for build
            )

            response = ""
            if result.returncode == 0:
                response = f"Build successful in container {container_name}!\n\nstdout:\n{result.stdout}"
            else:
                response = f"Build failed in container {container_name} (exit code {result.returncode})\n\nstdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"

            return [TextContent(type="text", text=response)]

        elif name == "ci_test_pkg":
            pkg_type = arguments["pkg_type"]
            distro = arguments.get("distro")
            test_type = arguments.get("test_type", "upgrade")
            prev_version = arguments.get("prev_version")

            if not distro:
                if pkg_type == "deb":
                    distro = "debian-13"
                elif pkg_type == "rpm":
                    distro = "rockylinux-9"

            image_map = {
                "debian-13": "ghcr.io/saltstack/salt-ci-containers/testing:debian-13",
                "debian-12": "ghcr.io/saltstack/salt-ci-containers/testing:debian-12",
                "rockylinux-9": "ghcr.io/saltstack/salt-ci-containers/testing:rockylinux-9",
            }
            image = image_map.get(distro)
            if not image:
                return [
                    TextContent(type="text", text=f"Error: Unknown distro '{distro}'")
                ]

            container_name = f"salt-test-{pkg_type}-{distro}"

            # 1. Create container
            create_cmd = ["container", "create", image, "--name", container_name]
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                check=False,
                stdout=sys.stderr,
                stderr=sys.stderr,
            )
            create_result = run_tool_command(*create_cmd)
            if not create_result["success"]:
                return [
                    TextContent(
                        type="text",
                        text=f"Failed to create container:\n{create_result['stderr']}",
                    )
                ]

            # 2. Start container
            subprocess.run(
                ["docker", "start", container_name],
                check=False,
                stdout=sys.stderr,
                stderr=sys.stderr,
            )

            # 3. Setup environment (nox, ipv6 fix)
            setup_cmds = [
                ["sysctl", "-w", "net.ipv6.conf.all.disable_ipv6=1"],
                [
                    "python3",
                    "-m",
                    "pip",
                    "install",
                    "nox",
                    "--break-system-packages",
                ],  # Debian 12+ needs this or venv
            ]

            for cmd in setup_cmds:
                subprocess.run(
                    ["docker", "exec", container_name] + cmd,
                    check=False,
                    stdout=sys.stderr,
                    stderr=sys.stderr,
                )

            # 4. Copy artifacts (if needed)
            copy_script = f"""
            mkdir -p /salt/artifacts/pkg
            if [ -d /salt/artifacts/{pkg_type} ]; then
              cp -r /salt/artifacts/{pkg_type}/* /salt/artifacts/pkg/
            fi
            ls -l /salt/artifacts/pkg/
            """
            subprocess.run(
                ["docker", "exec", container_name, "bash", "-c", copy_script],
                check=False,
                stdout=sys.stderr,
                stderr=sys.stderr,
            )

            # 5. Run nox
            nox_cmd = ["nox", "-e", "ci-test-onedir-pkgs", "--", test_type]
            if prev_version:
                nox_cmd.append(f"--prev-version={prev_version}")

            if arguments.get("extra_args"):
                nox_cmd.extend(arguments["extra_args"])

            full_cmd = [
                "docker",
                "exec",
                "-e",
                "FORCE_COLOR=1",
                container_name,
            ] + nox_cmd

            logger.info(f"Running test in container: {full_cmd}")
            result = subprocess.run(
                full_cmd, capture_output=True, text=True, timeout=3600
            )

            response = ""
            if result.returncode == 0:
                response = f"Tests passed in container {container_name}!\n\nstdout:\n{result.stdout}"
            else:
                response = f"Tests failed in container {container_name} (exit code {result.returncode})\n\nstdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"

            return [TextContent(type="text", text=response)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        # Run the command
        result = run_tool_command(*cmd_args)

        # Format response
        if result["success"]:
            response = result["stdout"]
            if result["stderr"]:
                response += f"\n\nWarnings/Info:\n{result['stderr']}"
        else:
            response = f"Command failed with exit code {result['returncode']}\n\n"
            response += f"stdout:\n{result['stdout']}\n\n"
            response += f"stderr:\n{result['stderr']}"

        return [TextContent(type="text", text=response)]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """
    Main entry point for the MCP server.
    """
    logger.info("Starting Salt Test MCP Server")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
