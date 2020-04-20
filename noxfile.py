# -*- coding: utf-8 -*-
"""
noxfile
~~~~~~~

Nox configuration script
"""
# pylint: disable=resource-leakage

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import datetime
import glob
import json
import os
import pprint
import shutil
import sys
import tempfile

# fmt: off
if __name__ == '__main__':
    sys.stderr.write('Do not execute this file directly. Use nox instead, it will know how to handle this file\n')
    sys.stderr.flush()
    exit(1)
# fmt: on

# Import 3rd-party libs
import nox  # isort:skip
from nox.command import CommandFailed  # isort:skip


IS_PY3 = sys.version_info > (2,)

# Be verbose when runing under a CI context
PIP_INSTALL_SILENT = (
    os.environ.get("JENKINS_URL") or os.environ.get("CI") or os.environ.get("DRONE")
) is None


# Global Path Definitions
REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
SITECUSTOMIZE_DIR = os.path.join(REPO_ROOT, "tests", "support", "coverage")
IS_DARWIN = sys.platform.lower().startswith("darwin")
IS_WINDOWS = sys.platform.lower().startswith("win")
# Python versions to run against
_PYTHON_VERSIONS = ("2", "2.7", "3", "3.4", "3.5", "3.6", "3.7")

# Nox options
#  Reuse existing virtualenvs
nox.options.reuse_existing_virtualenvs = True
#  Don't fail on missing interpreters
nox.options.error_on_missing_interpreters = False

# Change current directory to REPO_ROOT
os.chdir(REPO_ROOT)

RUNTESTS_LOGFILE = os.path.join(
    "artifacts",
    "logs",
    "runtests-{}.log".format(datetime.datetime.now().strftime("%Y%m%d%H%M%S.%f")),
)

# Prevent Python from writing bytecode
os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")


def _create_ci_directories():
    for dirname in ("logs", "coverage", "xml-unittests-output"):
        path = os.path.join("artifacts", dirname)
        if not os.path.exists(path):
            os.makedirs(path)


def _get_session_python_version_info(session):
    try:
        version_info = session._runner._real_python_version_info
    except AttributeError:
        old_install_only_value = session._runner.global_config.install_only
        try:
            # Force install only to be false for the following chunk of code
            # For additional information as to why see:
            #   https://github.com/theacodes/nox/pull/181
            session._runner.global_config.install_only = False
            session_py_version = session.run(
                "python",
                "-c"
                'import sys; sys.stdout.write("{}.{}.{}".format(*sys.version_info))',
                silent=True,
                log=False,
            )
            version_info = tuple(
                int(part) for part in session_py_version.split(".") if part.isdigit()
            )
            session._runner._real_python_version_info = version_info
        finally:
            session._runner.global_config.install_only = old_install_only_value
    return version_info


def _get_session_python_site_packages_dir(session):
    try:
        site_packages_dir = session._runner._site_packages_dir
    except AttributeError:
        old_install_only_value = session._runner.global_config.install_only
        try:
            # Force install only to be false for the following chunk of code
            # For additional information as to why see:
            #   https://github.com/theacodes/nox/pull/181
            session._runner.global_config.install_only = False
            site_packages_dir = session.run(
                "python",
                "-c"
                "import sys; from distutils.sysconfig import get_python_lib; sys.stdout.write(get_python_lib())",
                silent=True,
                log=False,
            )
            session._runner._site_packages_dir = site_packages_dir
        finally:
            session._runner.global_config.install_only = old_install_only_value
    return site_packages_dir


def _get_pydir(session):
    version_info = _get_session_python_version_info(session)
    if version_info < (2, 7):
        session.error("Only Python >= 2.7 is supported")
    return "py{}.{}".format(*version_info)


def _get_distro_info(session):
    try:
        distro = session._runner._distro
    except AttributeError:
        # The distro package doesn't output anything for Windows
        old_install_only_value = session._runner.global_config.install_only
        try:
            # Force install only to be false for the following chunk of code
            # For additional information as to why see:
            #   https://github.com/theacodes/nox/pull/181
            session._runner.global_config.install_only = False
            session.install("--progress-bar=off", "distro", silent=PIP_INSTALL_SILENT)
            output = session.run("distro", "-j", silent=True)
            distro = json.loads(output.strip())
            session.log("Distro information:\n%s", pprint.pformat(distro))
            session._runner._distro = distro
        finally:
            session._runner.global_config.install_only = old_install_only_value
    return distro


