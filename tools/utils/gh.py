# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated,bad-whitespace
from __future__ import annotations

import fnmatch
import os
import pathlib
import shutil
import sys
import tempfile
import zipfile
from typing import TYPE_CHECKING

from ptscripts import Context

import tools.utils
from tools.utils import ExitCode


def download_onedir_artifact(
    ctx: Context,
    run_id: int = None,
    platform: str = None,
    arch: str = "x86_64",
    repository: str = "saltstack/salt",
) -> int:
    """
    Download CI onedir artifacts.
    """
    if TYPE_CHECKING:
        assert run_id is not None
        assert platform is not None

    if platform == "windows":
        if arch in ("x64", "x86_64"):
            ctx.info(f"Turning passed arch {arch!r} into 'amd64'")
            arch = "amd64"
        if arch not in ("amd64", "x86"):
            ctx.error(
                "The allowed values for '--arch' on Windows are 'amd64' and 'x86'"
            )
            return ExitCode.FAIL
    else:
        if arch == "aarch64":
            ctx.info(f"Turning passed arch {arch!r} into 'arm64'")
            arch = "arm64"
        elif arch == "x64":
            ctx.info(f"Turning passed arch {arch!r} into 'x86_64'")
            arch = "x86_64"
        if arch not in ("x86_64", "arm64"):
            ctx.error(
                f"The allowed values for '--arch' on {platform.title()} are 'x86_64' or 'arm64'"
            )
            return ExitCode.FAIL
    artifacts_path = tools.utils.REPO_ROOT / "artifacts"
    artifacts_path.mkdir(exist_ok=True)
    if artifacts_path.joinpath("salt").exists():
        ctx.warn(
            "The 'artifacts/salt' directory already exists ... Stopped processing."
        )
        return ExitCode.SOFT_FAIL
    artifact_name = f"salt-*-onedir-{platform}-{arch}"
    if sys.platform.startswith("win"):
        artifact_name += ".zip"
    else:
        artifact_name += ".tar.xz"
    ctx.info(
        f"Searching for artifact {artifact_name} from run_id {run_id} in repository {repository} ..."
    )
    found_artifact_name = download_artifact(
        ctx,
        dest=artifacts_path,
        run_id=run_id,
        artifact_name=artifact_name,
        repository=repository,
    )
    if found_artifact_name is None:
        return ExitCode.FAIL
    found_artifact_path = artifacts_path / found_artifact_name
    checksum_algo = "sha512"
    ctx.info(f"Validating {found_artifact_name!r} {checksum_algo} checksum ...")
    artifact_expected_checksum = (
        artifacts_path.joinpath(f"{found_artifact_name}.{checksum_algo.upper()}")
        .read_text()
        .strip()
    )
    artifact_checksum = tools.utils.get_file_checksum(
        found_artifact_path, checksum_algo
    )
    if artifact_expected_checksum != artifact_checksum:
        ctx.error(f"The {checksum_algo} checksum does not match")
        ctx.error(f"{artifact_checksum!r} != {artifact_expected_checksum!r}")
        return ExitCode.FAIL

    ctx.info(
        f"Decompressing {found_artifact_name!r} to {artifacts_path.relative_to(tools.utils.REPO_ROOT)}{os.path.sep} ..."
    )
    if found_artifact_path.suffix == ".zip":
        with zipfile.ZipFile(found_artifact_path) as zfile:
            zfile.extractall(path=artifacts_path)
    else:
        ctx.run("tar", "xf", found_artifact_name, cwd=artifacts_path)

    return ExitCode.OK


