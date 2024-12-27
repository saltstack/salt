"""
noxfile
~~~~~~~

Nox configuration script
"""

# pylint: disable=resource-leakage,3rd-party-module-not-gated

import contextlib
import datetime
import glob
import gzip
import json
import os
import pathlib
import shutil
import sqlite3
import sys
import tarfile
import tempfile

import nox.command

# fmt: off
if __name__ == "__main__":
    sys.stderr.write(
        "Do not execute this file directly. Use nox instead, it will know how to handle this file\n"
    )
    sys.stderr.flush()
    exit(1)
# fmt: on

import nox  # isort:skip
from nox.command import CommandFailed  # isort:skip


REPO_ROOT = pathlib.Path(__file__).resolve().parent
ENV_FILE = REPO_ROOT / ".ci-env"
if ENV_FILE.exists():
    print("Found .ci-env file. Updating environment...", flush=True)
    for key, value in json.loads(ENV_FILE.read_text()).items():
        print(f"  {key}={value}", flush=True)
        os.environ[key] = value
    print("Deleting .ci-env file", flush=True)
    ENV_FILE.unlink()

# Be verbose when running under a CI context
CI_RUN = (
    os.environ.get("JENKINS_URL")
    or os.environ.get("CI")
    or os.environ.get("DRONE") is not None
)
PIP_INSTALL_SILENT = CI_RUN is False
PRINT_TEST_SELECTION = os.environ.get("PRINT_TEST_SELECTION")
if PRINT_TEST_SELECTION is None:
    PRINT_TEST_SELECTION = CI_RUN
else:
    PRINT_TEST_SELECTION = PRINT_TEST_SELECTION == "1"
PRINT_TEST_PLAN_ONLY = os.environ.get("PRINT_TEST_PLAN_ONLY", "0") == "1"
PRINT_SYSTEM_INFO = os.environ.get("PRINT_SYSTEM_INFO")
if PRINT_SYSTEM_INFO is None:
    PRINT_SYSTEM_INFO = CI_RUN
else:
    PRINT_SYSTEM_INFO = PRINT_SYSTEM_INFO == "1"
PRINT_SYSTEM_INFO_ONLY = os.environ.get("PRINT_SYSTEM_INFO_ONLY", "0") == "1"
SKIP_REQUIREMENTS_INSTALL = os.environ.get("SKIP_REQUIREMENTS_INSTALL", "0") == "1"
EXTRA_REQUIREMENTS_INSTALL = os.environ.get("EXTRA_REQUIREMENTS_INSTALL")
COVERAGE_REQUIREMENT = os.environ.get("COVERAGE_REQUIREMENT")

# Global Path Definitions
REPO_ROOT = pathlib.Path(os.path.dirname(__file__)).resolve()
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
COVERAGE_OUTPUT_DIR = ARTIFACTS_DIR / "coverage"
COVERAGE_FILE = os.environ.get("COVERAGE_FILE")
if COVERAGE_FILE is None:
    COVERAGE_FILE = str(COVERAGE_OUTPUT_DIR / ".coverage")
IS_DARWIN = sys.platform.lower().startswith("darwin")
IS_WINDOWS = sys.platform.lower().startswith("win")
IS_FREEBSD = sys.platform.lower().startswith("freebsd")
IS_LINUX = sys.platform.lower().startswith("linux")
ONEDIR_ARTIFACT_PATH = ARTIFACTS_DIR / "salt"
if IS_WINDOWS:
    ONEDIR_PYTHON_PATH = ONEDIR_ARTIFACT_PATH / "Scripts" / "python.exe"
else:
    ONEDIR_PYTHON_PATH = ONEDIR_ARTIFACT_PATH / "bin" / "python3"
# Python versions to run against
_PYTHON_VERSIONS = ("3", "3.8", "3.9", "3.10", "3.11")

# Nox options
#  Reuse existing virtualenvs
nox.options.reuse_existing_virtualenvs = True

# Change current directory to REPO_ROOT
os.chdir(str(REPO_ROOT))

RUNTESTS_LOGFILE = ARTIFACTS_DIR.joinpath(
    "logs",
    "runtests-{}.log".format(datetime.datetime.now().strftime("%Y%m%d%H%M%S.%f")),
)

# Prevent Python from writing bytecode
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def session_warn(session, message):
    try:
        session.warn(message)
    except AttributeError:
        session.log(f"WARNING: {message}")


def session_run_always(session, *command, **kwargs):
    """
    Patch nox to allow running some commands which would be skipped if --install-only is passed.
    """
    try:
        # Guess we weren't the only ones wanting this
        # https://github.com/theacodes/nox/pull/331
        return session.run_always(*command, **kwargs)
    except AttributeError:
        old_install_only_value = session._runner.global_config.install_only
        try:
            # Force install only to be false for the following chunk of code
            # For additional information as to why see:
            #   https://github.com/theacodes/nox/pull/181
            session._runner.global_config.install_only = False
            return session.run(*command, **kwargs)
        finally:
            session._runner.global_config.install_only = old_install_only_value


def find_session_runner(session, name, python_version, onedir=False, **kwargs):
    if onedir:
        name += f"-onedir-{ONEDIR_PYTHON_PATH}"
    else:
        name += f"-{python_version}"
    for s, _ in session._runner.manifest.list_all_sessions():
        if name not in s.signatures:
            continue
        for signature in s.signatures:
            for key, value in kwargs.items():
                param = f"{key}={value!r}"
                if param not in signature:
                    break
            else:
                return s
            continue
    session.error(
        "Could not find a nox session by the name {!r} with the following keyword arguments: {!r}".format(
            name, kwargs
        )
    )


def _create_ci_directories():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    # Allow other users to write to this directory.
    # This helps when some tests run under a different name and yet
    # they need access to this path, for example, code coverage.
    ARTIFACTS_DIR.chmod(0o777)
    COVERAGE_OUTPUT_DIR.mkdir(exist_ok=True)
    COVERAGE_OUTPUT_DIR.chmod(0o777)
    ARTIFACTS_DIR.joinpath("xml-unittests-output").mkdir(exist_ok=True)


def _get_session_python_version_info(session):
    try:
        version_info = session._runner._real_python_version_info
    except AttributeError:
        session_py_version = session_run_always(
            session,
            "python",
            "-c",
            'import sys; sys.stdout.write("{}.{}.{}".format(*sys.version_info))',
            stderr=None,
            silent=True,
            log=False,
        )
        version_info = tuple(
            int(part)
            for part in session_py_version.strip().split(".")
            if part.isdigit()
        )
        session._runner._real_python_version_info = version_info
    return version_info


def _get_pydir(session):
    version_info = _get_session_python_version_info(session)
    if version_info < (3, 8):
        session.error("Only Python >= 3.8 is supported")
    return "py{}.{}".format(*version_info)