def _install_system_packages(session):
    """
    Because some python packages are provided by the distribution and cannot
    be pip installed, and because we don't want the whole system python packages
    on our virtualenvs, we copy the required system python packages into
    the virtualenv
    """
    system_python_packages = {
        "__debian_based_distros__": ["/usr/lib/python{py_version}/dist-packages/*apt*"]
    }

    distro = _get_distro_info(session)
    if not distro["id"].startswith(("debian", "ubuntu")):
        # This only applies to debian based distributions
        return

    system_python_packages["{id}-{version}".format(**distro)] = system_python_packages[
        "{id}-{version_parts[major]}".format(**distro)
    ] = system_python_packages["__debian_based_distros__"][:]

    distro_keys = [
        "{id}".format(**distro),
        "{id}-{version}".format(**distro),
        "{id}-{version_parts[major]}".format(**distro),
    ]
    version_info = _get_session_python_version_info(session)
    py_version_keys = ["{}".format(*version_info), "{}.{}".format(*version_info)]
    session_site_packages_dir = _get_session_python_site_packages_dir(session)
    for distro_key in distro_keys:
        if distro_key not in system_python_packages:
            continue
        patterns = system_python_packages[distro_key]
        for pattern in patterns:
            for py_version in py_version_keys:
                matches = set(glob.glob(pattern.format(py_version=py_version)))
                if not matches:
                    continue
                for match in matches:
                    src = os.path.realpath(match)
                    dst = os.path.join(
                        session_site_packages_dir, os.path.basename(match)
                    )
                    if os.path.exists(dst):
                        session.log(
                            "Not overwritting already existing %s with %s", dst, src
                        )
                        continue
                    session.log("Copying %s into %s", src, dst)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copyfile(src, dst)


def _get_distro_pip_constraints(session, transport):
    # Install requirements
    distro_constraints = []

    if transport == "tcp":
        # The TCP requirements are the exact same requirements as the ZeroMQ ones
        transport = "zeromq"

    pydir = _get_pydir(session)

    if IS_WINDOWS:
        _distro_constraints = os.path.join(
            "requirements", "static", pydir, "{}-windows.txt".format(transport)
        )
        if os.path.exists(_distro_constraints):
            distro_constraints.append(_distro_constraints)
        _distro_constraints = os.path.join(
            "requirements", "static", pydir, "windows.txt"
        )
        if os.path.exists(_distro_constraints):
            distro_constraints.append(_distro_constraints)
        _distro_constraints = os.path.join(
            "requirements", "static", pydir, "windows-crypto.txt"
        )
        if os.path.exists(_distro_constraints):
            distro_constraints.append(_distro_constraints)
    elif IS_DARWIN:
        _distro_constraints = os.path.join(
            "requirements", "static", pydir, "{}-darwin.txt".format(transport)
        )
        if os.path.exists(_distro_constraints):
            distro_constraints.append(_distro_constraints)
        _distro_constraints = os.path.join(
            "requirements", "static", pydir, "darwin.txt"
        )
        if os.path.exists(_distro_constraints):
            distro_constraints.append(_distro_constraints)
        _distro_constraints = os.path.join(
            "requirements", "static", pydir, "darwin-crypto.txt"
        )
        if os.path.exists(_distro_constraints):
            distro_constraints.append(_distro_constraints)
    else:
        _install_system_packages(session)
        distro = _get_distro_info(session)
        distro_keys = [
            "linux",
            "{id}".format(**distro),
            "{id}-{version}".format(**distro),
            "{id}-{version_parts[major]}".format(**distro),
        ]
        for distro_key in distro_keys:
            _distro_constraints = os.path.join(
                "requirements", "static", pydir, "{}.txt".format(distro_key)
            )
            if os.path.exists(_distro_constraints):
                distro_constraints.append(_distro_constraints)
            _distro_constraints = os.path.join(
                "requirements", "static", pydir, "{}-crypto.txt".format(distro_key)
            )
            if os.path.exists(_distro_constraints):
                distro_constraints.append(_distro_constraints)
            _distro_constraints = os.path.join(
                "requirements",
                "static",
                pydir,
                "{}-{}.txt".format(transport, distro_key),
            )
            if os.path.exists(_distro_constraints):
                distro_constraints.append(_distro_constraints)
                distro_constraints.append(_distro_constraints)
            _distro_constraints = os.path.join(
                "requirements",
                "static",
                pydir,
                "{}-{}-crypto.txt".format(transport, distro_key),
            )
            if os.path.exists(_distro_constraints):
                distro_constraints.append(_distro_constraints)
    return distro_constraints