def download_nox_artifact(
    ctx: Context,
    platform: str,
    arch: str,
    run_id: int = None,
    nox_env: str = "ci-test-onedir",
    repository: str = "saltstack/salt",
) -> ExitCode:
    """
    Download CI nox artifacts.
    """
    if TYPE_CHECKING:
        assert run_id is not None
        assert arch is not None
        assert platform is not None

    if platform == "windows":
        if arch in ("x64", "x86_64"):
            ctx.info(f"Turning passed arch {arch!r} into 'amd64'")
            arch = "amd64"
        if arch not in ("amd64", "x86"):
            ctx.error(
                "The allowed values for '--arch' on Windows are 'amd64' and 'x86'"
            )
            return ExitCode.FAIL
    else:
        if arch == "aarch64":
            ctx.info(f"Turning passed arch {arch!r} into 'arm64'")
            arch = "arm64"
        elif arch == "x64":
            ctx.info(f"Turning passed arch {arch!r} into 'x86_64'")
            arch = "x86_64"
        if arch not in ("x86_64", "arm64"):
            ctx.error(
                f"The allowed values for '--arch' on {platform.title()} are 'x86_64' or 'arm64'"
            )
            return ExitCode.FAIL

    artifacts_path = tools.utils.REPO_ROOT / ".nox" / nox_env
    if artifacts_path.exists():
        ctx.error(
            f"The '.nox/{nox_env}' directory already exists ... Stopped processing."
        )
        return ExitCode.SOFT_FAIL
    artifact_name = f"nox-{platform}-{arch}-{nox_env}"
    ctx.info(
        f"Searching for artifact {artifact_name} from run_id {run_id} in repository {repository} ..."
    )
    found_artifact_name = download_artifact(
        ctx,
        dest=tools.utils.REPO_ROOT,
        run_id=run_id,
        artifact_name=artifact_name,
        repository=repository,
    )
    nox = shutil.which("nox")
    if nox is None:
        ctx.error("Could not find the 'nox' binary in $PATH")
        return ExitCode.FAIL
    ret = ctx.run(
        nox,
        "--force-color",
        "-e",
        "decompress-dependencies",
        "--",
        platform,
        arch,
        check=False,
    )
    if ret.returncode:
        ctx.error("Failed to decompress the nox dependencies")
        return ExitCode.FAIL
    return ExitCode.OK


def download_pkgs_artifact(
    ctx: Context,
    run_id: int = None,
    slug: str = None,
    arch: str = "x86_64",
    repository: str = "saltstack/salt",
) -> ExitCode:
    """
    Download CI nox artifacts.
    """
    if TYPE_CHECKING:
        assert run_id is not None
        assert slug is not None

    artifact_name = "salt-*-"
    if "windows" in slug:
        if arch in ("x64", "x86_64"):
            ctx.info(f"Turning passed arch {arch!r} into 'amd64'")
            arch = "amd64"
        if arch not in ("amd64", "x86"):
            ctx.error(
                "The allowed values for '--arch' on Windows are 'amd64' and 'x86'"
            )
            return ExitCode.FAIL
        artifact_name += f"{arch}-MSI"
    else:
        if arch == "aarch64":
            ctx.info(f"Turning passed arch {arch!r} into 'arm64'")
            arch = "arm64"
        elif arch == "x64":
            ctx.info(f"Turning passed arch {arch!r} into 'x86_64'")
            arch = "x86_64"
        if arch not in ("x86_64", "arm64"):
            ctx.error(
                f"The allowed values for '--arch' for {slug} are 'x86_64' or 'arm64'"
            )
            return ExitCode.FAIL

        if slug.startswith(("debian", "ubuntu")):
            artifact_name += f"{arch}-deb"
        elif slug.startswith(
            ("rockylinux", "amazonlinux", "fedora", "opensuse", "photonos")
        ):
            artifact_name += f"{arch}-rpm"
        else:
            ctx.error(f"We do not build packages for {slug}")
            return ExitCode.FAIL

    artifacts_path = tools.utils.REPO_ROOT / "artifacts" / "pkg"
    artifacts_path.mkdir(exist_ok=True)

    ctx.info(
        f"Searching for artifact {artifact_name} from run_id {run_id} in repository {repository} ..."
    )
    found_artifact_name = download_artifact(
        ctx,
        dest=artifacts_path,
        run_id=run_id,
        artifact_name=artifact_name,
        repository=repository,
    )
    if found_artifact_name is None:
        return ExitCode.FAIL
    return ExitCode.OK


def get_github_token(ctx: Context) -> str | None:
    """
    Get the GITHUB_TOKEN to be able to authenticate to the API.
    """
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token is not None:
        ctx.info("$GITHUB_TOKEN was found on the environ")
        return github_token

    gh = shutil.which("gh")
    if gh is None:
        ctx.info("The 'gh' CLI tool is not available. Can't get a token using it.")
        return github_token

    ret = ctx.run(gh, "auth", "token", check=False, capture=True)
    if ret.returncode == 0:
        ctx.info("Got the GitHub token from the 'gh' CLI tool")
        return ret.stdout.decode().strip() or None
    ctx.info("Failed to get the GitHub token from the 'gh' CLI tool")
    return github_token