def _get_pip_requirements_file(session, crypto=None, requirements_type="ci"):
    assert requirements_type in ("ci", "pkg")
    pydir = _get_pydir(session)

    if IS_WINDOWS:
        if crypto is None:
            _requirements_file = os.path.join(
                "requirements", "static", requirements_type, pydir, "windows.txt"
            )
            if os.path.exists(_requirements_file):
                return _requirements_file
        _requirements_file = os.path.join(
            "requirements", "static", requirements_type, pydir, "windows-crypto.txt"
        )
        if os.path.exists(_requirements_file):
            return _requirements_file
        session.error(f"Could not find a windows requirements file for {pydir}")
    elif IS_DARWIN:
        if crypto is None:
            _requirements_file = os.path.join(
                "requirements", "static", requirements_type, pydir, "darwin.txt"
            )
            if os.path.exists(_requirements_file):
                return _requirements_file
        _requirements_file = os.path.join(
            "requirements", "static", requirements_type, pydir, "darwin-crypto.txt"
        )
        if os.path.exists(_requirements_file):
            return _requirements_file
        session.error(f"Could not find a darwin requirements file for {pydir}")
    elif IS_FREEBSD:
        if crypto is None:
            _requirements_file = os.path.join(
                "requirements", "static", requirements_type, pydir, "freebsd.txt"
            )
            if os.path.exists(_requirements_file):
                return _requirements_file
        _requirements_file = os.path.join(
            "requirements", "static", requirements_type, pydir, "freebsd-crypto.txt"
        )
        if os.path.exists(_requirements_file):
            return _requirements_file
        session.error(f"Could not find a freebsd requirements file for {pydir}")
    else:
        if crypto is None:
            _requirements_file = os.path.join(
                "requirements", "static", requirements_type, pydir, "linux.txt"
            )
            if os.path.exists(_requirements_file):
                return _requirements_file
        _requirements_file = os.path.join(
            "requirements", "static", requirements_type, pydir, "linux-crypto.txt"
        )
        if os.path.exists(_requirements_file):
            return _requirements_file
        session.error(f"Could not find a linux requirements file for {pydir}")


def _upgrade_pip_setuptools_and_wheel(session, upgrade=True):
    if SKIP_REQUIREMENTS_INSTALL:
        session.log(
            "Skipping Python Requirements because SKIP_REQUIREMENTS_INSTALL was found in the environ"
        )
        return False

    env = os.environ.copy()
    env["PIP_CONSTRAINT"] = str(REPO_ROOT / "requirements" / "constraints.txt")
    install_command = [
        "python",
        "-m",
        "pip",
        "install",
        "--progress-bar=off",
    ]
    if upgrade:
        install_command.append("-U")
    install_command.extend(["setuptools", "pip", "wheel"])
    session_run_always(session, *install_command, silent=PIP_INSTALL_SILENT, env=env)
    return True


def _install_requirements(
    session,
    *extra_requirements,
    requirements_type="ci",
    onedir=False,
):
    if onedir and IS_LINUX:
        session_run_always(session, "python3", "-m", "relenv", "toolchain", "fetch")

    if not _upgrade_pip_setuptools_and_wheel(session):
        return False

    # Install requirements
    env = os.environ.copy()
    env["PIP_CONSTRAINT"] = str(REPO_ROOT / "requirements" / "constraints.txt")

    requirements_file = _get_pip_requirements_file(
        session, requirements_type=requirements_type
    )
    install_command = ["--progress-bar=off", "-r", requirements_file]
    session.install(*install_command, silent=PIP_INSTALL_SILENT, env=env)

    if extra_requirements:
        install_command = ["--progress-bar=off"]
        install_command += list(extra_requirements)
        session.install(*install_command, silent=PIP_INSTALL_SILENT, env=env)

    if EXTRA_REQUIREMENTS_INSTALL:
        session.log(
            "Installing the following extra requirements because the"
            " EXTRA_REQUIREMENTS_INSTALL environment variable was set: %s",
            EXTRA_REQUIREMENTS_INSTALL,
        )
        # We pass --constraint in this step because in case any of these extra dependencies has a requirement
        # we're already using, we want to maintain the locked version
        install_command = ["--progress-bar=off", "--constraint", requirements_file]
        install_command += EXTRA_REQUIREMENTS_INSTALL.split()
        session.install(*install_command, silent=PIP_INSTALL_SILENT, env=env)

    return True


def _install_coverage_requirement(session):
    if SKIP_REQUIREMENTS_INSTALL is False:
        env = os.environ.copy()
        env["PIP_CONSTRAINT"] = str(REPO_ROOT / "requirements" / "constraints.txt")
        coverage_requirement = COVERAGE_REQUIREMENT
        if coverage_requirement is None:
            coverage_requirement = "coverage==7.3.1"
            if IS_LINUX:
                distro_slug = os.environ.get("TOOLS_DISTRO_SLUG")
                if distro_slug is not None and distro_slug in (
                    "centos-7",
                    "debian-10",
                    "photonos-3",
                ):
                    # Keep the old coverage requirement version since the new one, on these
                    # Plaforms turns the test suite quite slow.
                    # Unit tests don't finish before the 5 hours timeout when they should
                    # finish within 1 to 2 hours.
                    coverage_requirement = "coverage==5.5"
        session.install(
            "--progress-bar=off",
            coverage_requirement,
            silent=PIP_INSTALL_SILENT,
            env=env,
        )


def _run_with_coverage(session, *test_cmd, env=None, on_rerun=False):
    _install_coverage_requirement(session)
    if on_rerun is False:
        session.run("coverage", "erase")

    if env is None:
        env = {}

    sitecustomize_dir = session.run(
        "salt-factories", "--coverage", silent=True, log=True, stderr=None
    )
    if sitecustomize_dir is not None:
        sitecustomize_dir = pathlib.Path(sitecustomize_dir.strip()).resolve()
        if not sitecustomize_dir.exists():
            session.error(
                f"The path to 'sitecustomize.py', '{str(sitecustomize_dir)}', does not exist."
            )

    if sitecustomize_dir:
        try:
            relative_sitecustomize_dir = sitecustomize_dir.relative_to(REPO_ROOT)
        except ValueError:
            relative_sitecustomize_dir = sitecustomize_dir
        log_msg = f"Discovered salt-factories coverage 'sitecustomize.py' path: {relative_sitecustomize_dir}"
        try:
            session.debug(log_msg)
        except AttributeError:
            # Older nox
            session.log(log_msg)
        python_path_env_var = os.environ.get("PYTHONPATH") or None
        if python_path_env_var is None:
            python_path_env_var = str(sitecustomize_dir)
        else:
            python_path_entries = python_path_env_var.split(os.pathsep)
            if str(sitecustomize_dir) in python_path_entries:
                python_path_entries.remove(str(sitecustomize_dir))
            python_path_entries.insert(0, str(sitecustomize_dir))
            python_path_env_var = os.pathsep.join(python_path_entries)

        env.update(
            {
                # The updated python path so that sitecustomize is importable
                "PYTHONPATH": python_path_env_var,
                # Instruct sub processes to also run under coverage
                "COVERAGE_PROCESS_START": str(REPO_ROOT / ".coveragerc"),
                # The full path to the .coverage data file. Makes sure we always write
                # them to the same directory
                "COVERAGE_FILE": COVERAGE_FILE,
            }
        )

    session.run(*test_cmd, env=env)


