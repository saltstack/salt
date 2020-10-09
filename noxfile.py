"""
noxfile
~~~~~~~

Nox configuration script
"""
# pylint: disable=resource-leakage,3rd-party-module-not-gated


import datetime
import glob
import os
import shutil
import sys
import tempfile

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

IS_PY3 = sys.version_info > (2,)

# Be verbose when runing under a CI context
CI_RUN = (
    os.environ.get("JENKINS_URL")
    or os.environ.get("CI")
    or os.environ.get("DRONE") is not None
)
PIP_INSTALL_SILENT = CI_RUN is False
SKIP_REQUIREMENTS_INSTALL = "SKIP_REQUIREMENTS_INSTALL" in os.environ
EXTRA_REQUIREMENTS_INSTALL = os.environ.get("EXTRA_REQUIREMENTS_INSTALL")

# Global Path Definitions
REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
SITECUSTOMIZE_DIR = os.path.join(REPO_ROOT, "tests", "support", "coverage")
IS_DARWIN = sys.platform.lower().startswith("darwin")
IS_WINDOWS = sys.platform.lower().startswith("win")
IS_FREEBSD = sys.platform.lower().startswith("freebsd")
# Python versions to run against
_PYTHON_VERSIONS = ("3", "3.5", "3.6", "3.7", "3.8", "3.9")

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
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def find_session_runner(session, name, **kwargs):
    for s, _ in session._runner.manifest.list_all_sessions():
        if name not in s.signatures:
            continue
        for signature in s.signatures:
            for key, value in kwargs.items():
                param = "{}={!r}".format(key, value)
                if IS_PY3:
                    # Under Python2 repr unicode string are always "u" prefixed, ie, u'a string'.
                    param = param.replace("u'", "'")
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
    if version_info < (3, 5):
        session.error("Only Python >= 3.5 is supported")
    return "py{}.{}".format(*version_info)


def _install_system_packages(session):
    """
    Because some python packages are provided by the distribution and cannot
    be pip installed, and because we don't want the whole system python packages
    on our virtualenvs, we copy the required system python packages into
    the virtualenv
    """
    version_info = _get_session_python_version_info(session)
    py_version_keys = ["{}".format(*version_info), "{}.{}".format(*version_info)]
    session_site_packages_dir = _get_session_python_site_packages_dir(session)
    session_site_packages_dir = os.path.relpath(session_site_packages_dir, REPO_ROOT)
    for py_version in py_version_keys:
        dist_packages_path = "/usr/lib/python{}/dist-packages".format(py_version)
        if not os.path.isdir(dist_packages_path):
            continue
        for aptpkg in glob.glob(os.path.join(dist_packages_path, "*apt*")):
            src = os.path.realpath(aptpkg)
            dst = os.path.join(session_site_packages_dir, os.path.basename(src))
            if os.path.exists(dst):
                session.log("Not overwritting already existing %s with %s", dst, src)
                continue
            session.log("Copying %s into %s", src, dst)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copyfile(src, dst)


def _get_pip_requirements_file(session, transport, crypto=None):
    pydir = _get_pydir(session)

    if IS_WINDOWS:
        if crypto is None:
            _requirements_file = os.path.join(
                "requirements",
                "static",
                "ci",
                pydir,
                "{}-windows.txt".format(transport),
            )
            if os.path.exists(_requirements_file):
                return _requirements_file
            _requirements_file = os.path.join(
                "requirements", "static", "ci", pydir, "windows.txt"
            )
            if os.path.exists(_requirements_file):
                return _requirements_file
        _requirements_file = os.path.join(
            "requirements", "static", "ci", pydir, "windows-crypto.txt"
        )
        if os.path.exists(_requirements_file):
            return _requirements_file
    elif IS_DARWIN:
        if crypto is None:
            _requirements_file = os.path.join(
                "requirements", "static", "ci", pydir, "{}-darwin.txt".format(transport)
            )
            if os.path.exists(_requirements_file):
                return _requirements_file
            _requirements_file = os.path.join(
                "requirements", "static", "ci", pydir, "darwin.txt"
            )
            if os.path.exists(_requirements_file):
                return _requirements_file
        _requirements_file = os.path.join(
            "requirements", "static", "ci", pydir, "darwin-crypto.txt"
        )
        if os.path.exists(_requirements_file):
            return _requirements_file
    elif IS_FREEBSD:
        if crypto is None:
            _requirements_file = os.path.join(
                "requirements",
                "static",
                "ci",
                pydir,
                "{}-freebsd.txt".format(transport),
            )
            if os.path.exists(_requirements_file):
                return _requirements_file
            _requirements_file = os.path.join(
                "requirements", "static", "ci", pydir, "freebsd.txt"
            )
            if os.path.exists(_requirements_file):
                return _requirements_file
        _requirements_file = os.path.join(
            "requirements", "static", "ci", pydir, "freebsd-crypto.txt"
        )
        if os.path.exists(_requirements_file):
            return _requirements_file
    else:
        _install_system_packages(session)
        if crypto is None:
            _requirements_file = os.path.join(
                "requirements", "static", "ci", pydir, "{}-linux.txt".format(transport)
            )
            if os.path.exists(_requirements_file):
                return _requirements_file
            _requirements_file = os.path.join(
                "requirements", "static", "ci", pydir, "linux.txt"
            )
            if os.path.exists(_requirements_file):
                return _requirements_file
        _requirements_file = os.path.join(
            "requirements", "static", "ci", pydir, "linux-crypto.txt"
        )
        if os.path.exists(_requirements_file):
            return _requirements_file


