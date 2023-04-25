"""
These commands are used in the CI pipeline.
"""
# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import json
import logging
import os
import pathlib
import time
from typing import TYPE_CHECKING

from ptscripts import Context, command_group

import tools.utils

log = logging.getLogger(__name__)

# Define the command group
ci = command_group(name="ci", help="CI Related Commands", description=__doc__)


@ci.command(
    name="print-gh-event",
)
def print_gh_event(ctx: Context):
    """
    Pretty print the GH Actions event.
    """
    gh_event_path = os.environ.get("GITHUB_EVENT_PATH") or None
    if gh_event_path is None:
        ctx.warn("The 'GITHUB_EVENT_PATH' variable is not set.")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert gh_event_path is not None

    try:
        gh_event = json.loads(open(gh_event_path).read())
    except Exception as exc:
        ctx.error(f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc)
        ctx.exit(1)

    ctx.info("GH Event Payload:")
    ctx.print(gh_event, soft_wrap=True)
    ctx.exit(0)


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
    Process changed files to avoid path traversal.
    """
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is None:
        ctx.warn("The 'GITHUB_OUTPUT' variable is not set.")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert github_output is not None

    if not changed_files.exists():
        ctx.error(f"The '{changed_files}' file does not exist.")
        ctx.exit(1)

    contents = changed_files.read_text()
    if not contents:
        if event_name == "pull_request":
            ctx.error(f"The '{changed_files}' file is empty.")
            ctx.exit(1)
        else:
            ctx.debug(f"The '{changed_files}' file is empty.")
            with open(github_output, "a", encoding="utf-8") as wfh:
                wfh.write(f"changed-files={json.dumps({})}\n")
            ctx.exit(0)

    try:
        changed_files_contents = json.loads(contents)
    except Exception as exc:
        ctx.error(f"Could not load the changed files from '{changed_files}': {exc}")
        ctx.exit(1)

    sanitized_changed_files = {}
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
                        tools.utils.REPO_ROOT.joinpath(entry)
                        .resolve()
                        .relative_to(tools.utils.REPO_ROOT)
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
    ctx.exit(0)


@ci.command(
    name="runner-types",
    arguments={
        "event_name": {
            "help": "The name of the GitHub event being processed.",
        },
    },
)
def runner_types(ctx: Context, event_name: str):
    """
    Set GH Actions 'runners' output to know what can run where.
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

    ctx.info("Selecting which type of runners(self hosted runners or not) to run")
    runners = {"github-hosted": False, "self-hosted": False}
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
            ctx.info("Writing 'runners' to the github outputs file")
            with open(github_output, "a", encoding="utf-8") as wfh:
                wfh.write(f"runners={json.dumps(runners)}\n")
            ctx.exit(0)

        # This is a PR from a forked repository
        ctx.info("Pull request is not comming from the same repository")
        runners["github-hosted"] = runners["self-hosted"] = True
        ctx.info("Writing 'runners' to the github outputs file")
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"runners={json.dumps(runners)}\n")
        ctx.exit(0)

    # This is a push or a scheduled event
    ctx.info(f"Running from a {event_name!r} event")
    if (
        gh_event["repository"]["fork"] is True
        and os.environ.get("FORK_HAS_SELF_HOSTED_RUNNERS", "0") == "1"
    ):
        # This is running on a forked repository, don't run tests
        ctx.info("The push event is on a forked repository")
        runners["github-hosted"] = True
        ctx.info("Writing 'runners' to the github outputs file")
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"runners={json.dumps(runners)}\n")
        ctx.exit(0)

    # Not running on a fork, or the fork has self hosted runners, run everything
    ctx.info(f"The {event_name!r} event is from the main repository")
    runners["github-hosted"] = runners["self-hosted"] = True
    ctx.info("Writing 'runners' to the github outputs file")
    with open(github_output, "a", encoding="utf-8") as wfh:
        wfh.write(f"runners={json.dumps(runners)}")
    ctx.exit(0)


