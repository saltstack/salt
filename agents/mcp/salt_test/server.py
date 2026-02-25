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
except ImportError:
    print(
        "Error: MCP SDK not installed. Install with: pip install mcp",
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
    cmd = [sys.executable, "-m", "tools"] + list(args)

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