def _report_coverage(
    session,
    combine=True,
    cli_report=True,
    html_report=False,
    xml_report=False,
    json_report=False,
):
    _install_coverage_requirement(session)

    if not any([combine, cli_report, html_report, xml_report, json_report]):
        session.error(
            "At least one of combine, cli_report, html_report, xml_report, json_report needs to be True"
        )

    env = {
        # The full path to the .coverage data file. Makes sure we always write
        # them to the same directory
        "COVERAGE_FILE": COVERAGE_FILE,
    }

    report_section = None
    if session.posargs:
        report_section = session.posargs.pop(0)
        if report_section not in ("salt", "tests"):
            session.error(
                f"The report section can only be one of 'salt', 'tests', not: {report_section}"
            )
        if session.posargs:
            session.error(
                "Only one argument can be passed to the session, which is optional "
                "and is one of 'salt', 'tests'."
            )

    if combine is True:
        coverage_db_files = glob.glob(f"{COVERAGE_FILE}.*")
        if coverage_db_files:
            with contextlib.suppress(CommandFailed):
                # Sometimes some of the coverage files are corrupt which would trigger a CommandFailed
                # exception
                session.run("coverage", "combine", env=env)
        elif os.path.exists(COVERAGE_FILE):
            session_warn(session, "Coverage files already combined.")

        if os.path.exists(COVERAGE_FILE) and not IS_WINDOWS:
            # Some coverage files might have come from a windows machine, fix paths
            with sqlite3.connect(COVERAGE_FILE) as db:
                res = db.execute(r"SELECT * FROM file WHERE path LIKE '%salt\%'")
                if res.fetchone():
                    session_warn(
                        session,
                        "Replacing backwards slashes with forward slashes on file "
                        "paths in the coverage database",
                    )
                    db.execute(
                        r"UPDATE OR IGNORE file SET path=replace(path, '\', '/');"
                    )

    if not os.path.exists(COVERAGE_FILE):
        session.error("No coverage files found.")

    if report_section == "salt":
        json_coverage_file = COVERAGE_OUTPUT_DIR.relative_to(REPO_ROOT) / "salt.json"
        xml_coverage_file = COVERAGE_OUTPUT_DIR.relative_to(REPO_ROOT) / "salt.xml"
        html_coverage_dir = COVERAGE_OUTPUT_DIR.relative_to(REPO_ROOT) / "html" / "salt"
        cmd_args = [
            "--omit=tests/*,tests/pytests/pkg/*",
            "--include=salt/*",
        ]

    elif report_section == "tests":
        json_coverage_file = COVERAGE_OUTPUT_DIR.relative_to(REPO_ROOT) / "tests.json"
        xml_coverage_file = COVERAGE_OUTPUT_DIR.relative_to(REPO_ROOT) / "tests.xml"
        html_coverage_dir = (
            COVERAGE_OUTPUT_DIR.relative_to(REPO_ROOT) / "html" / "tests"
        )
        cmd_args = [
            "--omit=salt/*",
            "--include=tests/*,tests/pytests/pkg/*",
        ]
    else:
        json_coverage_file = (
            COVERAGE_OUTPUT_DIR.relative_to(REPO_ROOT) / "coverage.json"
        )
        xml_coverage_file = COVERAGE_OUTPUT_DIR.relative_to(REPO_ROOT) / "coverage.xml"
        html_coverage_dir = COVERAGE_OUTPUT_DIR.relative_to(REPO_ROOT) / "html" / "full"
        cmd_args = [
            "--include=salt/*,tests/*,tests/pytests/pkg/*",
        ]

    if cli_report:
        session.run(
            "coverage",
            "report",
            "--precision=2",
            *cmd_args,
            env=env,
        )

    if html_report:
        session.run(
            "coverage",
            "html",
            "-d",
            str(html_coverage_dir),
            "--show-contexts",
            "--precision=2",
            *cmd_args,
            env=env,
        )

    if xml_report:
        try:
            session.run(
                "coverage",
                "xml",
                "-o",
                str(xml_coverage_file),
                *cmd_args,
                env=env,
            )
        except CommandFailed:
            session_warn(
                session, "Failed to generate the source XML code coverage report"
            )

    if json_report:
        session.run(
            "coverage",
            "json",
            "-o",
            str(json_coverage_file),
            "--show-contexts",
            *cmd_args,
            env=env,
        )


@nox.session(python=_PYTHON_VERSIONS, name="test-parametrized")
@nox.parametrize("coverage", [False, True])
@nox.parametrize("transport", ["zeromq", "tcp"])
@nox.parametrize("crypto", [None, "m2crypto", "pycryptodome"])
def test_parametrized(session, coverage, transport, crypto):
    """
    DO NOT CALL THIS NOX SESSION DIRECTLY
    """
    # Install requirements
    if _install_requirements(session):

        if crypto:
            session_run_always(
                session,
                "pip",
                "uninstall",
                "-y",
                "m2crypto",
                "pycrypto",
                "pycryptodome",
                "pycryptodomex",
                silent=True,
            )
            install_command = [
                "--progress-bar=off",
                "--constraint",
                _get_pip_requirements_file(session, crypto=True),
            ]
            install_command.append(crypto)
            session.install(*install_command, silent=PIP_INSTALL_SILENT)

    cmd_args = [
        f"--transport={transport}",
    ] + session.posargs
    _pytest(session, coverage=coverage, cmd_args=cmd_args)


