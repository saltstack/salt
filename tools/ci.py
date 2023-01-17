"""
These commands are used in the CI pipeline.
"""
# pylint: disable=resource-leakage,broad-except
from __future__ import annotations

import json
import logging
import os
import pathlib
import time
from typing import TYPE_CHECKING

from ptscripts import Context, command_group

log = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Define the command group
ci = command_group(name="ci", help="CI Related Commands", description=__doc__)


@ci.command(
    name="process-changed-files",
    arguments={
        "event_name": {
            "help": "The name of the GitHub event being processed.",
        },
        "changed_files": {
            "help": (
                "Path to '.json' file containing the payload of changed files "
                "from the 'dorny/paths-filter' GitHub action."
            ),
        },
    },
)
def process_changed_files(ctx: Context, event_name: str, changed_files: pathlib.Path):
    """
    Set GH Actions outputs for what should build or not.
    """
    gh_event_path = os.environ.get("GITHUB_EVENT_PATH") or None
    if gh_event_path is None:
        ctx.warn("The 'GITHUB_EVENT_PATH' variable is not set.")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert gh_event_path is not None

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is None:
        ctx.warn("The 'GITHUB_OUTPUT' variable is not set.")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert github_output is not None

    try:
        gh_event = json.loads(open(gh_event_path).read())
    except Exception as exc:
        ctx.error(f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc)
        ctx.exit(1)

    ctx.info("GH Event Payload:")
    ctx.print(gh_event, soft_wrap=True)
    # Let's it print until the end
    time.sleep(1)

    if not changed_files.exists():
        ctx.error(f"The '{changed_files}' file does not exist.")
        ctx.exit(1)
    try:
        changed_files_contents = json.loads(changed_files.read_text())
    except Exception as exc:
        ctx.error(f"Could not load the changed files from '{changed_files}': {exc}")
        ctx.exit(1)

    sanitized_changed_files = {}
    if event_name != "schedule":
        ctx.info("Sanitizing paths and confirming no path traversal is being used...")
        for key, data in changed_files_contents.items():
            try:
                loaded_data = json.loads(data)
            except ValueError:
                loaded_data = data
            if key.endswith("_files"):
                files = set()
                for entry in list(loaded_data):
                    if not entry:
                        loaded_data.remove(entry)
                    try:
                        entry = (
                            REPO_ROOT.joinpath(entry).resolve().relative_to(REPO_ROOT)
                        )
                    except ValueError:
                        ctx.error(
                            f"While processing the changed files key {key!r}, the "
                            f"path entry {entry!r} was checked and it's not relative "
                            "to the repository root."
                        )
                        ctx.exit(1)
                    files.add(str(entry))
                sanitized_changed_files[key] = sorted(files)
                continue
            sanitized_changed_files[key] = loaded_data

    ctx.info("Writing 'changed-files' to the github outputs file")
    with open(github_output, "a", encoding="utf-8") as wfh:
        wfh.write(f"changed-files={json.dumps(sanitized_changed_files)}\n")

    ctx.info("Selecting which type of jobs(self hosted runners or not) to run")
    jobs = {"github-hosted-runners": False, "self-hosted-runners": False}
    if event_name == "pull_request":
        ctx.info("Running from a pull request event")
        pr_event_data = gh_event["pull_request"]
        if (
            pr_event_data["head"]["repo"]["full_name"]
            == pr_event_data["base"]["repo"]["full_name"]
        ):
            # If this is a pull request coming from the same repository, don't run anything
            ctx.info("Pull request is coming from the same repository.")
            ctx.info("Not running any jobs since they will run against the branch")
            ctx.info("Writing 'jobs' to the github outputs file")
            with open(github_output, "a", encoding="utf-8") as wfh:
                wfh.write(f"jobs={json.dumps(jobs)}\n")
            ctx.exit(0)

        # This is a PR from a forked repository
        ctx.info("Pull request is not comming from the same repository")
        jobs["github-hosted-runners"] = jobs["self-hosted-runners"] = True
        ctx.info("Writing 'jobs' to the github outputs file")
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"jobs={json.dumps(jobs)}\n")
        ctx.exit(0)

    # This is a push or a scheduled event
    ctx.info(f"Running from a {event_name!r} event")
    if gh_event["repository"]["fork"] is True:
        # This is running on a forked repository, don't run tests
        ctx.info("The push event is on a forked repository")
        jobs["github-hosted-runners"] = True
        ctx.info("Writing 'jobs' to the github outputs file")
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"jobs={json.dumps(jobs)}\n")
        ctx.exit(0)

    # Not running on a fork, run everything
    ctx.info(f"The {event_name!r} event is from the main repository")
    jobs["github-hosted-runners"] = jobs["self-hosted-runners"] = True
    ctx.info("Writing 'jobs' to the github outputs file")
    with open(github_output, "a", encoding="utf-8") as wfh:
        wfh.write(f"jobs={json.dumps(jobs)}")
    ctx.exit(0)


