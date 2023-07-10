"""
These commands are used in the CI pipeline.
"""
# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import json
import logging
import os
import pathlib
import sys
import time
from typing import TYPE_CHECKING, Any

import yaml
from ptscripts import Context, command_group

import tools.utils

if sys.version_info < (3, 11):
    from typing_extensions import NotRequired, TypedDict
else:
    from typing import NotRequired, TypedDict  # pylint: disable=no-name-in-module

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

    # This is a pull-request

    labels: list[str] = []
    gh_event_path = os.environ.get("GITHUB_EVENT_PATH") or None
    if gh_event_path is not None:
        try:
            gh_event = json.loads(open(gh_event_path).read())
        except Exception as exc:
            ctx.error(
                f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc
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
            gh_event = json.loads(open(gh_event_path).read())
        except Exception as exc:
            ctx.error(
                f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc
            )
            ctx.exit(1)

        labels.extend(
            label[0] for label in _get_pr_test_labels_from_event_payload(gh_event)
        )

    skip_code_coverage = True
    if "test:coverage" in labels:
        skip_code_coverage = False
    elif event_name != "pull_request":
        skip_code_coverage = False

    if event_name != "pull_request":
        # In this case, a full test run is in order
        ctx.info("Writing 'testrun' to the github outputs file")
        testrun = TestRun(type="full", skip_code_coverage=skip_code_coverage)
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
        testrun = TestRun(type="full", skip_code_coverage=skip_code_coverage)
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
        testrun = TestRun(type="full", skip_code_coverage=skip_code_coverage)
    elif "test:full" in labels:
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write("Full test run chosen because the label `test:full` is set.\n")
        testrun = TestRun(type="full", skip_code_coverage=skip_code_coverage)
    else:
        testrun_changed_files_path = tools.utils.REPO_ROOT / "testrun-changed-files.txt"
        testrun = TestRun(
            type="changed",
            skip_code_coverage=skip_code_coverage,
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
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is None:
        ctx.warn("The 'GITHUB_OUTPUT' variable is not set.")
    if TYPE_CHECKING:
        assert testing_releases
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
        # with the tiamat onedir packages.
        # we will need to ensure when we release 3006.0
        # we allow for 3006.0 jobs to run, because then
        # we will have arm64 onedir packages to upgrade from
        sessions.append("upgrade")
    # TODO: Remove this block when we reach version 3009.0, we will no longer be testing upgrades from classic packages
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
        versions: list[str | None] = [None]
        if session == "upgrade":
            versions = [str(version) for version in testing_releases]
        elif session == "upgrade-classic":
            versions = [
                str(version)
                for version in testing_releases
                if version < tools.utils.Version("3006.0")
            ]
        for version in versions:
            matrix.append(
                {
                    "test-chunk": session,
                    "version": version,
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
        gh_event = json.loads(open(gh_event_path).read())
    except Exception as exc:
        ctx.error(f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc)
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
    release_branches = shared_context["release-branches"]

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
    gh_event_path = os.environ.get("GITHUB_EVENT_PATH") or None
    if gh_event_path is None:
        labels = _get_pr_test_labels_from_api(ctx, repository, pr=pr)
    else:
        if TYPE_CHECKING:
            assert gh_event_path is not None

        try:
            gh_event = json.loads(open(gh_event_path).read())
        except Exception as exc:
            ctx.error(
                f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc
            )
            ctx.exit(1)

        if "pull_request" not in gh_event:
            ctx.warning("The 'pull_request' key was not found on the event payload.")
            ctx.exit(1)

        pr = gh_event["pull_request"]["number"]
        labels = _get_pr_test_labels_from_event_payload(gh_event)

    if labels:
        ctx.info(f"Test labels for pull-request #{pr} on {repository}:")
        for name, description in labels:
            ctx.info(f" * [yellow]{name}[/yellow]: {description}")
    else:
        ctx.info(f"No test labels for pull-request #{pr} on {repository}")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is None:
        ctx.exit(0)

    if TYPE_CHECKING:
        assert github_output is not None

    ctx.info("Writing 'labels' to the github outputs file")
    with open(github_output, "a", encoding="utf-8") as wfh:
        wfh.write(f"labels={json.dumps([label[0] for label in labels])}\n")
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
        if "GITHUB_TOKEN" in os.environ:
            headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
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
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is None:
        ctx.exit(1, "The 'GITHUB_OUTPUT' variable is not set.")
    else:
        # We aren't testing upgrades from anything before 3006.0 except the latest 3005.x
        threshold_major = 3006
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
                    if version.major >= threshold_major
                }
            )
        )[-num_major_versions:]
        testing_releases = []
        # Append the latest minor for each major
        for major in majors:
            minors_of_major = [
                version for version in releases if version.major == major
            ]
            testing_releases.append(minors_of_major[-1])

        # TODO: Remove this block when we reach version 3009.0
        # Append the latest minor version of 3005 if we don't have enough major versions to test against
        if len(testing_releases) != num_major_versions:
            url = "https://repo.saltproject.io/salt/onedir/repo.json"
            ret = ctx.web.get(url)
            repo_data = ret.json()
            latest = list(repo_data["latest"].keys())[0]
            version = repo_data["latest"][latest]["version"]
            testing_releases = [version] + testing_releases

        str_releases = [str(version) for version in testing_releases]

        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"testing-releases={json.dumps(str_releases)}\n")

        ctx.exit(0)