@nox.session(python=_PYTHON_VERSIONS)
@nox.parametrize("coverage", [False, True])
def test(session, coverage):
    """
    pytest session with zeromq transport and default crypto
    """
    session.notify(
        find_session_runner(
            session,
            "test-parametrized",
            session.python,
            coverage=coverage,
            crypto=None,
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS)
@nox.parametrize("coverage", [False, True])
def pytest(session, coverage):
    """
    pytest session with zeromq transport and default crypto
    """
    try:
        session_name = session.name
    except AttributeError:
        session_name = session._runner.friendly_name
    session_warn(
        session,
        "This nox session is deprecated, please call {!r} instead".format(
            session_name.replace("pytest-", "test-")
        ),
    )
    session.notify(session_name.replace("pytest-", "test-"))


@nox.session(python=_PYTHON_VERSIONS, name="test-tcp")
@nox.parametrize("coverage", [False, True])
def test_tcp(session, coverage):
    """
    pytest session with TCP transport and default crypto
    """
    session.notify(
        find_session_runner(
            session,
            "test-parametrized",
            session.python,
            coverage=coverage,
            crypto=None,
            transport="tcp",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-tcp")
@nox.parametrize("coverage", [False, True])
def pytest_tcp(session, coverage):
    """
    pytest session with TCP transport and default crypto
    """
    try:
        session_name = session.name
    except AttributeError:
        session_name = session._runner.friendly_name
    session_warn(
        session,
        "This nox session is deprecated, please call {!r} instead".format(
            session_name.replace("pytest-", "test-")
        ),
    )
    session.notify(session_name.replace("pytest-", "test-"))


@nox.session(python=_PYTHON_VERSIONS, name="test-zeromq")
@nox.parametrize("coverage", [False, True])
def test_zeromq(session, coverage):
    """
    pytest session with zeromq transport and default crypto
    """
    session.notify(
        find_session_runner(
            session,
            "test-parametrized",
            session.python,
            coverage=coverage,
            crypto=None,
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-zeromq")
@nox.parametrize("coverage", [False, True])
def pytest_zeromq(session, coverage):
    """
    pytest session with zeromq transport and default crypto
    """
    try:
        session_name = session.name
    except AttributeError:
        session_name = session._runner.friendly_name
    session_warn(
        session,
        "This nox session is deprecated, please call {!r} instead".format(
            session_name.replace("pytest-", "test-")
        ),
    )
    session.notify(session_name.replace("pytest-", "test-"))


@nox.session(python=_PYTHON_VERSIONS, name="test-m2crypto")
@nox.parametrize("coverage", [False, True])
def test_m2crypto(session, coverage):
    """
    pytest session with zeromq transport and m2crypto
    """
    session.notify(
        find_session_runner(
            session,
            "test-parametrized",
            session.python,
            coverage=coverage,
            crypto="m2crypto",
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-m2crypto")
@nox.parametrize("coverage", [False, True])
def pytest_m2crypto(session, coverage):
    """
    pytest session with zeromq transport and m2crypto
    """
    try:
        session_name = session.name
    except AttributeError:
        session_name = session._runner.friendly_name
    session_warn(
        session,
        "This nox session is deprecated, please call {!r} instead".format(
            session_name.replace("pytest-", "test-")
        ),
    )
    session.notify(session_name.replace("pytest-", "test-"))


@nox.session(python=_PYTHON_VERSIONS, name="test-tcp-m2crypto")
@nox.parametrize("coverage", [False, True])
def test_tcp_m2crypto(session, coverage):
    """
    pytest session with TCP transport and m2crypto
    """
    session.notify(
        find_session_runner(
            session,
            "test-parametrized",
            session.python,
            coverage=coverage,
            crypto="m2crypto",
            transport="tcp",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-tcp-m2crypto")
@nox.parametrize("coverage", [False, True])
def pytest_tcp_m2crypto(session, coverage):
    """
    pytest session with TCP transport and m2crypto
    """
    try:
        session_name = session.name
    except AttributeError:
        session_name = session._runner.friendly_name
    session_warn(
        session,
        "This nox session is deprecated, please call {!r} instead".format(
            session_name.replace("pytest-", "test-")
        ),
    )
    session.notify(session_name.replace("pytest-", "test-"))


@nox.session(python=_PYTHON_VERSIONS, name="test-zeromq-m2crypto")
@nox.parametrize("coverage", [False, True])
def test_zeromq_m2crypto(session, coverage):
    """
    pytest session with zeromq transport and m2crypto
    """
    session.notify(
        find_session_runner(
            session,
            "test-parametrized",
            session.python,
            coverage=coverage,
            crypto="m2crypto",
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-zeromq-m2crypto")
@nox.parametrize("coverage", [False, True])
def pytest_zeromq_m2crypto(session, coverage):
    """
    pytest session with zeromq transport and m2crypto
    """
    try:
        session_name = session.name
    except AttributeError:
        session_name = session._runner.friendly_name
    session_warn(
        session,
        "This nox session is deprecated, please call {!r} instead".format(
            session_name.replace("pytest-", "test-")
        ),
    )
    session.notify(session_name.replace("pytest-", "test-"))


@nox.session(python=_PYTHON_VERSIONS, name="test-pycryptodome")
@nox.parametrize("coverage", [False, True])
def test_pycryptodome(session, coverage):
    """
    pytest session with zeromq transport and pycryptodome
    """
    session.notify(
        find_session_runner(
            session,
            "test-parametrized",
            session.python,
            coverage=coverage,
            crypto="pycryptodome",
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-pycryptodome")
@nox.parametrize("coverage", [False, True])
def pytest_pycryptodome(session, coverage):
    """
    pytest session with zeromq transport and pycryptodome
    """
    try:
        session_name = session.name
    except AttributeError:
        session_name = session._runner.friendly_name
    session_warn(
        session,
        "This nox session is deprecated, please call {!r} instead".format(
            session_name.replace("pytest-", "test-")
        ),
    )
    session.notify(session_name.replace("pytest-", "test-"))


@nox.session(python=_PYTHON_VERSIONS, name="test-tcp-pycryptodome")
@nox.parametrize("coverage", [False, True])
def test_tcp_pycryptodome(session, coverage):
    """
    pytest session with TCP transport and pycryptodome
    """
    session.notify(
        find_session_runner(
            session,
            "test-parametrized",
            session.python,
            coverage=coverage,
            crypto="pycryptodome",
            transport="tcp",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-tcp-pycryptodome")
@nox.parametrize("coverage", [False, True])
def pytest_tcp_pycryptodome(session, coverage):
    """
    pytest session with TCP transport and pycryptodome
    """
    try:
        session_name = session.name
    except AttributeError:
        session_name = session._runner.friendly_name
    session_warn(
        session,
        "This nox session is deprecated, please call {!r} instead".format(
            session_name.replace("pytest-", "test-")
        ),
    )
    session.notify(session_name.replace("pytest-", "test-"))


@nox.session(python=_PYTHON_VERSIONS, name="test-zeromq-pycryptodome")
@nox.parametrize("coverage", [False, True])
def test_zeromq_pycryptodome(session, coverage):
    """
    pytest session with zeromq transport and pycryptodome
    """
    session.notify(
        find_session_runner(
            session,
            "test-parametrized",
            session.python,
            coverage=coverage,
            crypto="pycryptodome",
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-zeromq-pycryptodome")
@nox.parametrize("coverage", [False, True])
def pytest_zeromq_pycryptodome(session, coverage):
    """
    pytest session with zeromq transport and pycryptodome
    """
    try:
        session_name = session.name
    except AttributeError:
        session_name = session._runner.friendly_name
    session_warn(
        session,
        "This nox session is deprecated, please call {!r} instead".format(
            session_name.replace("pytest-", "test-")
        ),
    )
    session.notify(session_name.replace("pytest-", "test-"))


@nox.session(python=_PYTHON_VERSIONS, name="test-cloud")
@nox.parametrize("coverage", [False, True])
def test_cloud(session, coverage):
    """
    pytest cloud tests session
    """
    pydir = _get_pydir(session)
    if pydir == "py3.5":
        session.error(
            "Due to conflicting and unsupported requirements the cloud tests only run on Py3.6+"
        )
    # Install requirements
    if _upgrade_pip_setuptools_and_wheel(session):
        linux_requirements_file = os.path.join(
            "requirements", "static", "ci", pydir, "linux.txt"
        )
        cloud_requirements_file = os.path.join(
            "requirements", "static", "ci", pydir, "cloud.txt"
        )

        install_command = [
            "--progress-bar=off",
            "-r",
            linux_requirements_file,
            "-r",
            cloud_requirements_file,
        ]
        session.install(*install_command, silent=PIP_INSTALL_SILENT)

    cmd_args = [
        "--run-expensive",
        "-k",
        "cloud",
    ] + session.posargs
    _pytest(session, coverage=coverage, cmd_args=cmd_args)


@nox.session(python=_PYTHON_VERSIONS, name="pytest-cloud")
@nox.parametrize("coverage", [False, True])
def pytest_cloud(session, coverage):
    """
    pytest cloud tests session
    """
    try:
        session_name = session.name
    except AttributeError:
        session_name = session._runner.friendly_name
    session_warn(
        session,
        "This nox session is deprecated, please call {!r} instead".format(
            session_name.replace("pytest-", "test-")
        ),
    )
    session.notify(session_name.replace("pytest-", "test-"))


@nox.session(python=_PYTHON_VERSIONS, name="test-tornado")
@nox.parametrize("coverage", [False, True])
def test_tornado(session, coverage):
    """
    pytest tornado tests session
    """
    # Install requirements
    if _upgrade_pip_setuptools_and_wheel(session):
        _install_requirements(session)
        session.install(
            "--progress-bar=off", "tornado==5.0.2", silent=PIP_INSTALL_SILENT
        )
        session.install(
            "--progress-bar=off", "pyzmq==17.0.0", silent=PIP_INSTALL_SILENT
        )
    _pytest(session, coverage=coverage, cmd_args=session.posargs)


@nox.session(python=_PYTHON_VERSIONS, name="pytest-tornado")
@nox.parametrize("coverage", [False, True])
def pytest_tornado(session, coverage):
    """
    pytest tornado tests session
    """
    try:
        session_name = session.name
    except AttributeError:
        session_name = session._runner.friendly_name
    session_warn(
        session,
        "This nox session is deprecated, please call {!r} instead".format(
            session_name.replace("pytest-", "test-")
        ),
    )
    session.notify(session_name.replace("pytest-", "test-"))


def _pytest(session, coverage, cmd_args, env=None, on_rerun=False):
    # Create required artifacts directories
    _create_ci_directories()

    if env is None:
        env = {}

    env["CI_RUN"] = "1" if CI_RUN else "0"

    args = [
        "--rootdir",
        str(REPO_ROOT),
        "--log-file-level=debug",
        "--show-capture=no",
        "-ra",
        "-s",
        "-vv",
        "--showlocals",
    ]
    for arg in cmd_args:
        if arg == "--log-file" or arg.startswith("--log-file="):
            break
    else:
        args.append(f"--log-file={RUNTESTS_LOGFILE}")
    args.extend(cmd_args)

    if PRINT_SYSTEM_INFO_ONLY and "--sys-info-and-exit" not in args:
        args.append("--sys-info-and-exit")
        session.run("python", "-m", "pytest", *args, env=env)
        return

    if PRINT_SYSTEM_INFO and "--sysinfo" not in args:
        args.append("--sysinfo")

    if PRINT_TEST_SELECTION:
        # We'll print out the collected tests on CI runs.
        # This will show a full list of what tests are going to run, in the right order, which, in case
        # of a test suite hang, helps us pinpoint which test is hanging
        session.run(
            "python", "-m", "pytest", *(args + ["--collect-only", "-qqq"]), env=env
        )
        if PRINT_TEST_PLAN_ONLY:
            return

    if coverage is True:
        _coverage_cmd_args = []
        if "COVERAGE_CONTEXT" in os.environ:
            _coverage_cmd_args.append(f"--context={os.environ['COVERAGE_CONTEXT']}")
        _run_with_coverage(
            session,
            "python",
            "-m",
            "coverage",
            "run",
            *_coverage_cmd_args,
            "-m",
            "pytest",
            *args,
            env=env,
            on_rerun=on_rerun,
        )
    else:
        session.run("python", "-m", "pytest", *args, env=env)


def _ci_test(session, transport, onedir=False):
    # Install requirements
    _install_requirements(session, onedir=onedir)
    env = {}
    if onedir:
        env["ONEDIR_TESTRUN"] = "1"
    chunks = {
        "pkg": [
            "tests/pytests/pkg",
        ],
        "unit": [
            "tests/unit",
            "tests/pytests/unit",
        ],
        "functional": [
            "tests/pytests/functional",
        ],
        "scenarios": [
            "tests/pytests/scenarios",
        ],
    }

    test_group_number = os.environ.get("TEST_GROUP") or "1"

    if not session.posargs:
        chunk_cmd = []
        junit_report_filename = "test-results"
        runtests_log_filename = "runtests"
    else:
        chunk = session.posargs.pop(0)
        if chunk in ["unit", "functional", "integration", "scenarios", "all"]:
            if chunk == "all":
                chunk_cmd = []
                junit_report_filename = "test-results"
                runtests_log_filename = "runtests"
            elif chunk == "integration":
                chunk_cmd = []
                for values in chunks.values():
                    for value in values:
                        chunk_cmd.append(f"--ignore={value}")
                junit_report_filename = f"test-results-{chunk}-grp{test_group_number}"
                runtests_log_filename = f"runtests-{chunk}-grp{test_group_number}"
            else:
                chunk_cmd = chunks[chunk]
                junit_report_filename = f"test-results-{chunk}-grp{test_group_number}"
                runtests_log_filename = f"runtests-{chunk}-grp{test_group_number}"
            if session.posargs:
                if session.posargs[0] == "--":
                    session.posargs.pop(0)
                chunk_cmd.extend(session.posargs)
        else:
            chunk_cmd = [chunk] + session.posargs
            junit_report_filename = f"test-results-grp{test_group_number}"
            runtests_log_filename = f"runtests-grp{test_group_number}"

    rerun_failures = os.environ.get("RERUN_FAILURES", "0") == "1"
    track_code_coverage = os.environ.get("SKIP_CODE_COVERAGE", "0") == "0"

    common_pytest_args = [
        "--color=yes",
        "--ssh-tests",
        "--sys-stats",
        "--run-destructive",
        f"--output-columns={os.environ.get('OUTPUT_COLUMNS') or 120}",
    ]
    try:
        pytest_args = (
            common_pytest_args[:]
            + [
                f"--junitxml=artifacts/xml-unittests-output/{junit_report_filename}.xml",
                f"--log-file=artifacts/logs/{runtests_log_filename}.log",
            ]
            + chunk_cmd
        )
        _pytest(session, coverage=track_code_coverage, cmd_args=pytest_args, env=env)
    except CommandFailed:
        if rerun_failures is False:
            raise

        # Don't print the system information, not the test selection on reruns
        global PRINT_TEST_SELECTION
        global PRINT_SYSTEM_INFO
        PRINT_TEST_SELECTION = False
        PRINT_SYSTEM_INFO = False

        pytest_args = (
            common_pytest_args[:]
            + [
                "--lf",
                f"--junitxml=artifacts/xml-unittests-output/{junit_report_filename}-rerun.xml",
                f"--log-file=artifacts/logs/{runtests_log_filename}-rerun.log",
            ]
            + chunk_cmd
        )
        _pytest(
            session,
            coverage=track_code_coverage,
            cmd_args=pytest_args,
            env=env,
            on_rerun=True,
        )


@nox.session(python=_PYTHON_VERSIONS, name="ci-test")
def ci_test(session):
    transport = os.environ.get("SALT_TRANSPORT") or "zeromq"
    valid_transports = ("zeromq", "tcp")
    if transport not in valid_transports:
        session.error(
            "The value for the SALT_TRANSPORT environment variable can only be "
            f"one of: {', '.join(valid_transports)}"
        )
    _ci_test(session, transport)


@nox.session(python=_PYTHON_VERSIONS, name="ci-test-tcp")
def ci_test_tcp(session):
    _ci_test(session, "tcp")


@nox.session(
    python=str(ONEDIR_PYTHON_PATH),
    name="ci-test-onedir",
    venv_params=["--system-site-packages"],
)
def ci_test_onedir(session):
    if not ONEDIR_ARTIFACT_PATH.exists():
        session.error(
            "The salt onedir artifact, expected to be in '{}', was not found".format(
                ONEDIR_ARTIFACT_PATH.relative_to(REPO_ROOT)
            )
        )

    transport = os.environ.get("SALT_TRANSPORT") or "zeromq"
    valid_transports = ("zeromq", "tcp")
    if transport not in valid_transports:
        session.error(
            "The value for the SALT_TRANSPORT environment variable can only be "
            f"one of: {', '.join(valid_transports)}"
        )

    _ci_test(session, "zeromq", onedir=True)


@nox.session(
    python=str(ONEDIR_PYTHON_PATH),
    name="ci-test-onedir-tcp",
    venv_params=["--system-site-packages"],
)
def ci_test_onedir_tcp(session):
    if not ONEDIR_ARTIFACT_PATH.exists():
        session.error(
            "The salt onedir artifact, expected to be in '{}', was not found".format(
                ONEDIR_ARTIFACT_PATH.relative_to(REPO_ROOT)
            )
        )

    _ci_test(session, "tcp", onedir=True)


@nox.session(python="3", name="report-coverage")
def report_coverage(session):
    _report_coverage(session, combine=True, cli_report=True)


@nox.session(python="3", name="coverage-report")
def coverage_report(session):
    _report_coverage(session, combine=True, cli_report=True)


@nox.session(python=False, name="decompress-dependencies")
def decompress_dependencies(session):
    if not session.posargs:
        session.error(
            "The 'decompress-dependencies' session target needs "
            "two arguments, '<platform> <arch>'."
        )
    try:
        platform = session.posargs.pop(0)
        arch = session.posargs.pop(0)
        if session.posargs:
            session.error(
                "The 'decompress-dependencies' session target only accepts "
                "two arguments, '<platform> <arch>'."
            )
    except IndexError:
        session.error(
            "The 'decompress-dependencies' session target needs "
            "two arguments, '<platform> <arch>'."
        )
    if platform == "windows":
        extension = "tar.gz"
        scripts_dir_name = "Scripts"
    else:
        extension = "tar.xz"
        scripts_dir_name = "bin"
    nox_dependencies_tarball = f"nox.{platform}.{arch}.{extension}"
    nox_dependencies_tarball_path = REPO_ROOT / nox_dependencies_tarball
    if not nox_dependencies_tarball_path.exists():
        session.error(
            f"The {nox_dependencies_tarball} file "
            "does not exist. Not decompressing anything."
        )

    session_run_always(session, "tar", "xpf", nox_dependencies_tarball)
    if os.environ.get("DELETE_NOX_ARCHIVE", "0") == "1":
        nox_dependencies_tarball_path.unlink()

    session.log("Finding broken 'python' symlinks under '.nox/' ...")
    for dirname in os.scandir(REPO_ROOT / ".nox"):
        scan_path = REPO_ROOT.joinpath(".nox", dirname, scripts_dir_name)
        script_paths = {str(p): p for p in os.scandir(scan_path)}
        fixed_shebang = f"#!{scan_path / 'python'}"
        for key in sorted(script_paths):
            path = script_paths[key]
            if path.is_symlink():
                broken_link = pathlib.Path(path)
                resolved_link = os.readlink(path)
                if not os.path.isabs(resolved_link):
                    # Relative symlinks, resolve them
                    resolved_link = os.path.join(scan_path, resolved_link)
                if not os.path.exists(resolved_link):
                    session.log("The symlink %r looks to be broken", resolved_link)
                    # This is a broken link, fix it
                    resolved_link_suffix = resolved_link.split(
                        f"artifacts{os.sep}salt{os.sep}"
                    )[-1]
                    fixed_link = REPO_ROOT.joinpath(
                        "artifacts", "salt", resolved_link_suffix
                    )
                    session.log(
                        "Fixing broken symlink in nox virtualenv %r, from %r to %r",
                        dirname.name,
                        resolved_link,
                        str(fixed_link.relative_to(REPO_ROOT)),
                    )
                    broken_link.unlink()
                    broken_link.symlink_to(fixed_link)
                continue
            if not path.is_file():
                continue
            if platform != "windows":
                # Let's try to fix shebang's
                try:
                    fpath = pathlib.Path(path)
                    contents = fpath.read_text(encoding="utf-8").splitlines()
                    if (
                        contents[0].startswith("#!")
                        and contents[0].endswith("python")
                        and contents[0] != fixed_shebang
                    ):
                        session.log(
                            "Fixing broken shebang in %r",
                            str(fpath.relative_to(REPO_ROOT)),
                        )
                        fpath.write_text(
                            "\n".join([fixed_shebang] + contents[1:]), encoding="utf-8"
                        )
                except UnicodeDecodeError:
                    pass


@nox.session(python=False, name="compress-dependencies")
def compress_dependencies(session):
    if not session.posargs:
        session.error(
            "The 'compress-dependencies' session target needs "
            "two arguments, '<platform> <arch>'."
        )
    try:
        platform = session.posargs.pop(0)
        arch = session.posargs.pop(0)
        if session.posargs:
            session.error(
                "The 'compress-dependencies' session target only accepts "
                "two arguments, '<platform> <arch>'."
            )
    except IndexError:
        session.error(
            "The 'compress-dependencies' session target needs "
            "two arguments, '<platform> <arch>'."
        )
    if platform == "windows":
        extension = "tar.gz"
    else:
        extension = "tar.xz"
    nox_dependencies_tarball = f"nox.{platform}.{arch}.{extension}"
    nox_dependencies_tarball_path = REPO_ROOT / nox_dependencies_tarball
    if nox_dependencies_tarball_path.exists():
        session_warn(
            session, f"Found existing {nox_dependencies_tarball}. Deleting it."
        )
        nox_dependencies_tarball_path.unlink()

    session_run_always(
        session,
        "tar",
        "-caf",
        nox_dependencies_tarball,
        "--exclude=.nox/pre-archive-cleanup",
        ".nox",
    )


@nox.session(
    python=str(ONEDIR_PYTHON_PATH),
    name="pre-archive-cleanup",
)
@nox.parametrize("pkg", [False, True])
def pre_archive_cleanup(session, pkg):
    """
    Call `tools pkg pre-archive-cleanup <path>`
    """
    if session.posargs:
        session.error("No additional arguments can be passed to 'pre-archive-cleanup'")
    version_info = _get_session_python_version_info(session)
    if version_info < (3, 10):
        session.error(
            "The nox session 'pre-archive-cleanup' needs Python 3.10+ to run."
        )

    if _upgrade_pip_setuptools_and_wheel(session):
        requirements_file = os.path.join(
            "requirements", "static", "ci", _get_pydir(session), "tools.txt"
        )
        install_command = ["--progress-bar=off", "-r", requirements_file]
        session.install(*install_command, silent=PIP_INSTALL_SILENT)

    cmdline = [
        "tools",
        "pkg",
        "pre-archive-cleanup",
    ]
    if pkg:
        cmdline.append("--pkg")
    cmdline.append(".nox")
    session_run_always(session, *cmdline)


@nox.session(python="3", name="combine-coverage")
def combine_coverage(session):
    _report_coverage(session, combine=True, cli_report=False)


@nox.session(
    python=str(ONEDIR_PYTHON_PATH),
    name="combine-coverage-onedir",
    venv_params=["--system-site-packages"],
)
def combine_coverage_onedir(session):
    _report_coverage(session, combine=True, cli_report=False)


@nox.session(python="3", name="create-html-coverage-report")
def create_html_coverage_report(session):
    _report_coverage(session, combine=True, cli_report=False, html_report=True)


def _create_xml_coverage_reports(session):
    if session.posargs:
        session.error("No arguments are acceptable to this nox session.")
    session.posargs.append("salt")
    _report_coverage(session, combine=True, cli_report=False, xml_report=True)
    session.posargs.append("tests")
    _report_coverage(session, combine=True, cli_report=False, xml_report=True)


@nox.session(python="3", name="create-xml-coverage-reports")
def create_xml_coverage_reports(session):
    _create_xml_coverage_reports(session)


@nox.session(
    python=str(ONEDIR_PYTHON_PATH),
    name="create-xml-coverage-reports-onedir",
    venv_params=["--system-site-packages"],
)
def create_xml_coverage_reports_onedir(session):
    _create_xml_coverage_reports(session)


@nox.session(python="3", name="create-json-coverage-reports")
def create_json_coverage_reports(session):
    _report_coverage(session, combine=True, cli_report=False, json_report=True)


@nox.session(
    python=str(ONEDIR_PYTHON_PATH),
    name="create-json-coverage-reports-onedir",
    venv_params=["--system-site-packages"],
)
def create_json_coverage_reports_onedir(session):
    _report_coverage(session, combine=True, cli_report=False, json_report=True)


class Tee:
    """
    Python class to mimic linux tee behaviour
    """

    def __init__(self, first, second):
        self._first = first
        self._second = second

    def write(self, b):
        wrote = self._first.write(b)
        self._first.flush()
        self._second.write(b)
        self._second.flush()

    def fileno(self):
        return self._first.fileno()


def _lint(session, rcfile, flags, paths, upgrade_setuptools_and_pip=True):
    if _upgrade_pip_setuptools_and_wheel(session, upgrade=upgrade_setuptools_and_pip):
        linux_requirements_file = os.path.join(
            "requirements", "static", "ci", _get_pydir(session), "linux.txt"
        )
        lint_requirements_file = os.path.join(
            "requirements", "static", "ci", _get_pydir(session), "lint.txt"
        )
        install_command = [
            "--progress-bar=off",
            "-r",
            linux_requirements_file,
            "-r",
            lint_requirements_file,
        ]
        session.install(*install_command, silent=PIP_INSTALL_SILENT)

    cmd_args = ["pylint", f"--rcfile={rcfile}"] + list(flags) + list(paths)
    cmd_kwargs = {"env": {"PYTHONUNBUFFERED": "1"}}
    session.run(*cmd_args, **cmd_kwargs)


def _lint_pre_commit(session, rcfile, flags, paths):
    if "VIRTUAL_ENV" not in os.environ:
        session.error(
            "This should be running from within a virtualenv and "
            "'VIRTUAL_ENV' was not found as an environment variable."
        )
    if "pre-commit" not in os.environ["VIRTUAL_ENV"]:
        session.error(
            "This should be running from within a pre-commit virtualenv and "
            "'VIRTUAL_ENV'({}) does not appear to be a pre-commit virtualenv.".format(
                os.environ["VIRTUAL_ENV"]
            )
        )
    from nox.virtualenv import VirtualEnv

    # Let's patch nox to make it run inside the pre-commit virtualenv
    session._runner.venv = VirtualEnv(
        os.environ["VIRTUAL_ENV"],
        interpreter=session._runner.func.python,
        reuse_existing=True,
        venv=True,
    )
    _lint(
        session,
        rcfile,
        flags,
        paths,
        upgrade_setuptools_and_pip=False,
    )


@nox.session(python="3")
def lint(session):
    """
    Run PyLint against Salt and it's test suite.
    """
    session.notify(f"lint-salt-{session.python}")
    session.notify(f"lint-tests-{session.python}")


@nox.session(python="3", name="lint-salt")
def lint_salt(session):
    """
    Run PyLint against Salt.
    """
    flags = ["--disable=I"]
    if session.posargs:
        paths = session.posargs
    else:
        # TBD replace paths entries when implement pyproject.toml
        paths = ["setup.py", "noxfile.py", "salt/", "tools/"]
    _lint(session, ".pylintrc", flags, paths)


@nox.session(python="3", name="lint-tests")
def lint_tests(session):
    """
    Run PyLint against Salt and it's test suite.
    """
    flags = ["--disable=I"]
    if session.posargs:
        paths = session.posargs
    else:
        paths = ["tests/"]
    _lint(session, ".pylintrc", flags, paths)


@nox.session(python=False, name="lint-salt-pre-commit")
def lint_salt_pre_commit(session):
    """
    Run PyLint against Salt.
    """
    flags = ["--disable=I"]
    if session.posargs:
        paths = session.posargs
    else:
        paths = ["setup.py", "noxfile.py", "salt/", "tools/"]
    _lint_pre_commit(session, ".pylintrc", flags, paths)


@nox.session(python=False, name="lint-tests-pre-commit")
def lint_tests_pre_commit(session):
    """
    Run PyLint against Salt and it's test suite.
    """
    flags = ["--disable=I"]
    if session.posargs:
        paths = session.posargs
    else:
        paths = ["tests/"]
    _lint_pre_commit(session, ".pylintrc", flags, paths)


@nox.session(python="3")
@nox.parametrize("clean", [False, True])
@nox.parametrize("update", [False, True])
@nox.parametrize("compress", [False, True])
def docs(session, compress, update, clean):
    """
    Build Salt's Documentation
    """
    session.notify(f"docs-html-{session.python}(compress={compress})")
    session.notify(
        find_session_runner(
            session,
            "docs-man",
            session.python,
            compress=compress,
            update=update,
            clean=clean,
        )
    )


@nox.session(name="docs-html", python="3")
@nox.parametrize("clean", [False, True])
@nox.parametrize("compress", [False, True])
def docs_html(session, compress, clean):
    """
    Build Salt's HTML Documentation
    """
    if _upgrade_pip_setuptools_and_wheel(session):
        linux_requirements_file = os.path.join(
            "requirements", "static", "ci", _get_pydir(session), "linux.txt"
        )
        base_requirements_file = os.path.join("requirements", "base.txt")
        zeromq_requirements_file = os.path.join("requirements", "zeromq.txt")
        docs_requirements_file = os.path.join(
            "requirements", "static", "ci", _get_pydir(session), "docs.txt"
        )
        install_command = [
            "--progress-bar=off",
            "--constraint",
            linux_requirements_file,
            "-r",
            base_requirements_file,
            "-r",
            zeromq_requirements_file,
            "-r",
            docs_requirements_file,
        ]
        session.install(*install_command, silent=PIP_INSTALL_SILENT)
    os.chdir("doc/")
    if clean:
        session.run("make", "clean", external=True)
    session.run("make", "html", "SPHINXOPTS=-W", external=True)
    if compress:
        session.run("tar", "-cJvf", "html-archive.tar.xz", "_build/html", external=True)
    os.chdir("..")


@nox.session(name="docs-man", python="3")
@nox.parametrize("clean", [False, True])
@nox.parametrize("update", [False, True])
@nox.parametrize("compress", [False, True])
def docs_man(session, compress, update, clean):
    """
    Build Salt's Manpages Documentation
    """
    if _upgrade_pip_setuptools_and_wheel(session):
        linux_requirements_file = os.path.join(
            "requirements", "static", "ci", _get_pydir(session), "linux.txt"
        )
        base_requirements_file = os.path.join("requirements", "base.txt")
        zeromq_requirements_file = os.path.join("requirements", "zeromq.txt")
        docs_requirements_file = os.path.join(
            "requirements", "static", "ci", _get_pydir(session), "docs.txt"
        )
        install_command = [
            "--progress-bar=off",
            "--constraint",
            linux_requirements_file,
            "-r",
            base_requirements_file,
            "-r",
            zeromq_requirements_file,
            "-r",
            docs_requirements_file,
        ]
        session.install(*install_command, silent=PIP_INSTALL_SILENT)
    os.chdir("doc/")
    if clean:
        session.run("make", "clean", external=True)
    session.run("make", "man", "SPHINXOPTS=-W", external=True)
    if update:
        session.run("rm", "-rf", "man/", external=True)
        session.run("cp", "-Rp", "_build/man", "man/", external=True)
    if compress:
        session.run("tar", "-cJvf", "man-archive.tar.xz", "_build/man", external=True)
    os.chdir("..")


@nox.session(name="changelog", python="3")
@nox.parametrize("draft", [False, True])
@nox.parametrize("force", [False, True])
def changelog(session, draft, force):
    """
    Generate salt's changelog
    """
    session_warn(
        session,
        "Please stop using this nox session and start using the 'tools' command shown below.",
    )
    if _upgrade_pip_setuptools_and_wheel(session):
        requirements_file = os.path.join(
            "requirements", "static", "ci", _get_pydir(session), "tools.txt"
        )
        install_command = ["--progress-bar=off", "-r", requirements_file]
        session.install(*install_command, silent=PIP_INSTALL_SILENT)

    cmd = ["tools", "changelog", "update-changelog-md"]
    if draft:
        cmd.append("--draft")
    cmd.append(session.posargs[0])
    session.run(*cmd)


class Recompress:
    """
    Helper class to re-compress a ``.tag.gz`` file to make it reproducible.
    """

    def __init__(self, mtime):
        self.mtime = int(mtime)

    def tar_reset(self, tarinfo):
        """
        Reset user, group, mtime, and mode to create reproducible tar.
        """
        tarinfo.uid = tarinfo.gid = 0
        tarinfo.uname = tarinfo.gname = "root"
        tarinfo.mtime = self.mtime
        if tarinfo.type == tarfile.DIRTYPE:
            tarinfo.mode = 0o755
        else:
            tarinfo.mode = 0o644
        if tarinfo.pax_headers:
            raise ValueError(tarinfo.name, tarinfo.pax_headers)
        return tarinfo

    def recompress(self, targz):
        """
        Re-compress the passed path.
        """
        tempd = pathlib.Path(tempfile.mkdtemp()).resolve()
        d_src = tempd.joinpath("src")
        d_src.mkdir()
        d_tar = tempd.joinpath(targz.stem)
        d_targz = tempd.joinpath(targz.name)
        with tarfile.open(d_tar, "w|") as wfile:
            with tarfile.open(targz, "r:gz") as rfile:
                rfile.extractall(d_src)  # nosec
                extracted_dir = next(pathlib.Path(d_src).iterdir())
                for name in sorted(extracted_dir.rglob("*")):
                    wfile.add(
                        str(name),
                        filter=self.tar_reset,
                        recursive=False,
                        arcname=str(name.relative_to(d_src)),
                    )

        with open(d_tar, "rb") as rfh:
            with gzip.GzipFile(
                fileobj=open(d_targz, "wb"), mode="wb", filename="", mtime=self.mtime
            ) as gz:  # pylint: disable=invalid-name
                while True:
                    chunk = rfh.read(1024)
                    if not chunk:
                        break
                    gz.write(chunk)
        targz.unlink()
        shutil.move(str(d_targz), str(targz))


@nox.session(python="3")
def build(session):
    """
    Build source and binary distributions based off the current commit author date UNIX timestamp.

    The reason being, reproducible packages.

    .. code-block: shell

        git show -s --format=%at HEAD
    """
    shutil.rmtree("dist/", ignore_errors=True)
    if SKIP_REQUIREMENTS_INSTALL is False:
        session.install(
            "--progress-bar=off",
            "-r",
            "requirements/build.txt",
            silent=PIP_INSTALL_SILENT,
        )

    timestamp = session.run(
        "git",
        "show",
        "-s",
        "--format=%at",
        "HEAD",
        silent=True,
        log=False,
        stderr=None,
    ).strip()
    env = {"SOURCE_DATE_EPOCH": str(timestamp)}
    session.run(
        "python",
        "-m",
        "build",
        "--sdist",
        str(REPO_ROOT),
        env=env,
    )
    # Recreate sdist to be reproducible
    recompress = Recompress(timestamp)
    for targz in REPO_ROOT.joinpath("dist").glob("*.tar.gz"):
        session.log("Re-compressing %s...", targz.relative_to(REPO_ROOT))
        recompress.recompress(targz)

    sha256sum = shutil.which("sha256sum")
    if sha256sum:
        packages = [
            str(pkg.relative_to(REPO_ROOT))
            for pkg in REPO_ROOT.joinpath("dist").iterdir()
        ]
        session.run("sha256sum", *packages, external=True)
    session.run("python", "-m", "twine", "check", "dist/*")


@nox.session(
    python=str(ONEDIR_PYTHON_PATH),
    name="ci-test-onedir-pkgs",
    venv_params=["--system-site-packages"],
)
def ci_test_onedir_pkgs(session):
    from nox.virtualenv import VirtualEnv

    session_warn(session, "Replacing VirtualEnv instance...")

    ci_test_onedir_path = REPO_ROOT / ".nox" / "ci-test-onedir"
    session._runner.venv = VirtualEnv(
        str(ci_test_onedir_path.relative_to(REPO_ROOT)),
        interpreter=session._runner.func.python,
        reuse_existing=True,
        venv=session._runner.venv.venv_or_virtualenv == "venv",
        venv_params=session._runner.venv.venv_params,
    )
    os.environ["VIRTUAL_ENV"] = session._runner.venv.location
    session._runner.venv.create()

    if not ONEDIR_ARTIFACT_PATH.exists():
        session.error(
            "The salt onedir artifact, expected to be in '{}', was not found".format(
                ONEDIR_ARTIFACT_PATH.relative_to(REPO_ROOT)
            )
        )

    common_pytest_args = [
        "--color=yes",
        "--sys-stats",
        "--run-destructive",
        f"--output-columns={os.environ.get('OUTPUT_COLUMNS') or 120}",
        "--pkg-system-service",
    ]

    chunks = {
        "install": [],
        "upgrade": [
            "--upgrade",
            "--no-uninstall",
        ],
        "upgrade-classic": [
            "--upgrade",
            "--no-uninstall",
        ],
        "downgrade": [
            "--downgrade",
            "--no-uninstall",
        ],
        "downgrade-classic": [
            "--downgrade",
            "--no-uninstall",
        ],
        "download-pkgs": [
            "--download-pkgs",
        ],
    }

    if not session.posargs or session.posargs[0] not in chunks:
        chunk = "install"
        session.log("Choosing default 'install' test type")
    else:
        chunk = session.posargs.pop(0)

    cmd_args = chunks[chunk]
    for arg in session.posargs:
        if arg.startswith("tests/pytests/pkg/"):
            # The user is passing test paths
            cmd_args.pop()
            break

    if IS_LINUX:
        # Fetch the toolchain
        session_run_always(session, "python3", "-m", "relenv", "toolchain", "fetch")

    # Install requirements
    if _upgrade_pip_setuptools_and_wheel(session):
        _install_requirements(session, "pyzmq")
    env = {
        "ONEDIR_TESTRUN": "1",
        "PKG_TEST_TYPE": chunk,
    }

    if chunk in ("upgrade-classic", "downgrade-classic"):
        cmd_args.append("--classic")

    pytest_args = (
        common_pytest_args[:]
        + cmd_args[:]
        + [
            f"--junitxml=artifacts/xml-unittests-output/test-results-{chunk}.xml",
            f"--log-file=artifacts/logs/runtests-{chunk}.log",
        ]
        + session.posargs
    )
    append_tests_path = True
    test_paths = (
        "tests/pytests/pkg/",
        str(REPO_ROOT / "tests" / "pytests" / "pkg"),
    )
    for arg in session.posargs:
        if arg.startswith(test_paths):
            append_tests_path = False
            break
    if append_tests_path:
        pytest_args.append("tests/pytests/pkg/")
    try:
        _pytest(session, coverage=False, cmd_args=pytest_args, env=env)
    except CommandFailed:
        if os.environ.get("RERUN_FAILURES", "0") == "0":
            # Don't rerun on failures
            return

        # Don't print the system information, not the test selection on reruns
        global PRINT_TEST_SELECTION
        global PRINT_SYSTEM_INFO
        PRINT_TEST_SELECTION = False
        PRINT_SYSTEM_INFO = False

        pytest_args = (
            common_pytest_args[:]
            + cmd_args[:]
            + [
                f"--junitxml=artifacts/xml-unittests-output/test-results-{chunk}-rerun.xml",
                f"--log-file=artifacts/logs/runtests-{chunk}-rerun.log",
                "--lf",
            ]
            + session.posargs
        )
        if append_tests_path:
            pytest_args.append("tests/pytests/pkg/")
        _pytest(
            session,
            coverage=False,
            cmd_args=pytest_args,
            env=env,
            on_rerun=True,
        )

    if chunk not in ("install", "download-pkgs"):
        cmd_args = chunks["install"]
        pytest_args = (
            common_pytest_args[:]
            + cmd_args[:]
            + [
                "--no-install",
                "--junitxml=artifacts/xml-unittests-output/test-results-install.xml",
                "--log-file=artifacts/logs/runtests-install.log",
            ]
            + session.posargs
        )
        if "downgrade" in chunk:
            pytest_args.append("--use-prev-version")
        if chunk in ("upgrade-classic", "downgrade-classic"):
            pytest_args.append("--classic")
        if append_tests_path:
            pytest_args.append("tests/pytests/pkg/")
        try:
            _pytest(session, coverage=False, cmd_args=pytest_args, env=env)
        except CommandFailed:
            if os.environ.get("RERUN_FAILURES", "0") == "0":
                # Don't rerun on failures
                return
            cmd_args = chunks["install"]
            pytest_args = (
                common_pytest_args[:]
                + cmd_args[:]
                + [
                    "--no-install",
                    "--junitxml=artifacts/xml-unittests-output/test-results-install-rerun.xml",
                    "--log-file=artifacts/logs/runtests-install-rerun.log",
                    "--lf",
                ]
                + session.posargs
            )
            if "downgrade" in chunk:
                pytest_args.append("--use-prev-version")
            if chunk in ("upgrade-classic", "downgrade-classic"):
                pytest_args.append("--classic")
            if append_tests_path:
                pytest_args.append("tests/pytests/pkg/")
            _pytest(
                session,
                coverage=False,
                cmd_args=pytest_args,
                env=env,
                on_rerun=True,
            )
    sys.exit(0)
