"""
These commands are related to discovering CI test failures from PRs and workflow runs.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from ptscripts import Context, command_group

import tools.utils
import tools.utils.gh

log = logging.getLogger(__name__)

# Define the command group
ci_failure = command_group(
    name="ci-failure",
    help="CI test failure discovery commands",
    description=__doc__,
    parent="ts",
)


def get_workflow_runs_for_pr(
    ctx: Context,
    pr: int,
    repository: str = "saltstack/salt",
) -> list[dict[str, Any]]:
    """
    Get all workflow runs for a PR.
    """
    github_token = tools.utils.gh.get_github_token(ctx)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    with ctx.web as web:
        web.headers.update(headers)

        # Get PR details to find head SHA
        ret = web.get(f"https://api.github.com/repos/{repository}/pulls/{pr}")
        if ret.status_code != 200:
            ctx.error(f"Failed to get PR {pr}: {ret.reason}")
            return []

        pr_data = ret.json()
        head_sha = pr_data["head"]["sha"]
        ctx.info(f"PR #{pr} HEAD SHA: {head_sha}")

        # Get workflow runs for this SHA
        params = {
            "head_sha": head_sha,
            "per_page": 100,
        }
        ret = web.get(
            f"https://api.github.com/repos/{repository}/actions/runs",
            params=params,
        )
        if ret.status_code != 200:
            ctx.error(f"Failed to get workflow runs: {ret.reason}")
            return []

        data = ret.json()
        return data.get("workflow_runs", [])  # type: ignore[no-any-return]


def get_job_logs(
    ctx: Context,
    job_id: int,
    repository: str = "saltstack/salt",
) -> str:
    """
    Download job logs.
    """
    github_token = tools.utils.gh.get_github_token(ctx)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    with ctx.web as web:
        web.headers.update(headers)
        ret = web.get(
            f"https://api.github.com/repos/{repository}/actions/jobs/{job_id}/logs"
        )
        if ret.status_code == 200:
            return ret.text
        else:
            ctx.warn(f"Failed to get logs for job {job_id}: {ret.reason}")
            return ""


def parse_pytest_failures(log_text: str) -> list[str]:
    """
    Parse pytest output to extract failed test names.
    """
    failed_tests = []
    # Strip ANSI escape codes
    log_text = re.sub(r"\x1b\[[0-9;]*m", "", log_text)

    # Pattern for pytest FAILED or ERROR lines
    # Example: FAILED tests/pytests/unit/test_loader.py::test_load_modules - AssertionError
    # Example: ERROR tests/pytests/scenarios/performance/test_performance.py::test_performance - AssertionError
    failed_pattern = re.compile(r"(?:FAILED|ERROR)\s+([^\s:]+(?:::[^\s:]+)*)")

    for line in log_text.split("\n"):
        # Remove timestamp if present at the start (GHA style)
        line = re.sub(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+", "", line)

        match = failed_pattern.search(line)
        if match:
            test_path = match.group(1).split()[0]
            # Remove any trailing junk that might be captured if the path is followed by something other than space
            test_path = test_path.split(" - ")[0].split(" : ")[0]
            if test_path not in failed_tests and "/" in test_path:
                failed_tests.append(test_path)

    return failed_tests


def get_all_jobs(
    ctx: Context,
    run_id: int,
    repository: str = "saltstack/salt",
) -> list[dict[str, Any]]:
    """
    Get all jobs for a run, with pagination.
    """
    github_token = tools.utils.gh.get_github_token(ctx)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    all_jobs = []
    page = 1
    with ctx.web as web:
        web.headers.update(headers)
        while True:
            ret = web.get(
                f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/jobs",
                params={"per_page": 100, "page": page},
            )
            if ret.status_code != 200:
                ctx.error(f"Failed to get jobs (page {page}): {ret.reason}")
                break

            data = ret.json()
            jobs = data.get("jobs", [])
            if not jobs:
                break
            all_jobs.extend(jobs)
            if len(all_jobs) >= data.get("total_count", 0):
                break
            page += 1

    return all_jobs


@ci_failure.command(
    name="pr",
    arguments={
        "pr": {
            "help": "Pull request number",
        },
        "repository": {
            "help": "Repository (e.g., saltstack/salt)",
        },
        "json_output": {
            "help": "Output as JSON",
        },
    },
)
def pr_failures(
    ctx: Context,
    pr: int,
    repository: str = "saltstack/salt",
    json_output: bool = False,
):
    """
    Get all failing tests from a PR's CI runs.

    Examples:

     * Get failures from PR #68562:

         tools ts ci-failure pr 68562

     * Get failures as JSON:

         tools ts ci-failure pr 68562 --json-output
    """
    if TYPE_CHECKING:
        assert pr is not None

    ctx.info(f"Discovering test failures for PR #{pr} in {repository}")

    workflow_runs = get_workflow_runs_for_pr(ctx, pr, repository)
    if not workflow_runs:
        ctx.warn("No workflow runs found for this PR")
        ctx.exit(0)

    # Find the most recent test workflow run
    test_run = None
    for run in workflow_runs:
        run_name = run.get("name", "").lower()
        if any(x in run_name for x in ("test", "ci")) and all(
            x not in run_name for x in ("lint", "docs", "pre-commit")
        ):
            test_run = run
            break

    if not test_run:
        ctx.warn("No test workflow runs found")
        ctx.exit(0)

    run_id = test_run["id"]
    conclusion = test_run.get("conclusion", "unknown")
    status = test_run.get("status", "unknown")

    ctx.info(f"Latest test run: {run_id} (status: {status}, conclusion: {conclusion})")

    if conclusion == "success":
        ctx.info("All tests passed!")
        ctx.exit(0)

    # Get jobs for this run
    jobs = get_all_jobs(ctx, run_id, repository)

    failures_by_platform = {}

    for job in jobs:
        if job.get("conclusion") == "failure":
            job_name = job["name"]
            job_id = job["id"]

            ctx.info(f"Analyzing failed job: {job_name} ({job_id})")

            # Try to extract platform info from job name
            # Example: "Test / Linux (Arch Linux LTS, arm64, 1) / Test (1/8)"
            platform_match = re.search(r"Linux \(([^,]+)", job_name)
            platform = platform_match.group(1) if platform_match else "unknown"

            # Get logs and parse failures
            logs = get_job_logs(ctx, job_id, repository)
            failed_tests = parse_pytest_failures(logs)

            if failed_tests:
                if platform not in failures_by_platform:
                    failures_by_platform[platform] = {
                        "job_id": job_id,
                        "job_name": job_name,
                        "tests": [],
                    }
                failures_by_platform[platform]["tests"].extend(failed_tests)

    if json_output:
        output = {
            "pr": pr,
            "run_id": run_id,
            "repository": repository,
            "failures": failures_by_platform,
        }
        ctx.print(json.dumps(output, indent=2))
    else:
        ctx.info(f"\nTest Failures for PR #{pr}:")
        ctx.info(f"Run ID: {run_id}")
        ctx.info(f"Repository: {repository}\n")

        if not failures_by_platform:
            ctx.warn("No test failures found (or unable to parse logs)")
        else:
            for platform, data in failures_by_platform.items():
                ctx.info(f"Platform: {platform}")
                ctx.info(f"  Job: {data['job_name']}")
                ctx.info(f"  Job ID: {data['job_id']}")
                ctx.info(f"  Failed tests ({len(data['tests'])}):")
                for test in data["tests"]:
                    ctx.print(f"    - {test}")
                ctx.print("")

    ctx.exit(0)


@ci_failure.command(
    name="run",
    arguments={
        "run_id": {
            "help": "Workflow run ID",
        },
        "repository": {
            "help": "Repository (e.g., saltstack/salt)",
        },
        "json_output": {
            "help": "Output as JSON",
        },
    },
)
def run_failures(
    ctx: Context,
    run_id: int,
    repository: str = "saltstack/salt",
    json_output: bool = False,
):
    """
    Get failing tests from a specific workflow run.

    Examples:

     * Get failures from run 12345:

         tools ts ci-failure run 12345

     * Get failures as JSON:

         tools ts ci-failure run 12345 --json-output
    """
    if TYPE_CHECKING:
        assert run_id is not None

    ctx.info(f"Discovering test failures for run {run_id} in {repository}")

    github_token = tools.utils.gh.get_github_token(ctx)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    with ctx.web as web:
        web.headers.update(headers)

        # Get run details
        ret = web.get(
            f"https://api.github.com/repos/{repository}/actions/runs/{run_id}"
        )
        if ret.status_code != 200:
            ctx.error(f"Failed to get run {run_id}: {ret.reason}")
            ctx.exit(1)

        run_data = ret.json()
        conclusion = run_data.get("conclusion", "unknown")
        ctx.info(f"Run conclusion: {conclusion}")

        if conclusion == "success":
            ctx.info("All tests passed!")
            ctx.exit(0)

        # Get jobs for this run
        jobs = get_all_jobs(ctx, run_id, repository)

    failures_by_job = {}

    for job in jobs:
        if job.get("conclusion") == "failure":
            job_name = job["name"]
            job_id = job["id"]

            ctx.info(f"Analyzing failed job: {job_name} ({job_id})")

            # Get logs and parse failures
            logs = get_job_logs(ctx, job_id, repository)
            failed_tests = parse_pytest_failures(logs)

            if failed_tests:
                failures_by_job[job_name] = {
                    "job_id": job_id,
                    "tests": failed_tests,
                }

    if json_output:
        output = {
            "run_id": run_id,
            "repository": repository,
            "failures": failures_by_job,
        }
        ctx.print(json.dumps(output, indent=2))
    else:
        ctx.info(f"\nTest Failures for Run {run_id}:")
        ctx.info(f"Repository: {repository}\n")

        if not failures_by_job:
            ctx.warn("No test failures found (or unable to parse logs)")
        else:
            for job_name, data in failures_by_job.items():
                ctx.info(f"Job: {job_name}")
                ctx.info(f"  Job ID: {data['job_id']}")
                ctx.info(f"  Failed tests ({len(data['tests'])}):")
                for test in data["tests"]:
                    ctx.print(f"    - {test}")
                ctx.print("")

    ctx.exit(0)


@ci_failure.command(
    name="summary",
    arguments={
        "pr": {
            "help": "Pull request number",
        },
        "repository": {
            "help": "Repository (e.g., saltstack/salt)",
        },
    },
)
def failure_summary(
    ctx: Context,
    pr: int,
    repository: str = "saltstack/salt",
):
    """
    Get a human-readable summary of PR test failures.

    Examples:

     * Get failure summary for PR #68562:

         tools ts ci-failure summary 68562
    """
    if TYPE_CHECKING:
        assert pr is not None

    ctx.info(f"Generating failure summary for PR #{pr}\n")

    workflow_runs = get_workflow_runs_for_pr(ctx, pr, repository)
    if not workflow_runs:
        ctx.warn("No workflow runs found for this PR")
        ctx.exit(0)

    # Find the most recent test workflow run
    test_run = None
    for run in workflow_runs:
        run_name = run.get("name", "").lower()
        if any(x in run_name for x in ("test", "ci")) and all(
            x not in run_name for x in ("lint", "docs", "pre-commit")
        ):
            test_run = run
            break

    if not test_run:
        ctx.warn("No test workflow runs found")
        ctx.exit(0)

    run_id = test_run["id"]
    conclusion = test_run.get("conclusion", "unknown")
    html_url = test_run.get("html_url", "")

    ctx.print("=" * 70)
    ctx.print(f"PR #{pr} - CI Test Summary")
    ctx.print("=" * 70)
    ctx.print(f"Repository: {repository}")
    ctx.print(f"Run ID: {run_id}")
    ctx.print(f"Status: {conclusion}")
    ctx.print(f"URL: {html_url}")
    ctx.print("=" * 70)
    ctx.print("")

    if conclusion == "success":
        ctx.print("✓ All tests passed!")
        ctx.exit(0)

    # Get jobs
    jobs = get_all_jobs(ctx, run_id, repository)

    total_jobs = len(jobs)
    failed_jobs = sum(1 for job in jobs if job.get("conclusion") == "failure")
    passed_jobs = sum(1 for job in jobs if job.get("conclusion") == "success")

    ctx.print(f"Jobs: {total_jobs} total, {passed_jobs} passed, {failed_jobs} failed")
    ctx.print("")

    if failed_jobs > 0:
        ctx.print("Failed Jobs:")
        ctx.print("-" * 70)

        for job in jobs:
            if job.get("conclusion") == "failure":
                job_name = job["name"]
                job_id = job["id"]
                ctx.print(f"\n• {job_name}")
                ctx.print(f"  Job ID: {job_id}")

                # Get quick failure count
                logs = get_job_logs(ctx, job_id, repository)
                failed_tests = parse_pytest_failures(logs)

                if failed_tests:
                    ctx.print(f"  Failed tests: {len(failed_tests)}")
                    # Show first few failures
                    for test in failed_tests[:3]:
                        ctx.print(f"    - {test}")
                    if len(failed_tests) > 3:
                        ctx.print(f"    ... and {len(failed_tests) - 3} more")

    ctx.exit(0)