@ci.command(
    name="define-jobs",
    arguments={
        "event_name": {
            "help": "The name of the GitHub event being processed.",
        },
        "skip_tests": {
            "help": "Skip running the Salt tests",
        },
        "skip_pkg_tests": {
            "help": "Skip running the Salt Package tests",
        },
        "skip_pkg_download_tests": {
            "help": "Skip running the Salt Package download tests",
        },
        "changed_files": {
            "help": (
                "Path to '.json' file containing the payload of changed files "
                "from the 'dorny/paths-filter' GitHub action."
            ),
        },
    },
)
def define_jobs(
    ctx: Context,
    event_name: str,
    changed_files: pathlib.Path,
    skip_tests: bool = False,
    skip_pkg_tests: bool = False,
    skip_pkg_download_tests: bool = False,
):
    """
    Set GH Actions 'jobs' output to know which jobs should run.
    """
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is None:
        ctx.warn("The 'GITHUB_OUTPUT' variable is not set.")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert github_output is not None

    github_step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_step_summary is None:
        ctx.warn("The 'GITHUB_STEP_SUMMARY' variable is not set.")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert github_step_summary is not None

    jobs = {
        "lint": True,
        "test": True,
        "test-pkg": True,
        "test-pkg-download": True,
        "prepare-release": True,
        "build-docs": True,
        "build-source-tarball": True,
        "build-deps-onedir": True,
        "build-salt-onedir": True,
        "build-pkgs": True,
    }

    if skip_tests:
        jobs["test"] = False
    if skip_pkg_tests:
        jobs["test-pkg"] = False
    if skip_pkg_download_tests:
        jobs["test-pkg-download"] = False

    if event_name != "pull_request":
        # In this case, all defined jobs should run
        ctx.info("Writing 'jobs' to the github outputs file")
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"jobs={json.dumps(jobs)}\n")

        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write(
                f"All defined jobs will run due to event type of `{event_name}`.\n"
            )
        return

    if not changed_files.exists():
        ctx.error(f"The '{changed_files}' file does not exist.")
        ctx.error(
            "FYI, the command 'tools process-changed-files <changed-files-path>' "
            "needs to run prior to this one."
        )
        ctx.exit(1)
    try:
        changed_files_contents = json.loads(changed_files.read_text())
    except Exception as exc:
        ctx.error(f"Could not load the changed files from '{changed_files}': {exc}")
        ctx.exit(1)

    # So, it's a pull request...
    # Based on which files changed, we can decide what jobs to run.
    required_lint_changes: set[str] = {
        changed_files_contents["salt"],
        changed_files_contents["tests"],
        changed_files_contents["lint"],
    }
    if required_lint_changes == {"false"}:
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write("De-selecting the 'lint' job.\n")
        jobs["lint"] = False

    required_docs_changes: set[str] = {
        changed_files_contents["salt"],
        changed_files_contents["docs"],
    }
    if required_docs_changes == {"false"}:
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write("De-selecting the 'build-docs' job.\n")
        jobs["build-docs"] = False

    required_test_changes: set[str] = {
        changed_files_contents["testrun"],
        changed_files_contents["workflows"],
        changed_files_contents["golden_images"],
    }
    if jobs["test"] and required_test_changes == {"false"}:
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write("De-selecting the 'test' job.\n")
        jobs["test"] = False

    required_pkg_test_changes: set[str] = {
        changed_files_contents["pkg_tests"],
        changed_files_contents["workflows"],
    }
    if jobs["test-pkg"] and required_pkg_test_changes == {"false"}:
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write("De-selecting the 'test-pkg' job.\n")
        jobs["test-pkg"] = False

    if jobs["test-pkg-download"] and required_pkg_test_changes == {"false"}:
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write("De-selecting the 'test-pkg-download' job.\n")
        jobs["test-pkg-download"] = False

    if not jobs["test"] and not jobs["test-pkg"] and not jobs["test-pkg-download"]:
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            for job in (
                "build-deps-onedir",
                "build-salt-onedir",
                "build-pkgs",
            ):
                wfh.write(f"De-selecting the '{job}' job.\n")
                jobs[job] = False
            if not jobs["build-docs"]:
                with open(github_step_summary, "a", encoding="utf-8") as wfh:
                    wfh.write("De-selecting the 'build-source-tarball' job.\n")
                jobs["build-source-tarball"] = False

    with open(github_step_summary, "a", encoding="utf-8") as wfh:
        wfh.write("Selected Jobs:\n")
        for name, value in sorted(jobs.items()):
            wfh.write(f" - {name}: {value}\n")

    ctx.info("Writing 'jobs' to the github outputs file")
    with open(github_output, "a", encoding="utf-8") as wfh:
        wfh.write(f"jobs={json.dumps(jobs)}\n")


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
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is None:
        ctx.warn("The 'GITHUB_OUTPUT' variable is not set.")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert github_output is not None

    github_step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_step_summary is None:
        ctx.warn("The 'GITHUB_STEP_SUMMARY' variable is not set.")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert github_step_summary is not None

    if event_name != "pull_request":
        # In this case, a full test run is in order
        ctx.info("Writing 'testrun' to the github outputs file")
        testrun = {"type": "full"}
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"testrun={json.dumps(testrun)}\n")

        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write(f"Full test run chosen due to event type of `{event_name}`.\n")
        return

    if not changed_files.exists():
        ctx.error(f"The '{changed_files}' file does not exist.")
        ctx.error(
            "FYI, the command 'tools process-changed-files <changed-files-path>' "
            "needs to run prior to this one."
        )
        ctx.exit(1)
    try:
        changed_files_contents = json.loads(changed_files.read_text())
    except Exception as exc:
        ctx.error(f"Could not load the changed files from '{changed_files}': {exc}")
        ctx.exit(1)

    # So, it's a pull request...
    # Based on which files changed, or other things like PR comments we can
    # decide what to run, or even if the full test run should be running on the
    # pull request, etc...
    changed_pkg_requirements_files = json.loads(
        changed_files_contents["pkg_requirements_files"]
    )
    changed_test_requirements_files = json.loads(
        changed_files_contents["test_requirements_files"]
    )
    if changed_files_contents["golden_images"] == "true":
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write(
                "Full test run chosen because there was a change made "
                "to `cicd/golden-images.json`.\n"
            )
        testrun = {"type": "full"}
    elif changed_pkg_requirements_files or changed_test_requirements_files:
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write(
                "Full test run chosen because there was a change made "
                "to the requirements files.\n"
            )
            wfh.write(
                "<details>\n<summary>Changed Requirements Files (click me)</summary>\n<pre>\n"
            )
            for path in sorted(
                changed_pkg_requirements_files + changed_test_requirements_files
            ):
                wfh.write(f"{path}\n")
            wfh.write("</pre>\n</details>\n")
        testrun = {"type": "full"}
    else:
        testrun_changed_files_path = tools.utils.REPO_ROOT / "testrun-changed-files.txt"
        testrun = {
            "type": "changed",
            "from-filenames": str(
                testrun_changed_files_path.relative_to(tools.utils.REPO_ROOT)
            ),
        }
        ctx.info(f"Writing {testrun_changed_files_path.name} ...")
        selected_changed_files = []
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
                        f"Full test run chosen because there was a change to `{fpath}`.\n"
                    )
            selected_changed_files.append(fpath)
        testrun_changed_files_path.write_text("\n".join(sorted(selected_changed_files)))
        if testrun["type"] == "changed":
            with open(github_step_summary, "a", encoding="utf-8") as wfh:
                wfh.write("Partial test run chosen.\n")
        if selected_changed_files:
            with open(github_step_summary, "a", encoding="utf-8") as wfh:
                wfh.write(
                    "<details>\n<summary>Selected Changed Files (click me)</summary>\n<pre>\n"
                )
                for path in sorted(selected_changed_files):
                    wfh.write(f"{path}\n")
                wfh.write("</pre>\n</details>\n")

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
            if distro_slug not in (
                "centosstream-9",
                "ubuntu-22.04",
                "ubuntu-22.04-arm64",
            ):
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
            if distro_slug not in (
                "centosstream-9",
                "ubuntu-22.04",
                "ubuntu-22.04-arm64",
            ):
                # Only run TCP transport tests on these distributions
                continue
        _matrix.append({"transport": transport})
    print(json.dumps(_matrix))
    ctx.exit(0)