def _install_requirements(session, transport, *extra_requirements):
    if SKIP_REQUIREMENTS_INSTALL:
        session.log(
            "Skipping Python Requirements because SKIP_REQUIREMENTS_INSTALL was found in the environ"
        )
        return

    # setuptools 50.0.0 is broken
    # https://github.com/pypa/setuptools/issues?q=is%3Aissue+setuptools+50+
    install_command = ["--progress-bar=off", "-U", "setuptools<50.0.0"]
    session.install(*install_command, silent=PIP_INSTALL_SILENT)

    # Install requirements
    requirements_file = _get_pip_requirements_file(session, transport)
    install_command = ["--progress-bar=off", "-r", requirements_file]
    session.install(*install_command, silent=PIP_INSTALL_SILENT)

    if extra_requirements:
        install_command = ["--progress-bar=off"]
        install_command += list(extra_requirements)
        session.install(*install_command, silent=PIP_INSTALL_SILENT)

    if EXTRA_REQUIREMENTS_INSTALL:
        session.log(
            "Installing the following extra requirements because the EXTRA_REQUIREMENTS_INSTALL environment variable "
            "was set: %s",
            EXTRA_REQUIREMENTS_INSTALL,
        )
        # We pass --constraint in this step because in case any of these extra dependencies has a requirement
        # we're already using, we want to maintain the locked version
        install_command = ["--progress-bar=off", "--constraint", requirements_file]
        install_command += EXTRA_REQUIREMENTS_INSTALL.split()
        session.install(*install_command, silent=PIP_INSTALL_SILENT)


def _run_with_coverage(session, *test_cmd, env=None):
    if SKIP_REQUIREMENTS_INSTALL is False:
        session.install(
            "--progress-bar=off", "coverage==5.2", silent=PIP_INSTALL_SILENT
        )
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

    if env is None:
        env = {}

    env.update(
        {
            # The updated python path so that sitecustomize is importable
            "PYTHONPATH": python_path_env_var,
            # The full path to the .coverage data file. Makes sure we always write
            # them to the same directory
            "COVERAGE_FILE": os.path.abspath(os.path.join(REPO_ROOT, ".coverage")),
            # Instruct sub processes to also run under coverage
            "COVERAGE_PROCESS_START": os.path.join(REPO_ROOT, ".coveragerc"),
        }
    )

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
        # Move the coverage DB to artifacts/coverage in order for it to be archived by CI
        shutil.move(".coverage", os.path.join("artifacts", "coverage", ".coverage"))


