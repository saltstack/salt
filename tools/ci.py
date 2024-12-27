"""
These commands are used in the CI pipeline.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import json
import logging
import os
import pathlib
import random
import shutil
import sys
import time
from typing import TYPE_CHECKING, Any

import yaml
from ptscripts import Context, command_group

import tools.utils
import tools.utils.gh
from tools.precommit.workflows import TEST_SALT_LISTING

if sys.version_info < (3, 11):
    from typing_extensions import NotRequired, TypedDict
else:
    from typing import NotRequired, TypedDict  # pylint: disable=no-name-in-module

try:
    import boto3
except ImportError:
    print(
        "\nPlease run 'python -m pip install -r "
        "requirements/static/ci/py{}.{}/tools.txt'\n".format(*sys.version_info),
        file=sys.stderr,
        flush=True,
    )
    raise

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
        gh_event = json.loads(open(gh_event_path, encoding="utf-8").read())
    except Exception as exc:
        ctx.error(f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc)  # type: ignore[arg-type]
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
        gh_event = json.loads(open(gh_event_path, encoding="utf-8").read())
    except Exception as exc:
        ctx.error(f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc)  # type: ignore[arg-type]
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
            ctx.info("Writing 'runners' to the github outputs file:\n", runners)
            with open(github_output, "a", encoding="utf-8") as wfh:
                wfh.write(f"runners={json.dumps(runners)}\n")
            ctx.exit(0)

        # This is a PR from a forked repository
        ctx.info("Pull request is not comming from the same repository")
        runners["github-hosted"] = runners["self-hosted"] = True
        ctx.info("Writing 'runners' to the github outputs file:\n", runners)
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
        ctx.info("Writing 'runners' to the github outputs file:\n", runners)
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"runners={json.dumps(runners)}\n")
        ctx.exit(0)

    # Not running on a fork, or the fork has self hosted runners, run everything
    ctx.info(f"The {event_name!r} event is from the main repository")
    runners["github-hosted"] = runners["self-hosted"] = True
    ctx.info("Writing 'runners' to the github outputs file:\n", runners)
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
        "build-deps-ci": True,
    }

    if skip_tests:
        jobs["test"] = False
    if skip_pkg_tests:
        jobs["test-pkg"] = False
    if skip_pkg_download_tests:
        jobs["test-pkg-download"] = False

    if event_name != "pull_request":
        # In this case, all defined jobs should run
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write("Selected Jobs:\n")
            for name, value in sorted(jobs.items()):
                wfh.write(f" - `{name}`: {value}\n")

        ctx.info("Writing 'jobs' to the github outputs file")
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"jobs={json.dumps(jobs)}\n")

        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write(
                f"All defined jobs will run due to event type of `{event_name}`.\n"
            )
        return

    # This is a pull-request

    labels: list[str] = []
    gh_event_path = os.environ.get("GITHUB_EVENT_PATH") or None
    if gh_event_path is not None:
        try:
            gh_event = json.loads(open(gh_event_path, encoding="utf-8").read())
        except Exception as exc:
            ctx.error(
                f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc  # type: ignore[arg-type]
            )
            ctx.exit(1)

        labels.extend(
            label[0] for label in _get_pr_test_labels_from_event_payload(gh_event)
        )

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
        changed_files_contents["golden_images"],
    }
    if jobs["test-pkg"] and required_pkg_test_changes == {"false"}:
        if "test:pkg" in labels:
            with open(github_step_summary, "a", encoding="utf-8") as wfh:
                wfh.write(
                    "The 'test-pkg' job is forcefully selected by the use of the 'test:pkg' label.\n"
                )
            jobs["test-pkg"] = True
        else:
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
                "build-deps-ci",
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
            wfh.write(f" - `{name}`: {value}\n")

    ctx.info("Writing 'jobs' to the github outputs file")
    with open(github_output, "a", encoding="utf-8") as wfh:
        wfh.write(f"jobs={json.dumps(jobs)}\n")


class TestRun(TypedDict):
    type: str
    skip_code_coverage: bool
    from_filenames: NotRequired[str]
    selected_tests: NotRequired[dict[str, bool]]


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

    labels: list[str] = []
    gh_event_path = os.environ.get("GITHUB_EVENT_PATH") or None
    if gh_event_path is not None:
        try:
            gh_event = json.loads(open(gh_event_path, encoding="utf-8").read())
        except Exception as exc:
            ctx.error(
                f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc  # type: ignore[arg-type]
            )
            ctx.exit(1)

        labels.extend(
            label[0] for label in _get_pr_test_labels_from_event_payload(gh_event)
        )

    if "test:coverage" in labels:
        ctx.info("Writing 'testrun' to the github outputs file")
        testrun = TestRun(type="full", skip_code_coverage=False)
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"testrun={json.dumps(testrun)}\n")
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write(
                "Full test run chosen because the label `test:coverage` is set.\n"
            )
        return
    elif event_name != "pull_request":
        # In this case, a full test run is in order
        ctx.info("Writing 'testrun' to the github outputs file")
        testrun = TestRun(type="full", skip_code_coverage=False)
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"testrun={json.dumps(testrun)}\n")

        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write(f"Full test run chosen due to event type of `{event_name}`.\n")
        return

    # So, it's a pull request...

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

    # Based on which files changed, or other things like PR labels we can
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
        testrun = TestRun(type="full", skip_code_coverage=True)
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
        testrun = TestRun(type="full", skip_code_coverage=True)
    elif "test:full" in labels:
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write("Full test run chosen because the label `test:full` is set.\n")
        testrun = TestRun(type="full", skip_code_coverage=True)
    else:
        testrun_changed_files_path = tools.utils.REPO_ROOT / "testrun-changed-files.txt"
        testrun = TestRun(
            type="changed",
            skip_code_coverage=True,
            from_filenames=str(
                testrun_changed_files_path.relative_to(tools.utils.REPO_ROOT)
            ),
        )
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
            testrun["selected_tests"] = {
                "core": False,
                "slow": False,
                "fast": True,
                "flaky": False,
            }
            if "test:slow" in labels:
                with open(github_step_summary, "a", encoding="utf-8") as wfh:
                    wfh.write("Slow tests chosen by `test:slow` label.\n")
                testrun["selected_tests"]["slow"] = True
            if "test:core" in labels:
                with open(github_step_summary, "a", encoding="utf-8") as wfh:
                    wfh.write("Core tests chosen by `test:core` label.\n")
                testrun["selected_tests"]["core"] = True
            if "test:no-fast" in labels:
                with open(github_step_summary, "a", encoding="utf-8") as wfh:
                    wfh.write("Fast tests deselected by `test:no-fast` label.\n")
                testrun["selected_tests"]["fast"] = False
            if "test:flaky-jail" in labels:
                with open(github_step_summary, "a", encoding="utf-8") as wfh:
                    wfh.write("Flaky jailed tests chosen by `test:flaky-jail` label.\n")
                testrun["selected_tests"]["flaky"] = True
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

    ctx.info("Writing 'testrun' to the github outputs file:\n", testrun)
    with open(github_output, "a", encoding="utf-8") as wfh:
        wfh.write(f"testrun={json.dumps(testrun)}\n")


@ci.command(
    arguments={
        "distro_slug": {
            "help": "The distribution slug to generate the matrix for",
        },
        "full": {
            "help": "Full test run",
        },
        "workflow": {
            "help": "Which workflow is running",
        },
    },
)
def matrix(
    ctx: Context,
    distro_slug: str,
    full: bool = False,
    workflow: str = "ci",
):
    """
    Generate the test matrix.
    """
    gh_event_path = os.environ.get("GITHUB_EVENT_PATH") or None
    if gh_event_path is None:
        ctx.warn("The 'GITHUB_EVENT_PATH' variable is not set.")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert gh_event_path is not None

    gh_event = None
    try:
        gh_event = json.loads(open(gh_event_path, encoding="utf-8").read())
    except Exception as exc:
        ctx.error(f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc)
        ctx.exit(1)

    if TYPE_CHECKING:
        assert gh_event is not None

    _matrix = []
    _splits = {
        "functional": 4,
        "integration": 7,
        "scenarios": 1,
        "unit": 4,
    }
    for transport in ("zeromq", "tcp"):
        if transport == "tcp":
            if distro_slug not in (
                "rockylinux-9",
                "rockylinux-9-arm64",
                "photonos-5",
                "photonos-5-arm64",
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
            splits = _splits.get(chunk) or 1
            if full and splits > 1:
                for split in range(1, splits + 1):
                    _matrix.append(
                        {
                            "transport": transport,
                            "tests-chunk": chunk,
                            "test-group": split,
                            "test-group-count": splits,
                        }
                    )
            else:
                _matrix.append({"transport": transport, "tests-chunk": chunk})

    ctx.info("Generated matrix:")
    if not _matrix:
        ctx.print(" * `None`")
    else:
        for entry in _matrix:
            ctx.print(" * ", entry, soft_wrap=True)

    if (
        gh_event["repository"]["fork"] is True
        and "macos" in distro_slug
        and "arm64" in distro_slug
    ):
        ctx.warn("Forks don't have access to MacOS 13 Arm64. Clearning the matrix.")
        _matrix.clear()

    if not _matrix:
        build_reports = False
        ctx.info("Not building reports because the matrix is empty")
    else:
        build_reports = True

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is not None:
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"matrix={json.dumps(_matrix)}\n")
            wfh.write(f"build-reports={json.dumps(build_reports)}\n")
    ctx.exit(0)


@ci.command(
    name="pkg-matrix",
    arguments={
        "distro_slug": {
            "help": "The distribution slug to generate the matrix for",
        },
        "pkg_type": {
            "help": "The type of package we are testing against",
        },
        "testing_releases": {
            "help": "The salt releases to test upgrades against",
            "nargs": "+",
            "required": True,
        },
    },
)
def pkg_matrix(
    ctx: Context,
    distro_slug: str,
    pkg_type: str,
    testing_releases: list[tools.utils.Version] = None,
):
    """
    Generate the test matrix.
    """
    gh_event = None
    gh_event_path = os.environ.get("GITHUB_EVENT_PATH") or None
    if gh_event_path is None:
        ctx.warn("The 'GITHUB_EVENT_PATH' variable is not set.")
    else:
        try:
            gh_event = json.loads(open(gh_event_path, encoding="utf-8").read())
        except Exception as exc:
            ctx.error(
                f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc
            )

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is None:
        ctx.warn("The 'GITHUB_OUTPUT' variable is not set.")

    if TYPE_CHECKING:
        assert testing_releases

    still_testing_3005 = False
    for release_version in testing_releases:
        if still_testing_3005:
            break
        if release_version < tools.utils.Version("3006.0"):
            still_testing_3005 = True

    if still_testing_3005 is False:
        ctx.error(
            f"No longer testing 3005.x releases please update {__file__} "
            "and remove this error and the logic above the error. There may "
            "be other places that need code removed as well."
        )
        ctx.exit(1)

    adjusted_versions = []
    for ver in testing_releases:
        if ver < tools.utils.Version("3006.0"):
            adjusted_versions.append((ver, "classic"))
            adjusted_versions.append((ver, "tiamat"))
        else:
            adjusted_versions.append((ver, "relenv"))
    ctx.info(f"Will look for the following versions: {adjusted_versions}")

    # Filter out the prefixes to look under
    if "macos-" in distro_slug:
        # We don't have golden images for macos, handle these separately
        prefixes = {
            "classic": "osx/",
            "tiamat": "salt/py3/macos/minor/",
            "relenv": "salt/py3/macos/minor/",
        }
    else:
        parts = distro_slug.split("-")
        name = parts[0]
        version = parts[1]

        if len(parts) > 2:
            arch = parts[2]
        elif name in ("debian", "ubuntu"):
            arch = "amd64"
        else:
            arch = "x86_64"

        if name == "amazonlinux":
            name = "amazon"
        elif name == "rockylinux":
            name = "redhat"
        elif "photon" in name:
            name = "photon"

        if name == "windows":
            prefixes = {
                "classic": "windows/",
                "tiamat": "salt/py3/windows/minor",
                "relenv": "salt/py3/windows/minor",
            }
        else:
            prefixes = {
                "classic": f"py3/{name}/{version}/{arch}/",
                "tiamat": f"salt/py3/{name}/{version}/{arch}/minor/",
                "relenv": f"salt/py3/{name}/{version}/{arch}/minor/",
            }

    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    _matrix = [
        {
            "tests-chunk": "install",
            "version": None,
        }
    ]

    for version, backend in adjusted_versions:
        if (
            distro_slug.startswith(("macos-", "debian-", "ubuntu-"))
            or version.major < 3006
        ):
            # XXX: Temporarily skip problematic tests
            ctx.warn(
                f"Temporary skip builds on {distro_slug} for version {version} with backend {backend}"
            )
            continue

        prefix = prefixes[backend]
        # TODO: Remove this after 3009.0
        if backend == "relenv" and version >= tools.utils.Version("3006.5"):
            prefix.replace("/arm64/", "/aarch64/")
        # Using a paginator allows us to list recursively and avoid the item limit
        page_iterator = paginator.paginate(
            Bucket=f"salt-project-{tools.utils.SPB_ENVIRONMENT}-salt-artifacts-release",
            Prefix=prefix,
        )
        # Uses a jmespath expression to test if the wanted version is in any of the filenames
        key_filter = f"Contents[?contains(Key, '{version}')][]"
        if pkg_type == "MSI":
            # TODO: Add this back when we add MSI upgrade and downgrade tests
            # key_filter = f"Contents[?contains(Key, '{version}')] | [?ends_with(Key, '.msi')]"
            continue
        elif pkg_type == "NSIS":
            # XXX: Temporarily skip problematic tests
            # key_filter = (
            #    f"Contents[?contains(Key, '{version}')] | [?ends_with(Key, '.exe')]"
            # )
            continue
        objects = list(page_iterator.search(key_filter))
        # Testing using `any` because sometimes the paginator returns `[None]`
        if any(objects):
            ctx.info(
                f"Found {version} ({backend}) for {distro_slug}: {objects[0]['Key']}"
            )
            for session in ("upgrade", "downgrade"):
                if session == "downgrade" and distro_slug.startswith(
                    ("rockylinux", "amazonlinux", "centos")
                ):
                    # XXX: Temporarily skip problematic tests
                    ctx.warn(
                        f"Temporary skip {session} builds on {distro_slug} for version {version} "
                        f"with backend {backend}"
                    )
                    continue
                if backend == "classic":
                    session += "-classic"
                _matrix.append(
                    {
                        "tests-chunk": session,
                        "version": str(version),
                    }
                )
        else:
            ctx.info(f"No {version} ({backend}) for {distro_slug} at {prefix}")

    ctx.info("Generated matrix:")
    if not _matrix:
        ctx.print(" * `None`")
    else:
        for entry in _matrix:
            ctx.print(" * ", entry, soft_wrap=True)

    if (
        gh_event is not None
        and gh_event["repository"]["fork"] is True
        and "macos" in distro_slug
        and "arm64" in distro_slug
    ):
        ctx.warn("Forks don't have access to MacOS 13 Arm64. Clearning the matrix.")
        _matrix.clear()

    if not _matrix:
        build_reports = False
        ctx.info("Not building reports because the matrix is empty")
    else:
        build_reports = True

    if github_output is not None:
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"matrix={json.dumps(_matrix)}\n")
            wfh.write(f"build-reports={json.dumps(build_reports)}\n")
    ctx.exit(0)


@ci.command(name="deps-matrix")
def get_ci_deps_matrix(ctx: Context):
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

    gh_event = None
    try:
        gh_event = json.loads(open(gh_event_path, encoding="utf-8").read())
    except Exception as exc:
        ctx.error(f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc)
        ctx.exit(1)

    if TYPE_CHECKING:
        assert gh_event is not None

    _matrix = {
        "linux": [
            {"distro-slug": "amazonlinux-2", "arch": "x86_64"},
            {"distro-slug": "amazonlinux-2-arm64", "arch": "arm64"},
        ],
        "macos": [
            {"distro-slug": "macos-12", "arch": "x86_64"},
        ],
        "windows": [
            {"distro-slug": "windows-2022", "arch": "amd64"},
        ],
    }
    if gh_event["repository"]["fork"] is not True:
        _matrix["macos"].append(
            {
                "distro-slug": "macos-13-arm64",
                "arch": "arm64",
            }
        )

    ctx.info("Generated matrix:")
    ctx.print(_matrix, soft_wrap=True)

    if github_output is not None:
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"matrix={json.dumps(_matrix)}\n")
    ctx.exit(0)


@ci.command(name="pkg-downloads-matrix")
def get_pkg_downloads_matrix(ctx: Context):
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

    gh_event = None
    try:
        gh_event = json.loads(open(gh_event_path, encoding="utf-8").read())
    except Exception as exc:
        ctx.error(f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc)
        ctx.exit(1)

    if TYPE_CHECKING:
        assert gh_event is not None

    _matrix: dict[str, list[dict[str, str]]] = {
        "linux": [],
        "macos": [],
        "windows": [],
    }

    rpm_slugs = (
        "rockylinux",
        "amazonlinux",
        "fedora",
        "photon",
    )
    linux_skip_pkg_download_tests = (
        "archlinux-lts",
        "opensuse-15",
        "windows",
    )
    for slug in sorted(tools.utils.get_golden_images()):
        if slug.startswith(linux_skip_pkg_download_tests):
            continue
        if "arm64" in slug:
            arch = "arm64"
        else:
            arch = "x86_64"
        if slug.startswith(rpm_slugs) and arch == "arm64":
            # While we maintain backwards compatible urls
            _matrix["linux"].append(
                {"distro-slug": slug, "arch": "aarch64", "pkg-type": "package"}
            )
        _matrix["linux"].append(
            {"distro-slug": slug, "arch": arch, "pkg-type": "package"}
        )
        if slug.startswith("ubuntu-22"):
            _matrix["linux"].append(
                {"distro-slug": slug, "arch": arch, "pkg-type": "onedir"}
            )
    for mac in TEST_SALT_LISTING["macos"]:
        if gh_event["repository"]["fork"] is True and mac.arch == "arm64":
            continue
        _matrix["macos"].append(
            {"distro-slug": mac.slug, "arch": mac.arch, "pkg-type": "package"}
        )

    if gh_event["repository"]["fork"] is True:
        macos_idx = 0  # macos-12
    else:
        macos_idx = 1  # macos-13
    _matrix["macos"].append(
        {
            "distro-slug": TEST_SALT_LISTING["macos"][macos_idx].slug,
            "arch": TEST_SALT_LISTING["macos"][macos_idx].arch,
            "pkg-type": "onedir",
        }
    )

    for win in TEST_SALT_LISTING["windows"][-1:]:
        for pkg_type in ("nsis", "msi", "onedir"):
            _matrix["windows"].append(
                {
                    "distro-slug": win.slug,
                    "arch": win.arch,
                    "pkg-type": pkg_type,
                }
            )

    ctx.info("Generated matrix:")
    ctx.print(_matrix, soft_wrap=True)

    if github_output is not None:
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"matrix={json.dumps(_matrix)}\n")
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
    releases = tools.utils.get_salt_releases(ctx, repository)
    str_releases = [str(version) for version in releases]
    latest = str_releases[-1]

    ctx.info("Releases:", sorted(str_releases))
    ctx.info(f"Latest Release: '{latest}'")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is not None:
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"latest-release={latest}\n")
            wfh.write(f"releases={json.dumps(str_releases)}\n")
        ctx.exit(0)


@ci.command(
    name="get-release-changelog-target",
    arguments={
        "event_name": {
            "help": "The name of the GitHub event being processed.",
        },
    },
)
def get_release_changelog_target(ctx: Context, event_name: str):
    """
    Define which kind of release notes should be generated, next minor or major.
    """
    gh_event_path = os.environ.get("GITHUB_EVENT_PATH") or None
    if gh_event_path is None:
        ctx.warn("The 'GITHUB_EVENT_PATH' variable is not set.")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert gh_event_path is not None

    try:
        gh_event = json.loads(open(gh_event_path, encoding="utf-8").read())
    except Exception as exc:
        ctx.error(f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc)  # type: ignore[arg-type]
        ctx.exit(1)

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is None:
        ctx.warn("The 'GITHUB_OUTPUT' variable is not set.")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert github_output is not None

    shared_context = yaml.safe_load(
        tools.utils.SHARED_WORKFLOW_CONTEXT_FILEPATH.read_text()
    )
    release_branches = shared_context["release_branches"]

    release_changelog_target = "next-major-release"
    if event_name == "pull_request":
        if gh_event["pull_request"]["base"]["ref"] in release_branches:
            release_changelog_target = "next-minor-release"
    elif event_name == "schedule":
        branch_name = gh_event["repository"]["default_branch"]
        if branch_name in release_branches:
            release_changelog_target = "next-minor-release"
    else:
        for branch_name in release_branches:
            if branch_name in gh_event["ref"]:
                release_changelog_target = "next-minor-release"
                break
    with open(github_output, "a", encoding="utf-8") as wfh:
        wfh.write(f"release-changelog-target={release_changelog_target}\n")
    ctx.exit(0)


@ci.command(
    name="get-pr-test-labels",
    arguments={
        "pr": {
            "help": "Pull request number",
        },
        "repository": {
            "help": "Github repository.",
        },
    },
)
def get_pr_test_labels(
    ctx: Context, repository: str = "saltstack/salt", pr: int = None
):
    """
    Set the pull-request labels.
    """
    github_step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    gh_event_path = os.environ.get("GITHUB_EVENT_PATH") or None
    if gh_event_path is None:
        labels = _get_pr_test_labels_from_api(ctx, repository, pr=pr)
    else:
        if TYPE_CHECKING:
            assert gh_event_path is not None

        try:
            gh_event = json.loads(open(gh_event_path, encoding="utf-8").read())
        except Exception as exc:
            ctx.error(
                f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc  # type: ignore[arg-type]
            )
            ctx.exit(1)

        if "pull_request" not in gh_event:
            ctx.warn("The 'pull_request' key was not found on the event payload.")
            ctx.exit(1)

        pr = gh_event["pull_request"]["number"]
        labels = _get_pr_test_labels_from_event_payload(gh_event)

    shared_context = tools.utils.get_cicd_shared_context()
    mandatory_os_slugs = set(shared_context["mandatory_os_slugs"])
    available = set(tools.utils.get_golden_images())
    # Add MacOS provided by GitHub
    available.update({"macos-12", "macos-13", "macos-13-arm64"})
    # Remove mandatory OS'ss
    available.difference_update(mandatory_os_slugs)
    select_all = set(available)
    selected = set()
    test_labels = []
    if labels:
        ctx.info(f"Test labels for pull-request #{pr} on {repository}:")
        for name, description in sorted(labels):
            ctx.info(
                f" * [yellow]{name}[/yellow]: {description or '[red][No description][/red]'}"
            )
            if name.startswith("test:os:"):
                slug = name.split("test:os:", 1)[-1]
                if slug not in available and name != "test:os:all":
                    ctx.warn(
                        f"The '{slug}' slug exists as a label but not as an available OS."
                    )
                selected.add(slug)
                if slug != "all":
                    available.remove(slug)
                continue
            test_labels.append(name)

    else:
        ctx.info(f"No test labels for pull-request #{pr} on {repository}")

    if "test:coverage" in test_labels:
        ctx.info(
            "Selecting ALL available OS'es because the label 'test:coverage' is set."
        )
        selected.add("all")
        if github_step_summary is not None:
            with open(github_step_summary, "a", encoding="utf-8") as wfh:
                wfh.write(
                    "Selecting ALL available OS'es because the label `test:coverage` is set.\n"
                )

    if "all" in selected:
        selected = select_all
        available.clear()

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is None:
        ctx.exit(0)

    if TYPE_CHECKING:
        assert github_output is not None

    ctx.info("Writing 'labels' to the github outputs file...")
    ctx.info("Test Labels:")
    if not test_labels:
        ctx.info(" * None")
    else:
        for label in sorted(test_labels):
            ctx.info(f" * [yellow]{label}[/yellow]")
    ctx.info("* OS Labels:")
    if not selected:
        ctx.info(" * None")
    else:
        for slug in sorted(selected):
            ctx.info(f" * [yellow]{slug}[/yellow]")
    with open(github_output, "a", encoding="utf-8") as wfh:
        wfh.write(f"os-labels={json.dumps([label for label in selected])}\n")
        wfh.write(f"test-labels={json.dumps([label for label in test_labels])}\n")

    github_step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_step_summary is not None:
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write("Mandatory OS Test Runs:\n")
            for slug in sorted(mandatory_os_slugs):
                wfh.write(f"* `{slug}`\n")

            wfh.write("\nOptional OS Test Runs(selected by label):\n")
            if not selected:
                wfh.write("* None\n")
            else:
                for slug in sorted(selected):
                    wfh.write(f"* `{slug}`\n")

            wfh.write("\nSkipped OS Tests Runs(NOT selected by label):\n")
            if not available:
                wfh.write("* None\n")
            else:
                for slug in sorted(available):
                    wfh.write(f"* `{slug}`\n")

    ctx.exit(0)


def _get_pr_test_labels_from_api(
    ctx: Context, repository: str = "saltstack/salt", pr: int = None
) -> list[tuple[str, str]]:
    """
    Set the pull-request labels.
    """
    if pr is None:
        ctx.error(
            "Could not find the 'GITHUB_EVENT_PATH' variable and the "
            "--pr flag was not passed. Unable to detect pull-request number."
        )
        ctx.exit(1)
    with ctx.web as web:
        headers = {
            "Accept": "application/vnd.github+json",
        }
        github_token = tools.utils.gh.get_github_token(ctx)
        if github_token is not None:
            headers["Authorization"] = f"Bearer {github_token}"
        web.headers.update(headers)
        ret = web.get(f"https://api.github.com/repos/{repository}/pulls/{pr}")
        if ret.status_code != 200:
            ctx.error(
                f"Failed to get the #{pr} pull-request details on repository {repository!r}: {ret.reason}"
            )
            ctx.exit(1)
        pr_details = ret.json()
        return _filter_test_labels(pr_details["labels"])


def _get_pr_test_labels_from_event_payload(
    gh_event: dict[str, Any]
) -> list[tuple[str, str]]:
    """
    Get the pull-request test labels.
    """
    if "pull_request" not in gh_event:
        return []
    return _filter_test_labels(gh_event["pull_request"]["labels"])


def _filter_test_labels(labels: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [
        (label["name"], label["description"])
        for label in labels
        if label["name"].startswith("test:")
    ]


@ci.command(
    name="get-testing-releases",
    arguments={
        "releases": {
            "help": "The list of releases of salt",
            "nargs": "*",
        },
        "salt_version": {
            "help": "The version of salt being tested against",
            "required": True,
        },
    },
)
def get_testing_releases(
    ctx: Context,
    releases: list[tools.utils.Version],
    salt_version: str = None,
):
    """
    Get a list of releases to use for the upgrade and downgrade tests.
    """
    parsed_salt_version = tools.utils.Version(salt_version)
    # We want the latest 4 major versions, removing the oldest if this version is a new major
    num_major_versions = 4
    if parsed_salt_version.minor == 0:
        num_major_versions = 3
    majors = sorted(
        list(
            {
                version.major
                for version in releases
                # We aren't testing upgrades from anything before
                # 3006.0 except the latest 3005.x
                if version.major >= 3005
                # We don't want to test 3007.? on the 3006.x branch
                and version.major <= parsed_salt_version.major
            }
        )
    )[-num_major_versions:]
    testing_releases = []
    # Append the latest minor for each major
    for major in majors:
        minors_of_major = [version for version in releases if version.major == major]
        testing_releases.append(minors_of_major[-1])

    str_releases = [str(version) for version in testing_releases]

    ctx.info("Testing Releases:", sorted(str_releases))

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is not None:
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"testing-releases={json.dumps(str_releases)}\n")

    ctx.exit(0)


@ci.command(
    name="define-cache-seed",
    arguments={
        "static_cache_seed": {
            "help": "The static cache seed value",
        },
        "randomize": {
            "help": "Randomize the cache seed value",
        },
    },
)
def define_cache_seed(ctx: Context, static_cache_seed: str, randomize: bool = False):
    """
    Set `cache-seed` in GH Actions outputs.
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

    labels: list[str] = []
    gh_event_path = os.environ.get("GITHUB_EVENT_PATH") or None
    if gh_event_path is not None:
        try:
            gh_event = json.loads(open(gh_event_path, encoding="utf-8").read())
        except Exception as exc:
            ctx.error(
                f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc  # type: ignore[arg-type]
            )
            ctx.exit(1)

        labels.extend(
            label[0] for label in _get_pr_test_labels_from_event_payload(gh_event)
        )

    if randomize is True:
        cache_seed = f"SEED-{random.randint(100, 1000)}"
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write(
                f"The cache seed has been randomized to `{cache_seed}` because "
                "`--randomize` was passed to `tools ci define-cache-seed`."
            )
    elif "test:random-cache-seed" in labels:
        cache_seed = f"SEED-{random.randint(100, 1000)}"
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write(
                f"The cache seed has been randomized to `{cache_seed}` because "
                "the label `test:random-cache-seed` was set."
            )
    else:
        cache_seed = static_cache_seed

    ctx.info("Writing 'cache-seed' to the github outputs file")
    with open(github_output, "a", encoding="utf-8") as wfh:
        wfh.write(f"cache-seed={cache_seed}\n")