@ci.command(
    name="pkg-matrix",
    arguments={
        "distro_slug": {
            "help": "The distribution slug to generate the matrix for",
        },
        "pkg_type": {
            "help": "The distribution slug to generate the matrix for",
        },
    },
)
def pkg_matrix(ctx: Context, distro_slug: str, pkg_type: str):
    """
    Generate the test matrix.
    """
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is None:
        ctx.warn("The 'GITHUB_OUTPUT' variable is not set.")

    matrix = []
    sessions = [
        "install",
    ]
    if (
        distro_slug
        not in [
            "debian-11-arm64",
            "ubuntu-20.04-arm64",
            "ubuntu-22.04-arm64",
            "photonos-3",
            "photonos-4",
        ]
        and pkg_type != "MSI"
    ):
        # These OS's never had arm64 packages built for them
        # with the tiamate onedir packages.
        # we will need to ensure when we release 3006.0
        # we allow for 3006.0 jobs to run, because then
        # we will have arm64 onedir packages to upgrade from
        sessions.append("upgrade")
    if (
        distro_slug
        not in [
            "centosstream-9",
            "ubuntu-22.04",
            "ubuntu-22.04-arm64",
            "photonos-3",
            "photonos-4",
        ]
        and pkg_type != "MSI"
    ):
        # Packages for these OSs where never built for classic previously
        sessions.append("upgrade-classic")

    for session in sessions:
        matrix.append(
            {
                "test-chunk": session,
            }
        )
    ctx.info("Generated matrix:")
    ctx.print(matrix, soft_wrap=True)

    if github_output is not None:
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"matrix={json.dumps(matrix)}\n")
    ctx.exit(0)


@ci.command(
    name="get-releases",
    arguments={
        "repository": {
            "help": "The repository to query for releases, e.g. saltstack/salt",
        },
    },
)
def get_releases(ctx: Context, repository: str = "saltstack/salt"):
    """
    Generate the latest salt release.
    """
    github_output = os.environ.get("GITHUB_OUTPUT")

    if github_output is None:
        ctx.exit(1, "The 'GITHUB_OUTPUT' variable is not set.")
    else:
        releases = tools.utils.get_salt_releases(ctx, repository)
        str_releases = [str(version) for version in releases]
        latest = str_releases[-1]

        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"latest-release={latest}\n")
            wfh.write(f"releases={json.dumps(str_releases)}\n")
        ctx.exit(0)