def _runtests(session, coverage, cmd_args):
    # Create required artifacts directories
    _create_ci_directories()
    env = {}
    if IS_DARWIN:
        # Don't nuke our multiprocessing efforts objc!
        # https://stackoverflow.com/questions/50168647/multiprocessing-causes-python-to-crash-and-gives-an-error-may-have-been-in-progr
        env["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
    try:
        if coverage is True:
            _run_with_coverage(
                session,
                "coverage",
                "run",
                os.path.join("tests", "runtests.py"),
                *cmd_args,
                env=env
            )
        else:
            cmd_args = ["python", os.path.join("tests", "runtests.py")] + list(cmd_args)
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
@nox.parametrize("crypto", [None, "m2crypto", "pycryptodome"])
def runtests_parametrized(session, coverage, transport, crypto):
    """
    DO NOT CALL THIS NOX SESSION DIRECTLY
    """
    # Install requirements
    _install_requirements(session, transport, "unittest-xml-reporting==2.5.2")

    if crypto:
        session.run(
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
            _get_pip_requirements_file(session, transport, crypto=True),
        ]
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
        find_session_runner(
            session,
            "runtests-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto=None,
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-tcp")
@nox.parametrize("coverage", [False, True])
def runtests_tcp(session, coverage):
    """
    runtests.py session with TCP transport and default crypto
    """
    session.notify(
        find_session_runner(
            session,
            "runtests-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto=None,
            transport="tcp",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-zeromq")
@nox.parametrize("coverage", [False, True])
def runtests_zeromq(session, coverage):
    """
    runtests.py session with zeromq transport and default crypto
    """
    session.notify(
        find_session_runner(
            session,
            "runtests-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto=None,
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-m2crypto")
@nox.parametrize("coverage", [False, True])
def runtests_m2crypto(session, coverage):
    """
    runtests.py session with zeromq transport and m2crypto
    """
    session.notify(
        find_session_runner(
            session,
            "runtests-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto="m2crypto",
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-tcp-m2crypto")
@nox.parametrize("coverage", [False, True])
def runtests_tcp_m2crypto(session, coverage):
    """
    runtests.py session with TCP transport and m2crypto
    """
    session.notify(
        find_session_runner(
            session,
            "runtests-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto="m2crypto",
            transport="tco",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-zeromq-m2crypto")
@nox.parametrize("coverage", [False, True])
def runtests_zeromq_m2crypto(session, coverage):
    """
    runtests.py session with zeromq transport and m2crypto
    """
    session.notify(
        find_session_runner(
            session,
            "runtests-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto="m2crypto",
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-pycryptodome")
@nox.parametrize("coverage", [False, True])
def runtests_pycryptodome(session, coverage):
    """
    runtests.py session with zeromq transport and pycryptodome
    """
    session.notify(
        find_session_runner(
            session,
            "runtests-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto="pycryptodome",
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-tcp-pycryptodome")
@nox.parametrize("coverage", [False, True])
def runtests_tcp_pycryptodome(session, coverage):
    """
    runtests.py session with TCP transport and pycryptodome
    """
    session.notify(
        find_session_runner(
            session,
            "runtests-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto="pycryptodome",
            transport="tcp",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-zeromq-pycryptodome")
@nox.parametrize("coverage", [False, True])
def runtests_zeromq_pycryptodome(session, coverage):
    """
    runtests.py session with zeromq transport and pycryptodome
    """
    session.notify(
        find_session_runner(
            session,
            "runtests-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto="pycryptodome",
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="runtests-cloud")
@nox.parametrize("coverage", [False, True])
def runtests_cloud(session, coverage):
    """
    runtests.py cloud tests session
    """
    # Install requirements
    _install_requirements(session, "zeromq", "unittest-xml-reporting==2.2.1")

    requirements_file = os.path.join(
        "requirements", "static", "ci", _get_pydir(session), "cloud.txt"
    )

    install_command = ["--progress-bar=off", "-r", requirements_file]
    session.install(*install_command, silent=PIP_INSTALL_SILENT)

    cmd_args = [
        "--tests-logfile={}".format(RUNTESTS_LOGFILE),
        "--cloud-provider-tests",
    ] + session.posargs
    _runtests(session, coverage, cmd_args)


@nox.session(python=_PYTHON_VERSIONS, name="runtests-tornado")
@nox.parametrize("coverage", [False, True])
def runtests_tornado(session, coverage):
    """
    runtests.py tornado tests session
    """
    # Install requirements
    _install_requirements(session, "zeromq", "unittest-xml-reporting==2.2.1")
    session.install("--progress-bar=off", "tornado==5.0.2", silent=PIP_INSTALL_SILENT)
    session.install("--progress-bar=off", "pyzmq==17.0.0", silent=PIP_INSTALL_SILENT)

    cmd_args = ["--tests-logfile={}".format(RUNTESTS_LOGFILE)] + session.posargs
    _runtests(session, coverage, cmd_args)


@nox.session(python=_PYTHON_VERSIONS, name="pytest-parametrized")
@nox.parametrize("coverage", [False, True])
@nox.parametrize("transport", ["zeromq", "tcp"])
@nox.parametrize("crypto", [None, "m2crypto", "pycryptodome"])
def pytest_parametrized(session, coverage, transport, crypto):
    """
    DO NOT CALL THIS NOX SESSION DIRECTLY
    """
    # Install requirements
    _install_requirements(session, transport)

    if crypto:
        session.run(
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
            _get_pip_requirements_file(session, transport, crypto=True),
        ]
        install_command.append(crypto)
        session.install(*install_command, silent=PIP_INSTALL_SILENT)

    cmd_args = [
        "--rootdir",
        REPO_ROOT,
        "--log-file={}".format(RUNTESTS_LOGFILE),
        "--log-file-level=debug",
        "--show-capture=no",
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
        find_session_runner(
            session,
            "pytest-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto=None,
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-tcp")
@nox.parametrize("coverage", [False, True])
def pytest_tcp(session, coverage):
    """
    pytest session with TCP transport and default crypto
    """
    session.notify(
        find_session_runner(
            session,
            "pytest-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto=None,
            transport="tcp",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-zeromq")
@nox.parametrize("coverage", [False, True])
def pytest_zeromq(session, coverage):
    """
    pytest session with zeromq transport and default crypto
    """
    session.notify(
        find_session_runner(
            session,
            "pytest-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto=None,
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-m2crypto")
@nox.parametrize("coverage", [False, True])
def pytest_m2crypto(session, coverage):
    """
    pytest session with zeromq transport and m2crypto
    """
    session.notify(
        find_session_runner(
            session,
            "pytest-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto="m2crypto",
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-tcp-m2crypto")
@nox.parametrize("coverage", [False, True])
def pytest_tcp_m2crypto(session, coverage):
    """
    pytest session with TCP transport and m2crypto
    """
    session.notify(
        find_session_runner(
            session,
            "pytest-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto="m2crypto",
            transport="tcp",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-zeromq-m2crypto")
@nox.parametrize("coverage", [False, True])
def pytest_zeromq_m2crypto(session, coverage):
    """
    pytest session with zeromq transport and m2crypto
    """
    session.notify(
        find_session_runner(
            session,
            "pytest-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto="m2crypto",
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-pycryptodome")
@nox.parametrize("coverage", [False, True])
def pytest_pycryptodome(session, coverage):
    """
    pytest session with zeromq transport and pycryptodome
    """
    session.notify(
        find_session_runner(
            session,
            "pytest-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto="pycryptodome",
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-tcp-pycryptodome")
@nox.parametrize("coverage", [False, True])
def pytest_tcp_pycryptodome(session, coverage):
    """
    pytest session with TCP transport and pycryptodome
    """
    session.notify(
        find_session_runner(
            session,
            "pytest-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto="pycryptodome",
            transport="tcp",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-zeromq-pycryptodome")
@nox.parametrize("coverage", [False, True])
def pytest_zeromq_pycryptodome(session, coverage):
    """
    pytest session with zeromq transport and pycryptodome
    """
    session.notify(
        find_session_runner(
            session,
            "pytest-parametrized-{}".format(session.python),
            coverage=coverage,
            crypto="pycryptodome",
            transport="zeromq",
        )
    )


@nox.session(python=_PYTHON_VERSIONS, name="pytest-cloud")
@nox.parametrize("coverage", [False, True])
def pytest_cloud(session, coverage):
    """
    pytest cloud tests session
    """
    # Install requirements
    _install_requirements(session, "zeromq")
    requirements_file = os.path.join(
        "requirements", "static", "ci", _get_pydir(session), "cloud.txt"
    )

    install_command = ["--progress-bar=off", "-r", requirements_file]
    session.install(*install_command, silent=PIP_INSTALL_SILENT)

    cmd_args = [
        "--rootdir",
        REPO_ROOT,
        "--log-file={}".format(RUNTESTS_LOGFILE),
        "--log-file-level=debug",
        "--show-capture=no",
        "-ra",
        "-s",
        "--run-expensive",
        "-k",
        "cloud",
    ] + session.posargs
    _pytest(session, coverage, cmd_args)


@nox.session(python=_PYTHON_VERSIONS, name="pytest-tornado")
@nox.parametrize("coverage", [False, True])
def pytest_tornado(session, coverage):
    """
    pytest tornado tests session
    """
    # Install requirements
    _install_requirements(session, "zeromq")
    session.install("--progress-bar=off", "tornado==5.0.2", silent=PIP_INSTALL_SILENT)
    session.install("--progress-bar=off", "pyzmq==17.0.0", silent=PIP_INSTALL_SILENT)

    cmd_args = [
        "--rootdir",
        REPO_ROOT,
        "--log-file={}".format(RUNTESTS_LOGFILE),
        "--log-file-level=debug",
        "--show-capture=no",
        "-ra",
        "-s",
    ] + session.posargs
    _pytest(session, coverage, cmd_args)


def _pytest(session, coverage, cmd_args):
    # Create required artifacts directories
    _create_ci_directories()

    session.run(
        "pip", "uninstall", "-y", "pytest-salt", silent=True,
    )

    env = {"PYTEST_SESSION": "1"}
    if IS_DARWIN:
        # Don't nuke our multiprocessing efforts objc!
        # https://stackoverflow.com/questions/50168647/multiprocessing-causes-python-to-crash-and-gives-an-error-may-have-been-in-progr
        env["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

    if CI_RUN:
        # We'll print out the collected tests on CI runs.
        # This will show a full list of what tests are going to run, in the right order, which, in case
        # of a test suite hang, helps us pinpoint which test is hanging
        session.run(
            "python", "-m", "pytest", *(cmd_args + ["--collect-only", "-qqq"]), env=env
        )

    try:
        if coverage is True:
            _run_with_coverage(
                session,
                "python",
                "-m",
                "coverage",
                "run",
                "-m",
                "pytest",
                "--showlocals",
                *cmd_args,
                env=env
            )
        else:
            session.run("python", "-m", "pytest", *cmd_args, env=env)
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
            _run_with_coverage(
                session,
                "python",
                "-m",
                "coverage",
                "run",
                "-m",
                "pytest",
                "--showlocals",
                *cmd_args
            )
        else:
            session.run("python", "-m", "pytest", *cmd_args, env=env)
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
    requirements_file = os.path.join(
        "requirements", "static", "ci", _get_pydir(session), "lint.txt"
    )
    install_command = ["--progress-bar=off", "-r", requirements_file]
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
        paths = ["setup.py", "noxfile.py", "salt/", "tasks/"]
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
@nox.parametrize("clean", [False, True])
@nox.parametrize("update", [False, True])
@nox.parametrize("compress", [False, True])
def docs(session, compress, update, clean):
    """
    Build Salt's Documentation
    """
    session.notify("docs-html-{}(compress={})".format(session.python, compress))
    session.notify(
        find_session_runner(
            session,
            "docs-man-{}".format(session.python),
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
    pydir = _get_pydir(session)
    requirements_file = os.path.join(
        "requirements", "static", "ci", _get_pydir(session), "docs.txt"
    )
    install_command = ["--progress-bar=off", "-r", requirements_file]
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
    pydir = _get_pydir(session)
    requirements_file = os.path.join(
        "requirements", "static", "ci", _get_pydir(session), "docs.txt"
    )
    install_command = ["--progress-bar=off", "-r", requirements_file]
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


def _invoke(session):
    """
    Run invoke tasks
    """
    requirements_file = os.path.join(
        "requirements", "static", "ci", _get_pydir(session), "invoke.txt"
    )
    install_command = ["--progress-bar=off", "-r", requirements_file]
    session.install(*install_command, silent=PIP_INSTALL_SILENT)
    cmd = ["inv"]
    files = []

    # Unfortunately, invoke doesn't support the nargs functionality like argpase does.
    # Let's make it behave properly
    for idx, posarg in enumerate(session.posargs):
        if idx == 0:
            cmd.append(posarg)
            continue
        if posarg.startswith("--"):
            cmd.append(posarg)
            continue
        files.append(posarg)
    if files:
        cmd.append("--files={}".format(" ".join(files)))
    session.run(*cmd)


@nox.session(name="invoke", python="3")
def invoke(session):
    """
    Run an invoke target
    """
    _invoke(session)


@nox.session(name="invoke-pre-commit", python=False)
def invoke_pre_commit(session):
    """
    DO NOT CALL THIS NOX SESSION DIRECTLY

    This session is called from a pre-commit hook
    """
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
    _invoke(session)


@nox.session(name="changelog", python="3")
@nox.parametrize("draft", [False, True])
def changelog(session, draft):
    """
    Generate salt's changelog
    """
    requirements_file = os.path.join(
        "requirements", "static", "ci", _get_pydir(session), "changelog.txt"
    )
    install_command = ["--progress-bar=off", "-r", requirements_file]
    session.install(*install_command, silent=PIP_INSTALL_SILENT)

    town_cmd = ["towncrier", "--version={}".format(session.posargs[0])]
    if draft:
        town_cmd.append("--draft")
    session.run(*town_cmd)