@ci.command(
    name="define-testrun",
    arguments={
        "event_name": {
            "help": "The name of the GitHub event being processed.",
        },
        "changed_files": {
            "help": (
                "Path to '.json' file containing the payload of changed files "
                "from the 'dorny/paths-filter' GitHub action."
            ),
        },
    },
)
def define_testrun(ctx: Context, event_name: str, changed_files: pathlib.Path):
    """
    Set GH Actions outputs for what and how Salt should be tested.
    """
    gh_event_path = os.environ.get("GITHUB_EVENT_PATH") or None
    if gh_event_path is None:
        ctx.warn("The 'GITHUB_EVENT_PATH' variable is not set.")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert gh_event_path is not None

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is None:
        ctx.warn("The 'GITHUB_OUTPUT' variable is not set.")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert github_output is not None

    try:
        gh_event = json.loads(open(gh_event_path).read())
    except Exception as exc:
        ctx.error(f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc)
        ctx.exit(1)

    ctx.info("GH Event Payload:")
    ctx.print(gh_event, soft_wrap=True)
    # Let it print until the end
    time.sleep(1)

    github_step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_step_summary is None:
        ctx.warn("The 'GITHUB_STEP_SUMMARY' variable is not set.")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert github_step_summary is not None

    if not changed_files.exists():
        ctx.error(f"The '{changed_files}' file does not exist.")
        ctx.exit(1)
    try:
        changed_files_contents = json.loads(changed_files.read_text())
    except Exception as exc:
        ctx.error(f"Could not load the changed files from '{changed_files}': {exc}")
        ctx.exit(1)

    if event_name in ("push", "schedule"):
        # In this case, a full test run is in order
        ctx.info("Writing 'testrun' to the github outputs file")
        testrun = {"type": "full"}
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"testrun={json.dumps(testrun)}\n")

        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write(f"Full test run chosen due to event type of {event_name!r}.\n")
        return

    # So, it's a pull request...
    # Based on which files changed, or other things like PR comments we can
    # decide what to run, or even if the full test run should be running on the
    # pull request, etc...
    changed_requirements_files = json.loads(
        changed_files_contents["test_requirements_files"]
    )
    if changed_requirements_files:
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write(
                "Full test run chosen because there was a change made "
                "to the requirements files.\n"
            )
            wfh.write(
                "<details>\n<summary>Changed Requirements Files (click me)</summary>\n<pre>\n"
            )
            for path in sorted(changed_requirements_files):
                wfh.write(f"{path}\n")
            wfh.write("</pre>\n</details>\n")
        testrun = {"type": "full"}
    else:
        testrun_changed_files_path = REPO_ROOT / "testrun-changed-files.txt"
        testrun = {
            "type": "changed",
            "from-filenames": str(testrun_changed_files_path.relative_to(REPO_ROOT)),
        }
        ctx.info(f"Writing {testrun_changed_files_path.name} ...")
        selected_changed_files = []
        step_summary_written = False
        for fpath in json.loads(changed_files_contents["testrun_files"]):
            if fpath.startswith(("tools/", "tasks/")):
                continue
            if fpath in ("noxfile.py",):
                continue
            if fpath == "tests/conftest.py":
                # In this particular case, just run the full test suite
                testrun["type"] = "full"
                with open(github_step_summary, "a", encoding="utf-8") as wfh:
                    wfh.write(
                        "Full test run chosen because there was a change to 'tests/conftest.py'.\n"
                    )
                    step_summary_written = True
            selected_changed_files.append(fpath)
        testrun_changed_files_path.write_text("\n".join(sorted(selected_changed_files)))
        if step_summary_written is False:
            with open(github_step_summary, "a", encoding="utf-8") as wfh:
                wfh.write("Partial test run chosen.\n")
                wfh.write(
                    "<details>\n<summary>Selected Changed Files (click me)</summary>\n<pre>\n"
                )
                for path in sorted(selected_changed_files):
                    wfh.write(f"{path}\n")
                wfh.write("</pre>\n</details>\n")
                step_summary_written = True

    with open(github_step_summary, "a", encoding="utf-8") as wfh:
        wfh.write("<details>\n<summary>All Changed Files (click me)</summary>\n<pre>\n")
        for path in sorted(json.loads(changed_files_contents["repo_files"])):
            wfh.write(f"{path}\n")
        wfh.write("</pre>\n</details>\n")

    ctx.info("Writing 'testrun' to the github outputs file")
    with open(github_output, "a", encoding="utf-8") as wfh:
        wfh.write(f"testrun={json.dumps(testrun)}\n")


@ci.command(
    arguments={
        "distro_slug": {
            "help": "The distribution slug to generate the matrix for",
        },
    },
)
def matrix(ctx: Context, distro_slug: str):
    """
    Generate the test matrix.
    """
    _matrix = []
    for transport in ("zeromq", "tcp"):
        if transport == "tcp":
            if distro_slug not in ("centosstream-9", "ubuntu-22.04-arm64"):
                # Only run TCP transport tests on these distributions
                continue
        for chunk in ("unit", "functional", "integration", "scenarios"):
            if transport == "tcp" and chunk in ("unit", "functional"):
                # Only integration and scenarios shall be tested under TCP,
                # the rest would be repeating tests
                continue
            if "macos" in distro_slug and chunk == "scenarios":
                continue
            _matrix.append({"transport": transport, "tests-chunk": chunk})
    print(json.dumps(_matrix))
    ctx.exit(0)


@ci.command(
    name="transport-matrix",
    arguments={
        "distro_slug": {
            "help": "The distribution slug to generate the matrix for",
        },
    },
)
def transport_matrix(ctx: Context, distro_slug: str):
    """
    Generate the test matrix.
    """
    _matrix = []
    for transport in ("zeromq", "tcp"):
        if transport == "tcp":
            if distro_slug not in ("centosstream-9", "ubuntu-22.04-arm64"):
                # Only run TCP transport tests on these distributions
                continue
        _matrix.append({"transport": transport})
    print(json.dumps(_matrix))
    ctx.exit(0)