@ci.command(
    name="upload-coverage",
    arguments={
        "commit_sha": {
            "help": "The commit SHA",
            "required": True,
        },
        "reports_path": {
            "help": "The path to the directory containing the XML Coverage Reports",
        },
    },
)
def upload_coverage(ctx: Context, reports_path: pathlib.Path, commit_sha: str = None):
    """
    Upload code coverage to codecov.
    """
    codecov = shutil.which("codecov")
    if not codecov:
        ctx.error("Could not find the path to the 'codecov' binary")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert commit_sha is not None

    codecov_args: list[str] = [
        codecov,
        "--nonZero",
        "--sha",
        commit_sha,
    ]

    from_pull_request = False

    gh_event_path = os.environ.get("GITHUB_EVENT_PATH") or None
    if gh_event_path is not None:
        try:
            gh_event = json.loads(open(gh_event_path, encoding="utf-8").read())
            pr_event_data = gh_event.get("pull_request")
            if pr_event_data:
                from_pull_request = True
                codecov_args.extend(["--parent", pr_event_data["base"]["sha"]])
        except Exception as exc:
            ctx.error(
                f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc  # type: ignore[arg-type]
            )

    sleep_time = 15
    for fpath in reports_path.glob("*.xml"):
        if fpath.name in ("salt.xml", "tests.xml"):
            flags = fpath.stem
        else:
            try:
                section, distro_slug, _, _ = fpath.stem.split("..")
                fips = ",fips"
            except ValueError:
                fips = ""
                try:
                    section, distro_slug, _ = fpath.stem.split("..")
                except ValueError:
                    ctx.error(
                        f"The file {fpath} does not respect the expected naming convention "
                        "'{salt|tests}..<distro-slug>..<nox-session>.xml'. Skipping..."
                    )
                    continue
            flags = f"{section},{distro_slug}{fips}"

        max_attempts = 3
        current_attempt = 0
        while True:
            current_attempt += 1
            ctx.info(
                f"Uploading '{fpath}' coverage report to codecov (attempt {current_attempt} of {max_attempts}) ..."
            )

            ret = ctx.run(
                *codecov_args,
                "--file",
                str(fpath),
                "--name",
                fpath.stem,
                "--flags",
                flags,
                check=False,
                capture=True,
            )
            stdout = ret.stdout.strip().decode()
            stderr = ret.stderr.strip().decode()
            if ret.returncode == 0:
                ctx.console_stdout.print(stdout)
                ctx.console.print(stderr)
                break

            if (
                "Too many uploads to this commit" in stdout
                or "Too many uploads to this commit" in stderr
            ):
                # Let's just stop trying
                ctx.console_stdout.print(stdout)
                ctx.console.print(stderr)
                break

            if current_attempt >= max_attempts:
                ctx.error(f"Failed to upload {fpath} to codecov:")
                ctx.console_stdout.print(stdout)
                ctx.console.print(stderr)
                if from_pull_request is True:
                    # Codecov is having some issues with tokenless uploads
                    # Don't let PR's fail, but do fail otherwise so we know
                    # we should fix it.
                    github_step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
                    if github_step_summary is not None:
                        with open(github_step_summary, "a", encoding="utf-8") as wfh:
                            wfh.write(f"Failed to upload `{fpath}` to codecov\n")
                    ctx.exit(0)
                ctx.exit(1)

            ctx.warn(f"Waiting {sleep_time} seconds until next retry...")
            time.sleep(sleep_time)

    ctx.exit(0)