def _install_requirements(session, transport, *extra_requirements):
    # Install requirements
    distro_constraints = _get_distro_pip_constraints(session, transport)

    _requirements_files = [
        os.path.join("requirements", "base.txt"),
        os.path.join("requirements", "zeromq.txt"),
        os.path.join("requirements", "pytest.txt"),
    ]
    if sys.platform.startswith("linux"):
        requirements_files = [os.path.join("requirements", "static", "linux.in")]
    elif sys.platform.startswith("win"):
        requirements_files = [
            os.path.join("pkg", "windows", "req.txt"),
            os.path.join("requirements", "static", "windows.in"),
        ]
    elif sys.platform.startswith("darwin"):
        requirements_files = [
            os.path.join("pkg", "osx", "req.txt"),
            os.path.join("pkg", "osx", "req_ext.txt"),
            os.path.join("pkg", "osx", "req_pyobjc.txt"),
            os.path.join("requirements", "static", "darwin.in"),
        ]

    while True:
        if not requirements_files:
            break
        requirements_file = requirements_files.pop(0)

        if requirements_file not in _requirements_files:
            _requirements_files.append(requirements_file)

        session.log("Processing {}".format(requirements_file))
        with open(requirements_file) as rfh:  # pylint: disable=resource-leakage
            for line in rfh:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("-r"):
                    reqfile = os.path.join(
                        os.path.dirname(requirements_file), line.strip().split()[-1]
                    )
                    if reqfile in _requirements_files:
                        continue
                    _requirements_files.append(reqfile)
                    continue

    for requirements_file in _requirements_files:
        install_command = ["--progress-bar=off", "-r", requirements_file]
        for distro_constraint in distro_constraints:
            install_command.extend(["--constraint", distro_constraint])
        session.install(*install_command, silent=PIP_INSTALL_SILENT)

    if extra_requirements:
        install_command = [
            "--progress-bar=off",
        ]
        for distro_constraint in distro_constraints:
            install_command.extend(["--constraint", distro_constraint])
        install_command += list(extra_requirements)
        session.install(*install_command, silent=PIP_INSTALL_SILENT)