def download_artifact(
    ctx: Context,
    dest: pathlib.Path,
    run_id: int,
    repository: str = "saltstack/salt",
    artifact_name: str | None = None,
) -> str | None:
    """
    Download CI artifacts.
    """
    found_artifact: str | None = None
    github_token = get_github_token(ctx)
    if github_token is None:
        ctx.error("Downloading artifacts requires being authenticated to GitHub.")
        ctx.info(
            "Either set 'GITHUB_TOKEN' to a valid token, or configure the 'gh' tool such that "
            "'gh auth token' returns a token."
        )
        return found_artifact
    with ctx.web as web:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        web.headers.update(headers)
        page = 0
        listed_artifacts: set[str] = set()
        while True:
            if found_artifact is not None:
                break
            page += 1
            params = {
                "per_page": 100,
                "page": page,
            }
            ret = web.get(
                f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/artifacts",
                params=params,
            )
            if ret.status_code != 200:
                ctx.error(
                    f"Failed to get the artifacts for the run ID {run_id} for repository {repository!r}: {ret.reason}"
                )
                ctx.exit(1)
            data = ret.json()
            if data["total_count"] <= len(listed_artifacts):
                ctx.info("Already gone through all of the listed artifacts:")
                ctx.print(sorted(listed_artifacts))
                break
            ctx.debug(f"Processing artifacts listing (page: {page}) ...")
            if not data["artifacts"]:
                break
            for artifact in data["artifacts"]:
                listed_artifacts.add(artifact["name"])
                ctx.debug(
                    f"Checking if {artifact['name']!r} matches {artifact_name!r} "
                    f"({len(listed_artifacts)}/{data['total_count']}) ..."
                )
                if fnmatch.fnmatch(artifact["name"], artifact_name):
                    found_artifact = artifact["name"]
                    tempdir_path = pathlib.Path(tempfile.gettempdir())
                    download_url = artifact["archive_download_url"]
                    downloaded_artifact = tools.utils.download_file(
                        ctx,
                        download_url,
                        tempdir_path / f"{artifact['name']}.zip",
                        headers=headers,
                    )
                    ctx.info(f"Downloaded {downloaded_artifact}")
                    with zipfile.ZipFile(downloaded_artifact) as zfile:
                        zfile.extractall(path=dest)
                    break
    if found_artifact is None:
        ctx.error(f"Failed to find an artifact by the name of {artifact_name!r}")
    return found_artifact


def discover_run_id(
    ctx: Context,
    branch: str = None,
    nightly: str = None,
    pr: int = None,
    repository: str = "saltstack/salt",
    completed_status: bool = True,
) -> int | None:
    ctx.info(f"Discovering the run_id({branch=}, {nightly=}, {pr=}, {repository=})")
    run_id: int | None = None
    with ctx.web as web:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        github_token = get_github_token(ctx)
        if github_token is not None:
            headers["Authorization"] = f"Bearer {github_token}"
        web.headers.update(headers)

        params: dict[str, str | int] = {
            "per_page": 100,
        }
        if completed_status is True:
            params["status"] = "completed"
        if branch is not None:
            ret = web.get(
                f"https://api.github.com/repos/{repository}/git/ref/heads/{branch}"
            )
            data = ret.json()
            if "message" in data:
                ctx.error(f"Could not find HEAD commit for branch {branch}")
                ctx.exit(1)
            params["event"] = "push"
            head_sha = data["object"]["sha"]
        elif pr is not None:
            ret = web.get(f"https://api.github.com/repos/{repository}/pulls/{pr}")
            data = ret.json()
            params["event"] = "pull_request"
            head_sha = data["head"]["sha"]
        elif nightly == "master":
            ret = web.get(
                f"https://api.github.com/repos/{repository}/git/ref/heads/{nightly}"
            )
            data = ret.json()
            if "message" in data:
                ctx.error(f"Could not find HEAD commit for branch {nightly}")
                ctx.exit(1)
            params["event"] = "schedule"
            head_sha = data["object"]["sha"]
        else:
            ret = web.get(
                f"https://api.github.com/repos/{repository}/git/ref/heads/{nightly}"
            )
            data = ret.json()
            if "message" in data:
                ctx.error(f"Could not find HEAD commit for branch {nightly}")
                ctx.exit(1)
            params["event"] = "workflow_dispatch"
            head_sha = data["object"]["sha"]

        params["head_sha"] = head_sha
        # params.pop("event")
        ctx.info(f"Searching for workflow runs for HEAD SHA: {head_sha}")
        page = 0
        while True:
            if run_id is not None:
                break
            page += 1
            params["page"] = page
            ret = web.get(
                f"https://api.github.com/repos/{repository}/actions/runs", params=params
            )
            data = ret.json()
            ctx.info(
                f"Discovered {data['total_count']} workflow runs for HEAD SHA {head_sha}"
            )
            # ctx.info(data)
            if not data["workflow_runs"]:
                break
            workflow_runs = data["workflow_runs"]
            for workflow_run in workflow_runs:
                run_id = workflow_run["id"]
                break

    if run_id:
        ctx.info(f"Discovered run_id: {run_id}")
    return run_id
