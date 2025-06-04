"""
These commands are used in the CI pipeline.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import json
import logging
import os
import pathlib
import pprint
import random
import shutil
import sys
import time
from typing import TYPE_CHECKING, Any, Literal

import yaml
from ptscripts import Context, command_group

import tools.utils
import tools.utils.gh
from tools.precommit.workflows import TEST_SALT_LISTING, TEST_SALT_PKG_LISTING

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


class TestRun(TypedDict):
    type: str
    skip_code_coverage: bool
    from_filenames: NotRequired[str]
    selected_tests: NotRequired[dict[str, bool]]


def _build_matrix(os_kind, linux_arm_runner):
    """
    Generate matrix for build ci/cd steps.
    """
    _matrix = [{"arch": "x86_64"}]
    if os_kind == "windows":
        _matrix = [
            {"arch": "amd64"},
            {"arch": "x86"},
        ]
    elif os_kind == "macos":
        _matrix.append({"arch": "arm64"})
    elif os_kind == "linux" and linux_arm_runner:
        _matrix.append({"arch": "arm64"})
    return _matrix


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
                if slug != "all" and slug in available:
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
    """
    Filter labels that can affect the workflow configuration. Return a tuple of
    their name and description.
    """
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
                # We aren't testing upgrades from anything before 3006.0
                # and we don't want to test 3007.? on the 3006.x branch
                version.major
                for version in releases
                if version.major > 3005 and version.major <= parsed_salt_version.major
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


def _os_test_filter(osdef, transport, chunk, arm_runner, requested_slugs):
    """
    Filter out some test runs based on os, tranport and chunk to be run.
    """
    if osdef.slug not in requested_slugs:
        return False
    if transport == "tcp" and chunk in ("unit", "functional"):
        return False
    if "macos" in osdef.slug and chunk == "scenarios":
        return False
    if osdef.platform == "linux" and osdef.arch == "arm64" and not arm_runner:
        return False
    if transport == "tcp" and osdef.slug not in (
        "rockylinux-9",
        "rockylinux-9-arm64",
        "photonos-5",
        "photonos-5-arm64",
        "ubuntu-22.04",
        "ubuntu-22.04-arm64",
    ):
        return False
    return True


def _define_testrun(ctx, changed_files, labels, full):
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
    changed_pkg_requirements_files: list[str] = []
    changed_test_requirements_files: list[str] = []
    if "pkg_requirements_files" in changed_files_contents:
        changed_pkg_requirements_files = json.loads(
            changed_files_contents["pkg_requirements_files"]
        )
    if "test_requirements_files" in changed_files_contents:
        changed_test_requirements_files = json.loads(
            changed_files_contents["test_requirements_files"]
        )
    if full:
        ctx.info("Full test run chosen")
        testrun = TestRun(type="full", skip_code_coverage=True)
    elif changed_pkg_requirements_files or changed_test_requirements_files:
        ctx.info(
            "Full test run chosen because there was a change made "
            "to the requirements files."
        )
        testrun = TestRun(type="full", skip_code_coverage=True)
    elif "test:full" in labels:
        ctx.info("Full test run chosen because the label `test:full` is set.\n")
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
                ctx.info(
                    f"Full test run chosen because there was a change to `{fpath}`."
                )
            selected_changed_files.append(fpath)
        testrun_changed_files_path.write_text("\n".join(sorted(selected_changed_files)))
        if testrun["type"] == "changed":
            testrun["selected_tests"] = {
                "core": False,
                "slow": False,
                "fast": True,
                "flaky": False,
            }
            if "test:slow" in labels:
                ctx.info("Slow tests chosen by `test:slow` label.")
                testrun["selected_tests"]["slow"] = True
            if "test:core" in labels:
                ctx.info("Core tests chosen by `test:core` label.")
                testrun["selected_tests"]["core"] = True
            if "test:no-fast" in labels:
                ctx.info("Fast tests deselected by `test:no-fast` label.")
                testrun["selected_tests"]["fast"] = False
            if "test:flaky-jail" in labels:
                ctx.info("Flaky jailed tests chosen by `test:flaky-jail` label.")
                testrun["selected_tests"]["flaky"] = True
    return testrun


def _environment_slugs(ctx, slugdef, labels):
    """
    Based a slugs defenition from our environment and labels for a pr, return
    the requeted slugs for a testrun.

    Environment slug defenitions can be a comma separated list. An "all" item
    in the list will include all os and package slugs.
    """
    if isinstance(slugdef, list):
        requests = slugdef
    else:
        requests = [_.strip().lower() for _ in slugdef.split(",") if _.strip()]
    label_requests = [
        _[0].rsplit(":", 1)[1] for _ in labels if _[0].startswith("test:os:")
    ]
    all_slugs = []
    slugs = set()
    for platform in TEST_SALT_LISTING:
        for osdef in TEST_SALT_LISTING[platform]:
            all_slugs.append(osdef.slug)
    for platform in TEST_SALT_LISTING:
        for osdef in TEST_SALT_LISTING[platform]:
            all_slugs.append(osdef.slug)
    if "all" in requests:
        slugs = all_slugs[:]
        requests.remove("all")
    if "all" in label_requests:
        slugs = all_slugs[:]
        label_requests.remove("all")
    for request in requests[:]:
        if request.startswith("+"):
            request = request.strip("+")
            if request not in all_slugs:
                ctx.warn(f"invalid slug name from environment {request}")
                continue
            if request in slugs:
                ctx.info("slug already requested from environment {request}")
                continue
            slugs.add(request)
        elif request.startswith("-"):
            request = request.strip("-")
            if request not in all_slugs:
                ctx.warn(f"invalid slug name from environment {request}")
                continue
            if request in slugs:
                slugs.remove(request)
            else:
                ctx.info("slug from environment was never requested {request}")
        else:
            if request not in all_slugs:
                ctx.warn(f"invalid slug name from environment {request}")
                continue
            if request in slugs:
                ctx.info("slug from environment already requested {request}")
                continue
            slugs.add(request)

    for label in label_requests:
        if label not in all_slugs:
            ctx.warn(f"invalid slug name from label {label}")
            continue
        if label in slugs:
            ctx.info(f"slug from labels already requested {label}")
            continue
        slugs.add(label)

    return list(slugs)


@ci.command(
    name="workflow-config",
    arguments={
        "salt_version": {
            "help": "The version of salt being tested against",
        },
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
def workflow_config(
    ctx: Context,
    salt_version: str,
    event_name: str,
    changed_files: pathlib.Path,
    skip_tests: bool = False,
    skip_pkg_tests: bool = False,
    skip_pkg_download_tests: bool = False,
):
    full = False
    gh_event_path = os.environ.get("GITHUB_EVENT_PATH") or None
    gh_event: dict[str, Any] = {}
    config: dict[str, Any] = {}
    labels: list[tuple[str, str]] = []
    slugs: str | list[str] = []

    ctx.info(f"{'==== environment ====':^80s}")
    ctx.info(f"{pprint.pformat(dict(os.environ))}")
    ctx.info(f"{'==== end environment ====':^80s}")
    ctx.info(f"Github event path is {gh_event_path}")

    if gh_event_path is None:
        config["linux_arm_runner"] = ""
    else:
        try:
            gh_event = json.loads(open(gh_event_path, encoding="utf-8").read())
        except Exception as exc:
            ctx.error(
                f"Could not load the GH Event payload from {gh_event_path!r}:\n", exc
            )
            ctx.exit(1)

        if "pull_request" in gh_event:
            pr = gh_event["pull_request"]["number"]
            labels = _get_pr_test_labels_from_event_payload(gh_event)
        else:
            ctx.warn("The 'pull_request' key was not found on the event payload.")

        if gh_event["repository"]["private"]:
            # Private repositories need arm runner configuration environment
            # variable.
            if os.environ.get("LINUX_ARM_RUNNER", "0") in ("0", ""):
                config["linux_arm_runner"] = ""
            else:
                config["linux_arm_runner"] = os.environ["LINUX_ARM_RUNNER"]
        else:
            # Public repositories can use github's arm64 runners.
            config["linux_arm_runner"] = "ubuntu-24.04-arm"

    if event_name != "pull_request" or "test:full" in [_[0] for _ in labels]:
        full = True
        slugs = os.environ.get("FULL_TESTRUN_SLUGS", "")
        if not slugs:
            slugs = tools.utils.get_cicd_shared_context()["full-testrun-slugs"]
    else:
        slugs = os.environ.get("PR_TESTRUN_SLUGS", "")
        if not slugs:
            slugs = tools.utils.get_cicd_shared_context()["pr-testrun-slugs"]

    requested_slugs = _environment_slugs(
        ctx,
        slugs,
        labels,
    )

    ctx.info(f"{'==== requested slugs ====':^80s}")
    ctx.info(f"{pprint.pformat(requested_slugs)}")
    ctx.info(f"{'==== end requested slugs ====':^80s}")

    ctx.info(f"{'==== labels ====':^80s}")
    ctx.info(f"{pprint.pformat(labels)}")
    ctx.info(f"{'==== end labels ====':^80s}")

    config["skip_code_coverage"] = True
    if "test:coverage" in labels:
        config["skip_code_coverage"] = False
    else:
        ctx.info("Skipping code coverage.")

    ctx.info(f"{'==== github event ====':^80s}")
    ctx.info(f"{pprint.pformat(gh_event)}")
    ctx.info(f"{'==== end github event ====':^80s}")

    config["testrun"] = _define_testrun(ctx, changed_files, labels, full)

    ctx.info(f"{'==== testrun ====':^80s}")
    ctx.info(f"{pprint.pformat(config['testrun'])}")
    ctx.info(f"{'==== testrun ====':^80s}")

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
        "build-deps-ci": True if requested_slugs else False,
    }

    platforms: list[Literal["linux", "macos", "windows"]] = [
        "linux",
        "macos",
        "windows",
    ]

    if skip_pkg_download_tests:
        jobs["test-pkg-download"] = False

    config["jobs"] = jobs
    config["build-matrix"] = {
        platform: _build_matrix(platform, config["linux_arm_runner"])
        for platform in platforms
    }
    ctx.info(f"{'==== build matrix ====':^80s}")
    ctx.info(f"{pprint.pformat(config['build-matrix'])}")
    ctx.info(f"{'==== end build matrix ====':^80s}")
    config["artifact-matrix"] = []
    for platform in platforms:
        config["artifact-matrix"] += [
            dict({"platform": platform}, **_) for _ in config["build-matrix"][platform]
        ]
    ctx.info(f"{'==== artifact matrix ====':^80s}")
    ctx.info(f"{pprint.pformat(config['artifact-matrix'])}")
    ctx.info(f"{'==== end artifact matrix ====':^80s}")

    # Get salt releases.
    releases = tools.utils.get_salt_releases(ctx)
    str_releases = [str(version) for version in releases]
    latest = str_releases[-1]

    # Get testing releases.
    parsed_salt_version = tools.utils.Version(salt_version)
    # We want the latest 4 major versions, removing the oldest if this version is a new major
    num_major_versions = 4
    if parsed_salt_version.minor == 0:
        num_major_versions = 3
    majors = sorted(
        list(
            {
                # We aren't testing upgrades from anything before 3006.0
                # and we don't want to test 3007.? on the 3006.x branch
                version.major
                for version in releases
                if version.major > 3005 and version.major <= parsed_salt_version.major
            }
        )
    )[-num_major_versions:]
    testing_releases = []
    # Append the latest minor for each major
    for major in majors:
        minors_of_major = [version for version in releases if version.major == major]
        testing_releases.append(minors_of_major[-1])
    str_releases = [str(version) for version in testing_releases]
    ctx.info(f"str_releases {str_releases}")

    pkg_test_matrix: dict[str, list] = {_: [] for _ in platforms}

    if not config["linux_arm_runner"]:
        # Filter out linux arm tests because we are on a private repository and
        # no arm64 runner is defined.
        TEST_SALT_LISTING["linux"] = list(
            filter(lambda x: x.arch != "arm64", TEST_SALT_LISTING["linux"])
        )
        TEST_SALT_PKG_LISTING["linux"] = list(
            filter(lambda x: x.arch != "arm64", TEST_SALT_PKG_LISTING["linux"])
        )
    if not skip_pkg_tests:
        for platform in platforms:
            pkg_test_matrix[platform] = [
                dict(
                    {
                        "tests-chunk": "install",
                        "version": None,
                    },
                    **_.as_dict(),
                )
                for _ in TEST_SALT_PKG_LISTING[platform]
                if _.slug in requested_slugs
            ]
        for version in str_releases:
            for platform in platforms:

                if platform == "windows" and "3006" in version:
                    # The salt_master_cli.py script used by the windows pakcage
                    # tests doesn't play nice with trying to go from 3006.x to
                    # >=3007.x.
                    ctx.info("3006.x upgrade/downgrade tests do not work on windows")
                    continue

                pkg_test_matrix[platform] += [
                    dict(
                        {
                            "tests-chunk": "upgrade",
                            "version": version,
                        },
                        **_.as_dict(),
                    )
                    for _ in TEST_SALT_PKG_LISTING[platform]
                    if _.slug in requested_slugs
                ]
                pkg_test_matrix[platform] += [
                    dict(
                        {
                            "tests-chunk": "downgrade",
                            "version": version,
                        },
                        **_.as_dict(),
                    )
                    for _ in TEST_SALT_PKG_LISTING[platform]
                    if _.slug in requested_slugs and "photon" not in _.slug
                ]
    ctx.info(f"{'==== pkg test matrix ====':^80s}")
    ctx.info(f"{pprint.pformat(pkg_test_matrix)}")
    ctx.info(f"{'==== end pkg test matrix ====':^80s}")

    # We need to be careful about how many chunks we make. We are limitied to
    # 256 items in a matrix.
    _splits = {
        "functional": 4,
        "integration": 7,
        "scenarios": 1,
        "unit": 4,
    }

    test_matrix: dict[str, list] = {
        "linux-x86_64": [],
        "linux-arm64": [],
        "macos": [],
        "windows": [],
    }
    if not skip_tests:
        for platform in platforms:
            for transport in ("zeromq", "tcp"):
                for chunk in ("unit", "functional", "integration", "scenarios"):
                    splits = _splits.get(chunk) or 1
                    if full and splits > 1:
                        for split in range(1, splits + 1):
                            if platform != "linux":
                                if platform not in test_matrix:
                                    test_matrix[platform] = []
                                test_matrix[platform] += [
                                    dict(
                                        {
                                            "transport": transport,
                                            "tests-chunk": chunk,
                                            "test-group": split,
                                            "test-group-count": splits,
                                        },
                                        **_.as_dict(),
                                    )
                                    for _ in TEST_SALT_LISTING[platform]
                                    if _os_test_filter(
                                        _,
                                        transport,
                                        chunk,
                                        config["linux_arm_runner"],
                                        requested_slugs,
                                    )
                                ]
                            else:
                                for arch in ["x86_64", "arm64"]:
                                    if f"{platform}-{arch}" not in test_matrix:
                                        test_matrix[f"{platform}-{arch}"] = []
                                    test_matrix[f"{platform}-{arch}"] += [
                                        dict(
                                            {
                                                "transport": transport,
                                                "tests-chunk": chunk,
                                                "test-group": split,
                                                "test-group-count": splits,
                                            },
                                            **_.as_dict(),
                                        )
                                        for _ in TEST_SALT_LISTING[platform]
                                        if _os_test_filter(
                                            _,
                                            transport,
                                            chunk,
                                            config["linux_arm_runner"],
                                            requested_slugs,
                                        )
                                        and _.arch == arch
                                    ]
                    else:
                        if platform != "linux":
                            if platform not in test_matrix:
                                test_matrix[platform] = []
                            test_matrix[platform] += [
                                dict(
                                    {"transport": transport, "tests-chunk": chunk},
                                    **_.as_dict(),
                                )
                                for _ in TEST_SALT_LISTING[platform]
                                if _os_test_filter(
                                    _,
                                    transport,
                                    chunk,
                                    config["linux_arm_runner"],
                                    requested_slugs,
                                )
                            ]
                        else:
                            for arch in ["x86_64", "arm64"]:
                                if f"{platform}-{arch}" not in test_matrix:
                                    test_matrix[f"{platform}-{arch}"] = []
                                test_matrix[f"{platform}-{arch}"] += [
                                    dict(
                                        {"transport": transport, "tests-chunk": chunk},
                                        **_.as_dict(),
                                    )
                                    for _ in TEST_SALT_LISTING[platform]
                                    if _os_test_filter(
                                        _,
                                        transport,
                                        chunk,
                                        config["linux_arm_runner"],
                                        requested_slugs,
                                    )
                                    and _.arch == arch
                                ]

    for key in test_matrix:
        if len(test_matrix[key]) > 256:
            ctx.warn(
                f"Number of jobs in {platform} test matrix exceeds 256 ({len(test_matrix[key])}), jobs may not run."
            )

    ctx.info(f"{'==== test matrix ====':^80s}")
    ctx.info(f"{pprint.pformat(test_matrix)}")
    ctx.info(f"{'==== end test matrix ====':^80s}")
    config["pkg-test-matrix"] = pkg_test_matrix
    config["test-matrix"] = test_matrix
    ctx.info("Jobs selected are")
    for x, y in jobs.items():
        ctx.info(f"{x} = {y}")
    github_step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_step_summary is not None:
        with open(github_step_summary, "a", encoding="utf-8") as wfh:
            wfh.write("Selected Jobs:\n")
            for name, value in sorted(jobs.items()):
                wfh.write(f" - `{name}`: {value}\n")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is not None:
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(f"config={json.dumps(config)}\n")
    ctx.exit(0)