def _run_with_coverage(session, *test_cmd):
    session.install("--progress-bar=off", "coverage==5.0.1", silent=PIP_INSTALL_SILENT)
    session.run("coverage", "erase")
    python_path_env_var = os.environ.get("PYTHONPATH") or None
    if python_path_env_var is None:
        python_path_env_var = SITECUSTOMIZE_DIR
    else:
        python_path_entries = python_path_env_var.split(os.pathsep)
        if SITECUSTOMIZE_DIR in python_path_entries:
            python_path_entries.remove(SITECUSTOMIZE_DIR)
        python_path_entries.insert(0, SITECUSTOMIZE_DIR)
        python_path_env_var = os.pathsep.join(python_path_entries)

    env = {
        # The updated python path so that sitecustomize is importable
        "PYTHONPATH": python_path_env_var,
        # The full path to the .coverage data file. Makes sure we always write
        # them to the same directory
        "COVERAGE_FILE": os.path.abspath(os.path.join(REPO_ROOT, ".coverage")),
        # Instruct sub processes to also run under coverage
        "COVERAGE_PROCESS_START": os.path.join(REPO_ROOT, ".coveragerc"),
    }
    if IS_DARWIN:
        # Don't nuke our multiprocessing efforts objc!
        # https://stackoverflow.com/questions/50168647/multiprocessing-causes-python-to-crash-and-gives-an-error-may-have-been-in-progr
        env["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

    try:
        session.run(*test_cmd, env=env)
    finally:
        # Always combine and generate the XML coverage report
        try:
            session.run("coverage", "combine")
        except CommandFailed:
            # Sometimes some of the coverage files are corrupt which would trigger a CommandFailed
            # exception
            pass
        # Generate report for salt code coverage
        session.run(
            "coverage",
            "xml",
            "-o",
            os.path.join("artifacts", "coverage", "salt.xml"),
            "--omit=tests/*",
            "--include=salt/*",
        )
        # Generate report for tests code coverage
        session.run(
            "coverage",
            "xml",
            "-o",
            os.path.join("artifacts", "coverage", "tests.xml"),
            "--omit=salt/*",
            "--include=tests/*",
        )


def _runtests(session, coverage, cmd_args):
    # Create required artifacts directories
    _create_ci_directories()
    try:
        if coverage is True:
            _run_with_coverage(
                session,
                "coverage",
                "run",
                os.path.join("tests", "runtests.py"),
                *cmd_args
            )
        else:
            cmd_args = ["python", os.path.join("tests", "runtests.py")] + list(cmd_args)
            env = None
            if IS_DARWIN:
                # Don't nuke our multiprocessing efforts objc!
                # https://stackoverflow.com/questions/50168647/multiprocessing-causes-python-to-crash-and-gives-an-error-may-have-been-in-progr
                env = {"OBJC_DISABLE_INITIALIZE_FORK_SAFETY": "YES"}
            session.run(*cmd_args, env=env)
    except CommandFailed:  # pylint: disable=try-except-raise
        # Disabling re-running failed tests for the time being
        raise

        # pylint: disable=unreachable
        names_file_path = os.path.join("artifacts", "failed-tests.txt")
        session.log("Re-running failed tests if possible")
        session.install(
            "--progress-bar=off", "xunitparser==1.3.3", silent=PIP_INSTALL_SILENT
        )
        session.run(
            "python",
            os.path.join(
                "tests", "support", "generate-names-file-from-failed-test-reports.py"
            ),
            names_file_path,
        )
        if not os.path.exists(names_file_path):
            session.log(
                "Failed tests file(%s) was not found. Not rerunning failed tests.",
                names_file_path,
            )
            # raise the original exception
            raise
        with open(names_file_path) as rfh:
            contents = rfh.read().strip()
            if not contents:
                session.log(
                    "The failed tests file(%s) is empty. Not rerunning failed tests.",
                    names_file_path,
                )
                # raise the original exception
                raise
            failed_tests_count = len(contents.splitlines())
            if failed_tests_count > 500:
                # 500 test failures?! Something else must have gone wrong, don't even bother
                session.error(
                    "Total failed tests({}) > 500. No point on re-running the failed tests".format(
                        failed_tests_count
                    )
                )

        for idx, flag in enumerate(cmd_args[:]):
            if "--names-file=" in flag:
                cmd_args.pop(idx)
                break
            elif flag == "--names-file":
                cmd_args.pop(idx)  # pop --names-file
                cmd_args.pop(idx)  # pop the actual names file
                break
        cmd_args.append("--names-file={}".format(names_file_path))
        if coverage is True:
            _run_with_coverage(
                session, "coverage", "run", "-m", "tests.runtests", *cmd_args
            )
        else:
            session.run("python", os.path.join("tests", "runtests.py"), *cmd_args)
        # pylint: enable=unreachable


@nox.session(python=_PYTHON_VERSIONS, name="runtests-parametrized")
@nox.parametrize("coverage", [False, True])
@nox.parametrize("transport", ["zeromq", "tcp"])
@nox.parametrize("crypto", [None, "m2crypto", "pycryptodomex"])
def runtests_parametrized(session, coverage, transport, crypto):
    # Install requirements
    _install_requirements(session, transport, "unittest-xml-reporting==2.5.2")

    if crypto:
        if crypto == "m2crypto":
            session.run(
                "pip",
                "uninstall",
                "-y",
                "pycrypto",
                "pycryptodome",
                "pycryptodomex",
                silent=True,
            )
        else:
            session.run("pip", "uninstall", "-y", "m2crypto", silent=True)
        distro_constraints = _get_distro_pip_constraints(session, transport)
        install_command = [
            "--progress-bar=off",
        ]
        for distro_constraint in distro_constraints:
            install_command.extend(["--constraint", distro_constraint])
        install_command.append(crypto)
        session.install(*install_command, silent=PIP_INSTALL_SILENT)

    cmd_args = [
        "--tests-logfile={}".format(RUNTESTS_LOGFILE),
        "--transport={}".format(transport),
    ] + session.posargs
    _runtests(session, coverage, cmd_args)


@nox.session(python=_PYTHON_VERSIONS)
@nox.parametrize("coverage", [False, True])
def runtests(session, coverage):
    """
    runtests.py session with zeromq transport and default crypto
    """
    session.notify(
        "runtests-parametrized-{}(coverage={}, crypto=None, transport='zeromq')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-tcp")
@nox.parametrize("coverage", [False, True])
def runtests_tcp(session, coverage):
    """
    runtests.py session with TCP transport and default crypto
    """
    session.notify(
        "runtests-parametrized-{}(coverage={}, crypto=None, transport='tcp')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-zeromq")
@nox.parametrize("coverage", [False, True])
def runtests_zeromq(session, coverage):
    """
    runtests.py session with zeromq transport and default crypto
    """
    session.notify(
        "runtests-parametrized-{}(coverage={}, crypto=None, transport='zeromq')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-m2crypto")
@nox.parametrize("coverage", [False, True])
def runtests_m2crypto(session, coverage):
    """
    runtests.py session with zeromq transport and m2crypto
    """
    session.notify(
        "runtests-parametrized-{}(coverage={}, crypto='m2crypto', transport='zeromq')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-tcp-m2crypto")
@nox.parametrize("coverage", [False, True])
def runtests_tcp_m2crypto(session, coverage):
    """
    runtests.py session with TCP transport and m2crypto
    """
    session.notify(
        "runtests-parametrized-{}(coverage={}, crypto='m2crypto', transport='tcp')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-zeromq-m2crypto")
@nox.parametrize("coverage", [False, True])
def runtests_zeromq_m2crypto(session, coverage):
    """
    runtests.py session with zeromq transport and m2crypto
    """
    session.notify(
        "runtests-parametrized-{}(coverage={}, crypto='m2crypto', transport='zeromq')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-pycryptodomex")
@nox.parametrize("coverage", [False, True])
def runtests_pycryptodomex(session, coverage):
    """
    runtests.py session with zeromq transport and pycryptodomex
    """
    session.notify(
        "runtests-parametrized-{}(coverage={}, crypto='pycryptodomex', transport='zeromq')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-tcp-pycryptodomex")
@nox.parametrize("coverage", [False, True])
def runtests_tcp_pycryptodomex(session, coverage):
    """
    runtests.py session with TCP transport and pycryptodomex
    """
    session.notify(
        "runtests-parametrized-{}(coverage={}, crypto='pycryptodomex', transport='tcp')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-zeromq-pycryptodomex")
@nox.parametrize("coverage", [False, True])
def runtests_zeromq_pycryptodomex(session, coverage):
    """
    runtests.py session with zeromq transport and pycryptodomex
    """
    session.notify(
        "runtests-parametrized-{}(coverage={}, crypto='pycryptodomex', transport='zeromq')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-cloud")
@nox.parametrize("coverage", [False, True])
def runtests_cloud(session, coverage):
    # Install requirements
    _install_requirements(session, "zeromq", "unittest-xml-reporting==2.2.1")

    pydir = _get_pydir(session)
    cloud_requirements = os.path.join("requirements", "static", pydir, "cloud.txt")

    session.install(
        "--progress-bar=off", "-r", cloud_requirements, silent=PIP_INSTALL_SILENT
    )

    cmd_args = [
        "--tests-logfile={}".format(RUNTESTS_LOGFILE),
        "--cloud-provider-tests",
    ] + session.posargs
    _runtests(session, coverage, cmd_args)


@nox.session(python=_PYTHON_VERSIONS, name="runtests-tornado")
@nox.parametrize("coverage", [False, True])
def runtests_tornado(session, coverage):
    # Install requirements
    _install_requirements(session, "zeromq", "unittest-xml-reporting==2.2.1")
    session.install("--progress-bar=off", "tornado==5.0.2", silent=PIP_INSTALL_SILENT)
    session.install("--progress-bar=off", "pyzmq==17.0.0", silent=PIP_INSTALL_SILENT)

    cmd_args = ["--tests-logfile={}".format(RUNTESTS_LOGFILE)] + session.posargs
    _runtests(session, coverage, cmd_args)


@nox.session(python=_PYTHON_VERSIONS, name="pytest-parametrized")
@nox.parametrize("coverage", [False, True])
@nox.parametrize("transport", ["zeromq", "tcp"])
@nox.parametrize("crypto", [None, "m2crypto", "pycryptodomex"])
def pytest_parametrized(session, coverage, transport, crypto):
    # Install requirements
    _install_requirements(session, transport)

    if crypto:
        if crypto == "m2crypto":
            session.run(
                "pip",
                "uninstall",
                "-y",
                "pycrypto",
                "pycryptodome",
                "pycryptodomex",
                silent=True,
            )
        else:
            session.run("pip", "uninstall", "-y", "m2crypto", silent=True)
        distro_constraints = _get_distro_pip_constraints(session, transport)
        install_command = [
            "--progress-bar=off",
        ]
        for distro_constraint in distro_constraints:
            install_command.extend(["--constraint", distro_constraint])
        install_command.append(crypto)
        session.install(*install_command, silent=PIP_INSTALL_SILENT)

    cmd_args = [
        "--rootdir",
        REPO_ROOT,
        "--log-file={}".format(RUNTESTS_LOGFILE),
        "--log-file-level=debug",
        "--no-print-logs",
        "-ra",
        "-s",
        "--transport={}".format(transport),
    ] + session.posargs
    _pytest(session, coverage, cmd_args)


@nox.session(python=_PYTHON_VERSIONS)
@nox.parametrize("coverage", [False, True])
def pytest(session, coverage):
    """
    pytest session with zeromq transport and default crypto
    """
    session.notify(
        "pytest-parametrized-{}(coverage={}, crypto=None, transport='zeromq')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-tcp")
@nox.parametrize("coverage", [False, True])
def pytest_tcp(session, coverage):
    """
    pytest session with TCP transport and default crypto
    """
    session.notify(
        "pytest-parametrized-{}(coverage={}, crypto=None, transport='tcp')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-zeromq")
@nox.parametrize("coverage", [False, True])
def pytest_zeromq(session, coverage):
    """
    pytest session with zeromq transport and default crypto
    """
    session.notify(
        "pytest-parametrized-{}(coverage={}, crypto=None, transport='zeromq')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-m2crypto")
@nox.parametrize("coverage", [False, True])
def pytest_m2crypto(session, coverage):
    """
    pytest session with zeromq transport and m2crypto
    """
    session.notify(
        "pytest-parametrized-{}(coverage={}, crypto='m2crypto', transport='zeromq')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-tcp-m2crypto")
@nox.parametrize("coverage", [False, True])
def pytest_tcp_m2crypto(session, coverage):
    """
    pytest session with TCP transport and m2crypto
    """
    session.notify(
        "pytest-parametrized-{}(coverage={}, crypto='m2crypto', transport='tcp')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-zeromq-m2crypto")
@nox.parametrize("coverage", [False, True])
def pytest_zeromq_m2crypto(session, coverage):
    """
    pytest session with zeromq transport and m2crypto
    """
    session.notify(
        "pytest-parametrized-{}(coverage={}, crypto='m2crypto', transport='zeromq')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-pycryptodomex")
@nox.parametrize("coverage", [False, True])
def pytest_pycryptodomex(session, coverage):
    """
    pytest session with zeromq transport and pycryptodomex
    """
    session.notify(
        "pytest-parametrized-{}(coverage={}, crypto='pycryptodomex', transport='zeromq')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-tcp-pycryptodomex")
@nox.parametrize("coverage", [False, True])
def pytest_tcp_pycryptodomex(session, coverage):
    """
    pytest session with TCP transport and pycryptodomex
    """
    session.notify(
        "pytest-parametrized-{}(coverage={}, crypto='pycryptodomex', transport='tcp')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-zeromq-pycryptodomex")
@nox.parametrize("coverage", [False, True])
def pytest_zeromq_pycryptodomex(session, coverage):
    """
    pytest session with zeromq transport and pycryptodomex
    """
    session.notify(
        "pytest-parametrized-{}(coverage={}, crypto='pycryptodomex', transport='zeromq')".format(
            session.python, coverage
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-cloud")
@nox.parametrize("coverage", [False, True])
def pytest_cloud(session, coverage):
    # Install requirements
    _install_requirements(session, "zeromq")
    pydir = _get_pydir(session)
    cloud_requirements = os.path.join("requirements", "static", pydir, "cloud.txt")

    session.install(
        "--progress-bar=off", "-r", cloud_requirements, silent=PIP_INSTALL_SILENT
    )

    cmd_args = [
        "--rootdir",
        REPO_ROOT,
        "--log-file={}".format(RUNTESTS_LOGFILE),
        "--log-file-level=debug",
        "--no-print-logs",
        "-ra",
        "-s",
        os.path.join("tests", "integration", "cloud", "providers"),
    ] + session.posargs
    _pytest(session, coverage, cmd_args)


@nox.session(python=_PYTHON_VERSIONS, name="pytest-tornado")
@nox.parametrize("coverage", [False, True])
def pytest_tornado(session, coverage):
    # Install requirements
    _install_requirements(session, "zeromq")
    session.install("--progress-bar=off", "tornado==5.0.2", silent=PIP_INSTALL_SILENT)
    session.install("--progress-bar=off", "pyzmq==17.0.0", silent=PIP_INSTALL_SILENT)

    cmd_args = [
        "--rootdir",
        REPO_ROOT,
        "--log-file={}".format(RUNTESTS_LOGFILE),
        "--log-file-level=debug",
        "--no-print-logs",
        "-ra",
        "-s",
    ] + session.posargs
    _pytest(session, coverage, cmd_args)


def _pytest(session, coverage, cmd_args):
    # Create required artifacts directories
    _create_ci_directories()

    env = None
    if IS_DARWIN:
        # Don't nuke our multiprocessing efforts objc!
        # https://stackoverflow.com/questions/50168647/multiprocessing-causes-python-to-crash-and-gives-an-error-may-have-been-in-progr
        env = {"OBJC_DISABLE_INITIALIZE_FORK_SAFETY": "YES"}

    try:
        if coverage is True:
            _run_with_coverage(session, "coverage", "run", "-m", "py.test", *cmd_args)
        else:
            session.run("py.test", *cmd_args, env=env)
    except CommandFailed:  # pylint: disable=try-except-raise
        # Not rerunning failed tests for now
        raise

        # pylint: disable=unreachable
        # Re-run failed tests
        session.log("Re-running failed tests")

        for idx, parg in enumerate(cmd_args):
            if parg.startswith("--junitxml="):
                cmd_args[idx] = parg.replace(".xml", "-rerun-failed.xml")
        cmd_args.append("--lf")
        if coverage is True:
            _run_with_coverage(session, "coverage", "run", "-m", "py.test", *cmd_args)
        else:
            session.run("py.test", *cmd_args, env=env)
        # pylint: enable=unreachable


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


def _lint(session, rcfile, flags, paths, tee_output=True):
    _install_requirements(session, "zeromq")
    requirements_file = "requirements/static/lint.in"
    distro_constraints = ["requirements/static/{}/lint.txt".format(_get_pydir(session))]
    install_command = ["--progress-bar=off", "-r", requirements_file]
    for distro_constraint in distro_constraints:
        install_command.extend(["--constraint", distro_constraint])
    session.install(*install_command, silent=PIP_INSTALL_SILENT)

    if tee_output:
        session.run("pylint", "--version")
        pylint_report_path = os.environ.get("PYLINT_REPORT")

    cmd_args = ["pylint", "--rcfile={}".format(rcfile)] + list(flags) + list(paths)

    cmd_kwargs = {"env": {"PYTHONUNBUFFERED": "1"}}

    if tee_output:
        stdout = tempfile.TemporaryFile(mode="w+b")
        cmd_kwargs["stdout"] = Tee(stdout, sys.__stdout__)

    lint_failed = False
    try:
        session.run(*cmd_args, **cmd_kwargs)
    except CommandFailed:
        lint_failed = True
        raise
    finally:
        if tee_output:
            stdout.seek(0)
            contents = stdout.read()
            if contents:
                if IS_PY3:
                    contents = contents.decode("utf-8")
                else:
                    contents = contents.encode("utf-8")
                sys.stdout.write(contents)
                sys.stdout.flush()
                if pylint_report_path:
                    # Write report
                    with open(pylint_report_path, "w") as wfh:
                        wfh.write(contents)
                    session.log("Report file written to %r", pylint_report_path)
            stdout.close()


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
    try:
        session._runner.venv = VirtualEnv(  # pylint: disable=unexpected-keyword-arg
            os.environ["VIRTUAL_ENV"],
            interpreter=session._runner.func.python,
            reuse_existing=True,
            venv=True,
        )
    except TypeError:
        # This is still nox-py2
        session._runner.venv = VirtualEnv(
            os.environ["VIRTUAL_ENV"],
            interpreter=session._runner.func.python,
            reuse_existing=True,
        )
    _lint(session, rcfile, flags, paths, tee_output=False)


@nox.session(python="3")
def lint(session):
    """
    Run PyLint against Salt and it's test suite. Set PYLINT_REPORT to a path to capture output.
    """
    session.notify("lint-salt-{}".format(session.python))
    session.notify("lint-tests-{}".format(session.python))


@nox.session(python="3", name="lint-salt")
def lint_salt(session):
    """
    Run PyLint against Salt. Set PYLINT_REPORT to a path to capture output.
    """
    flags = ["--disable=I"]
    if session.posargs:
        paths = session.posargs
    else:
        paths = ["setup.py", "noxfile.py", "salt/"]
    _lint(session, ".pylintrc", flags, paths)


@nox.session(python="3", name="lint-tests")
def lint_tests(session):
    """
    Run PyLint against Salt and it's test suite. Set PYLINT_REPORT to a path to capture output.
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
    Run PyLint against Salt. Set PYLINT_REPORT to a path to capture output.
    """
    flags = ["--disable=I"]
    if session.posargs:
        paths = session.posargs
    else:
        paths = ["setup.py", "noxfile.py", "salt/"]
    _lint_pre_commit(session, ".pylintrc", flags, paths)


@nox.session(python=False, name="lint-tests-pre-commit")
def lint_tests_pre_commit(session):
    """
    Run PyLint against Salt and it's test suite. Set PYLINT_REPORT to a path to capture output.
    """
    flags = ["--disable=I"]
    if session.posargs:
        paths = session.posargs
    else:
        paths = ["tests/"]
    _lint_pre_commit(session, ".pylintrc", flags, paths)


@nox.session(python="3")
@nox.parametrize("update", [False, True])
@nox.parametrize("compress", [False, True])
def docs(session, compress, update):
    """
    Build Salt's Documentation
    """
    session.notify("docs-html(compress={})".format(compress))
    session.notify("docs-man(compress={}, update={})".format(compress, update))


@nox.session(name="docs-html", python="3")
@nox.parametrize("compress", [False, True])
def docs_html(session, compress):
    """
    Build Salt's HTML Documentation
    """
    pydir = _get_pydir(session)
    if pydir == "py3.4":
        session.error("Sphinx only runs on Python >= 3.5")
    requirements_file = "requirements/static/docs.in"
    distro_constraints = ["requirements/static/{}/docs.txt".format(_get_pydir(session))]
    install_command = ["--progress-bar=off", "-r", requirements_file]
    for distro_constraint in distro_constraints:
        install_command.extend(["--constraint", distro_constraint])
    session.install(*install_command, silent=PIP_INSTALL_SILENT)
    os.chdir("doc/")
    session.run("make", "clean", external=True)
    session.run("make", "html", "SPHINXOPTS=-W", external=True)
    if compress:
        session.run("tar", "-cJvf", "html-archive.tar.xz", "_build/html", external=True)
    os.chdir("..")


@nox.session(name="docs-man", python="3")
@nox.parametrize("update", [False, True])
@nox.parametrize("compress", [False, True])
def docs_man(session, compress, update):
    """
    Build Salt's Manpages Documentation
    """
    pydir = _get_pydir(session)
    if pydir == "py3.4":
        session.error("Sphinx only runs on Python >= 3.5")
    requirements_file = "requirements/static/docs.in"
    distro_constraints = ["requirements/static/{}/docs.txt".format(_get_pydir(session))]
    install_command = ["--progress-bar=off", "-r", requirements_file]
    for distro_constraint in distro_constraints:
        install_command.extend(["--constraint", distro_constraint])
    session.install(*install_command, silent=PIP_INSTALL_SILENT)
    os.chdir("doc/")
    session.run("make", "clean", external=True)
    session.run("make", "man", "SPHINXOPTS=-W", external=True)
    if update:
        session.run("rm", "-rf", "man/", external=True)
        session.run("cp", "-Rp", "_build/man", "man/", external=True)
    if compress:
        session.run("tar", "-cJvf", "man-archive.tar.xz", "_build/man", external=True)
    os.chdir("..")
