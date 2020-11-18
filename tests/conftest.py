"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)

    tests.conftest
    ~~~~~~~~~~~~~~

    Prepare py.test for our test suite
"""
# pylint: disable=wrong-import-order,wrong-import-position,3rd-party-local-module-not-gated
# pylint: disable=redefined-outer-name,invalid-name,3rd-party-module-not-gated


import logging
import os
import pathlib
import pprint
import re
import shutil
import ssl
import stat
import sys
import textwrap
from functools import partial, wraps
from unittest import TestCase  # pylint: disable=blacklisted-module

import _pytest.logging
import _pytest.skipping
import psutil
import pytest
import salt.config
import salt.loader
import salt.log.mixins
import salt.log.setup
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.win_functions
import saltfactories.utils.compat
from salt.serializers import yaml
from salt.utils.immutabletypes import freeze
from tests.support.helpers import (
    PRE_PYTEST_SKIP_OR_NOT,
    PRE_PYTEST_SKIP_REASON,
    Webserver,
    get_virtualenv_binary_path,
)
from tests.support.pytest.helpers import *  # pylint: disable=unused-wildcard-import
from tests.support.runtests import RUNTIME_VARS
from tests.support.sminion import check_required_sminion_attributes, create_sminion

TESTS_DIR = pathlib.Path(__file__).resolve().parent
PYTESTS_DIR = TESTS_DIR / "pytests"
CODE_DIR = TESTS_DIR.parent

# Change to code checkout directory
os.chdir(str(CODE_DIR))

# Make sure the current directory is the first item in sys.path
if str(CODE_DIR) in sys.path:
    sys.path.remove(str(CODE_DIR))
sys.path.insert(0, str(CODE_DIR))

# Coverage
if "COVERAGE_PROCESS_START" in os.environ:
    MAYBE_RUN_COVERAGE = True
    COVERAGERC_FILE = os.environ["COVERAGE_PROCESS_START"]
else:
    COVERAGERC_FILE = str(CODE_DIR / ".coveragerc")
    MAYBE_RUN_COVERAGE = (
        sys.argv[0].endswith("pytest.py") or "_COVERAGE_RCFILE" in os.environ
    )
    if MAYBE_RUN_COVERAGE:
        # Flag coverage to track suprocesses by pointing it to the right .coveragerc file
        os.environ["COVERAGE_PROCESS_START"] = str(COVERAGERC_FILE)

# Define the pytest plugins we rely on
pytest_plugins = ["tempdir", "helpers_namespace"]

# Define where not to collect tests from
collect_ignore = ["setup.py"]


# Patch PyTest logging handlers
class LogCaptureHandler(
    salt.log.mixins.ExcInfoOnLogLevelFormatMixIn, _pytest.logging.LogCaptureHandler
):
    """
    Subclassing PyTest's LogCaptureHandler in order to add the
    exc_info_on_loglevel functionality and actually make it a NullHandler,
    it's only used to print log messages emmited during tests, which we
    have explicitly disabled in pytest.ini
    """


_pytest.logging.LogCaptureHandler = LogCaptureHandler


class LiveLoggingStreamHandler(
    salt.log.mixins.ExcInfoOnLogLevelFormatMixIn,
    _pytest.logging._LiveLoggingStreamHandler,
):
    """
    Subclassing PyTest's LiveLoggingStreamHandler in order to add the
    exc_info_on_loglevel functionality.
    """


_pytest.logging._LiveLoggingStreamHandler = LiveLoggingStreamHandler

# Reset logging root handlers
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)


# Reset the root logger to its default level(because salt changed it)
logging.root.setLevel(logging.WARNING)

log = logging.getLogger("salt.testsuite")


# ----- PyTest Tempdir Plugin Hooks --------------------------------------------------------------------------------->
def pytest_tempdir_basename():
    """
    Return the temporary directory basename for the salt test suite.
    """
    return "salt-tests-tmpdir"


# <---- PyTest Tempdir Plugin Hooks ----------------------------------------------------------------------------------


# ----- CLI Options Setup ------------------------------------------------------------------------------------------->
def pytest_addoption(parser):
    """
    register argparse-style options and ini-style config values.
    """
    test_selection_group = parser.getgroup("Tests Selection")
    test_selection_group.addoption(
        "--from-filenames",
        default=None,
        help=(
            "Pass a comma-separated list of file paths, and any test module which corresponds to the "
            "specified file(s) will run. For example, if 'setup.py' was passed, then the corresponding "
            "test files defined in 'tests/filename_map.yml' would run. Absolute paths are assumed to be "
            "files containing relative paths, one per line. Providing the paths in a file can help get "
            "around shell character limits when the list of files is long."
        ),
    )
    # Add deprecated CLI flag until we completely switch to PyTest
    test_selection_group.addoption(
        "--names-file", default=None, help="Deprecated option"
    )
    test_selection_group.addoption(
        "--transport",
        default="zeromq",
        choices=("zeromq", "tcp"),
        help=(
            "Select which transport to run the integration tests with, zeromq or tcp. Default: %(default)s"
        ),
    )
    test_selection_group.addoption(
        "--ssh",
        "--ssh-tests",
        dest="ssh",
        action="store_true",
        default=False,
        help="Run salt-ssh tests. These tests will spin up a temporary "
        "SSH server on your machine. In certain environments, this "
        "may be insecure! Default: False",
    )
    test_selection_group.addoption(
        "--proxy",
        "--proxy-tests",
        dest="proxy",
        action="store_true",
        default=False,
        help="Run proxy tests",
    )
    test_selection_group.addoption(
        "--run-slow", action="store_true", default=False, help="Run slow tests.",
    )

    output_options_group = parser.getgroup("Output Options")
    output_options_group.addoption(
        "--output-columns",
        default=80,
        type=int,
        help="Number of maximum columns to use on the output",
    )
    output_options_group.addoption(
        "--no-colors",
        "--no-colours",
        default=False,
        action="store_true",
        help="Disable colour printing.",
    )

    # ----- Test Groups --------------------------------------------------------------------------------------------->
    # This will allow running the tests in chunks
    test_selection_group.addoption(
        "--test-group-count",
        dest="test-group-count",
        type=int,
        help="The number of groups to split the tests into",
    )
    test_selection_group.addoption(
        "--test-group",
        dest="test-group",
        type=int,
        help="The group of tests that should be executed",
    )
    # <---- Test Groups ----------------------------------------------------------------------------------------------


# <---- CLI Options Setup --------------------------------------------------------------------------------------------


# ----- Register Markers -------------------------------------------------------------------------------------------->
@pytest.mark.trylast
def pytest_configure(config):
    """
    called after command line options have been parsed
    and all plugins and initial conftest files been loaded.
    """
    for dirname in CODE_DIR.iterdir():
        if not dirname.is_dir():
            continue
        if dirname != TESTS_DIR:
            config.addinivalue_line("norecursedirs", str(CODE_DIR / dirname))

    # Expose the markers we use to pytest CLI
    config.addinivalue_line(
        "markers",
        "requires_salt_modules(*required_module_names): Skip if at least one module is not available.",
    )
    config.addinivalue_line(
        "markers",
        "requires_salt_states(*required_state_names): Skip if at least one state module is not available.",
    )
    config.addinivalue_line(
        "markers", "windows_whitelisted: Mark test as whitelisted to run under Windows"
    )
    config.addinivalue_line(
        "markers", "requires_sshd_server: Mark test that require an SSH server running"
    )
    # Make sure the test suite "knows" this is a pytest test run
    RUNTIME_VARS.PYTEST_SESSION = True

    # "Flag" the slotTest decorator if we're skipping slow tests or not
    os.environ["SLOW_TESTS"] = str(config.getoption("--run-slow"))


# <---- Register Markers ---------------------------------------------------------------------------------------------


# ----- PyTest Tweaks ----------------------------------------------------------------------------------------------->
def set_max_open_files_limits(min_soft=3072, min_hard=4096):

    # Get current limits
    if salt.utils.platform.is_windows():
        import win32file

        prev_hard = win32file._getmaxstdio()
        prev_soft = 512
    else:
        import resource

        prev_soft, prev_hard = resource.getrlimit(resource.RLIMIT_NOFILE)

    # Check minimum required limits
    set_limits = False
    if prev_soft < min_soft:
        soft = min_soft
        set_limits = True
    else:
        soft = prev_soft

    if prev_hard < min_hard:
        hard = min_hard
        set_limits = True
    else:
        hard = prev_hard

    # Increase limits
    if set_limits:
        log.debug(
            " * Max open files settings is too low (soft: %s, hard: %s) for running the tests. "
            "Trying to raise the limits to soft: %s, hard: %s",
            prev_soft,
            prev_hard,
            soft,
            hard,
        )
        try:
            if salt.utils.platform.is_windows():
                hard = 2048 if hard > 2048 else hard
                win32file._setmaxstdio(hard)
            else:
                resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
        except Exception as err:  # pylint: disable=broad-except
            log.error(
                "Failed to raise the max open files settings -> %s. Please issue the following command "
                "on your console: 'ulimit -u %s'",
                err,
                soft,
            )
            exit(1)
    return soft, hard


def pytest_report_header():
    soft, hard = set_max_open_files_limits()
    return "max open files; soft: {}; hard: {}".format(soft, hard)


def pytest_itemcollected(item):
    """We just collected a test item."""
    try:
        pathlib.Path(item.fspath.strpath).resolve().relative_to(PYTESTS_DIR)
        # Test is under tests/pytests
        if item.cls and issubclass(item.cls, TestCase):
            pytest.fail(
                "The tests under {0!r} MUST NOT use unittest's TestCase class or a subclass of it. "
                "Please move {1!r} outside of {0!r}".format(
                    str(PYTESTS_DIR.relative_to(CODE_DIR)), item.nodeid
                )
            )
    except ValueError:
        # Test is not under tests/pytests
        if not item.cls or (item.cls and not issubclass(item.cls, TestCase)):
            pytest.fail(
                "The test {!r} appears to be written for pytest but it's not under {!r}. Please move it there.".format(
                    item.nodeid, str(PYTESTS_DIR.relative_to(CODE_DIR)), pytrace=False
                )
            )


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_collection_modifyitems(config, items):
    """
    called after collection has been performed, may filter or re-order
    the items in-place.

    :param _pytest.main.Session session: the pytest session object
    :param _pytest.config.Config config: pytest config object
    :param List[_pytest.nodes.Item] items: list of item objects
    """
    # Let PyTest or other plugins handle the initial collection
    yield
    groups_collection_modifyitems(config, items)
    from_filenames_collection_modifyitems(config, items)

    log.warning("Mofifying collected tests to keep track of fixture usage")
    for item in items:
        for fixture in item.fixturenames:
            if fixture not in item._fixtureinfo.name2fixturedefs:
                continue
            for fixturedef in item._fixtureinfo.name2fixturedefs[fixture]:
                if fixturedef.scope != "package":
                    continue
                try:
                    fixturedef.finish.__wrapped__
                except AttributeError:
                    original_func = fixturedef.finish

                    def wrapper(func, fixturedef):
                        @wraps(func)
                        def wrapped(self, request, nextitem=False):
                            try:
                                return self._finished
                            except AttributeError:
                                if nextitem:
                                    fpath = pathlib.Path(self.baseid).resolve()
                                    tpath = pathlib.Path(
                                        nextitem.fspath.strpath
                                    ).resolve()
                                    try:
                                        tpath.relative_to(fpath)
                                        # The test module is within the same package that the fixture is
                                        if (
                                            not request.session.shouldfail
                                            and not request.session.shouldstop
                                        ):
                                            log.debug(
                                                "The next test item is still under the fixture package path. "
                                                "Not terminating %s",
                                                self,
                                            )
                                            return
                                    except ValueError:
                                        pass
                                log.debug("Finish called on %s", self)
                                try:
                                    return func(request)
                                except BaseException as exc:  # pylint: disable=broad-except
                                    pytest.fail(
                                        "Failed to run finish() on {}: {}".format(
                                            fixturedef, exc
                                        ),
                                        pytrace=True,
                                    )
                                finally:
                                    self._finished = True

                        return partial(wrapped, fixturedef)

                    fixturedef.finish = wrapper(fixturedef.finish, fixturedef)
                    try:
                        fixturedef.finish.__wrapped__
                    except AttributeError:
                        fixturedef.finish.__wrapped__ = original_func


@pytest.hookimpl(trylast=True, hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """
    implements the runtest_setup/call/teardown protocol for
    the given test item, including capturing exceptions and calling
    reporting hooks.

    :arg item: test item for which the runtest protocol is performed.

    :arg nextitem: the scheduled-to-be-next test item (or None if this
                   is the end my friend).  This argument is passed on to
                   :py:func:`pytest_runtest_teardown`.

    :return boolean: True if no further hook implementations should be invoked.


    Stops at first non-None result, see :ref:`firstresult`
    """
    request = item._request
    used_fixture_defs = []
    for fixture in item.fixturenames:
        if fixture not in item._fixtureinfo.name2fixturedefs:
            continue
        for fixturedef in reversed(item._fixtureinfo.name2fixturedefs[fixture]):
            if fixturedef.scope != "package":
                continue
            used_fixture_defs.append(fixturedef)
    try:
        # Run the test
        yield
    finally:
        for fixturedef in used_fixture_defs:
            fixturedef.finish(request, nextitem=nextitem)
    del request
    del used_fixture_defs


# <---- PyTest Tweaks ------------------------------------------------------------------------------------------------


# ----- Test Setup -------------------------------------------------------------------------------------------------->
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """
    Fixtures injection based on markers or test skips based on CLI arguments
    """
    integration_utils_tests_path = str(TESTS_DIR / "integration" / "utils")
    if (
        str(item.fspath).startswith(integration_utils_tests_path)
        and PRE_PYTEST_SKIP_OR_NOT is True
    ):
        item._skipped_by_mark = True
        pytest.skip(PRE_PYTEST_SKIP_REASON)

    if saltfactories.utils.compat.has_unittest_attr(item, "__slow_test__"):
        if item.config.getoption("--run-slow") is False:
            item._skipped_by_mark = True
            pytest.skip("Slow tests are disabled!")

    requires_sshd_server_marker = item.get_closest_marker("requires_sshd_server")
    if requires_sshd_server_marker is not None:
        if not item.config.getoption("--ssh-tests"):
            item._skipped_by_mark = True
            pytest.skip("SSH tests are disabled, pass '--ssh-tests' to enable them.")
        item.fixturenames.append("sshd_server")

    requires_salt_modules_marker = item.get_closest_marker("requires_salt_modules")
    if requires_salt_modules_marker is not None:
        required_salt_modules = requires_salt_modules_marker.args
        if len(required_salt_modules) == 1 and isinstance(
            required_salt_modules[0], (list, tuple, set)
        ):
            required_salt_modules = required_salt_modules[0]
        required_salt_modules = set(required_salt_modules)
        not_available_modules = check_required_sminion_attributes(
            "functions", required_salt_modules
        )

        if not_available_modules:
            item._skipped_by_mark = True
            if len(not_available_modules) == 1:
                pytest.skip(
                    "Salt module '{}' is not available".format(*not_available_modules)
                )
            pytest.skip(
                "Salt modules not available: {}".format(
                    ", ".join(not_available_modules)
                )
            )

    requires_salt_states_marker = item.get_closest_marker("requires_salt_states")
    if requires_salt_states_marker is not None:
        required_salt_states = requires_salt_states_marker.args
        if len(required_salt_states) == 1 and isinstance(
            required_salt_states[0], (list, tuple, set)
        ):
            required_salt_states = required_salt_states[0]
        required_salt_states = set(required_salt_states)
        not_available_states = check_required_sminion_attributes(
            "states", required_salt_states
        )

        if not_available_states:
            item._skipped_by_mark = True
            if len(not_available_states) == 1:
                pytest.skip(
                    "Salt state module '{}' is not available".format(
                        *not_available_states
                    )
                )
            pytest.skip(
                "Salt state modules not available: {}".format(
                    ", ".join(not_available_states)
                )
            )

    if salt.utils.platform.is_windows():
        unit_tests_paths = (
            str(TESTS_DIR / "unit"),
            str(PYTESTS_DIR / "unit"),
        )
        if not str(pathlib.Path(item.fspath).resolve()).startswith(unit_tests_paths):
            # Unit tests are whitelisted on windows by default, so, we're only
            # after all other tests
            windows_whitelisted_marker = item.get_closest_marker("windows_whitelisted")
            if windows_whitelisted_marker is None:
                item._skipped_by_mark = True
                pytest.skip("Test is not whitelisted for Windows")


# <---- Test Setup ---------------------------------------------------------------------------------------------------


# ----- Test Groups Selection --------------------------------------------------------------------------------------->
def get_group_size_and_start(total_items, total_groups, group_id):
    """
    Calculate group size and start index.
    """
    base_size = total_items // total_groups
    rem = total_items % total_groups

    start = base_size * (group_id - 1) + min(group_id - 1, rem)
    size = base_size + 1 if group_id <= rem else base_size

    return (start, size)


def get_group(items, total_groups, group_id):
    """
    Get the items from the passed in group based on group size.
    """
    if not 0 < group_id <= total_groups:
        raise ValueError("Invalid test-group argument")

    start, size = get_group_size_and_start(len(items), total_groups, group_id)
    selected = items[start : start + size]
    deselected = items[:start] + items[start + size :]
    assert len(selected) + len(deselected) == len(items)
    return selected, deselected


def groups_collection_modifyitems(config, items):
    group_count = config.getoption("test-group-count")
    group_id = config.getoption("test-group")

    if not group_count or not group_id:
        # We're not selection tests using groups, don't do any filtering
        return

    total_items = len(items)

    tests_in_group, deselected = get_group(items, group_count, group_id)
    # Replace all items in the list
    items[:] = tests_in_group
    if deselected:
        config.hook.pytest_deselected(items=deselected)

    terminal_reporter = config.pluginmanager.get_plugin("terminalreporter")
    terminal_reporter.write(
        "Running test group #{} ({} tests)\n".format(group_id, len(items)), yellow=True,
    )


# <---- Test Groups Selection ----------------------------------------------------------------------------------------


# ----- Fixtures Overrides ------------------------------------------------------------------------------------------>
@pytest.fixture(scope="session")
def salt_factories_config():
    """
    Return a dictionary with the keyworkd arguments for FactoriesManager
    """
    return {
        "code_dir": str(CODE_DIR),
        "inject_coverage": MAYBE_RUN_COVERAGE,
        "inject_sitecustomize": MAYBE_RUN_COVERAGE,
        "start_timeout": 120
        if (os.environ.get("JENKINS_URL") or os.environ.get("CI"))
        else 60,
    }


# <---- Fixtures Overrides -------------------------------------------------------------------------------------------


# ----- Salt Factories ---------------------------------------------------------------------------------------------->
@pytest.fixture(scope="session")
def integration_files_dir(salt_factories):
    """
    Fixture which returns the salt integration files directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = salt_factories.root_dir / "integration-files"
    dirname.mkdir(exist_ok=True)
    for child in (PYTESTS_DIR / "integration" / "files").iterdir():
        if child.is_dir():
            shutil.copytree(str(child), str(dirname / child.name))
        else:
            shutil.copyfile(str(child), str(dirname / child.name))
    return dirname


@pytest.fixture(scope="session")
def state_tree_root_dir(integration_files_dir):
    """
    Fixture which returns the salt state tree root directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = integration_files_dir / "state-tree"
    dirname.mkdir(exist_ok=True)
    return dirname


@pytest.fixture(scope="session")
def pillar_tree_root_dir(integration_files_dir):
    """
    Fixture which returns the salt pillar tree root directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = integration_files_dir / "pillar-tree"
    dirname.mkdir(exist_ok=True)
    return dirname


@pytest.fixture(scope="session")
def base_env_state_tree_root_dir(state_tree_root_dir):
    """
    Fixture which returns the salt base environment state tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = state_tree_root_dir / "base"
    dirname.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_STATE_TREE = str(dirname.resolve())
    RUNTIME_VARS.TMP_BASEENV_STATE_TREE = RUNTIME_VARS.TMP_STATE_TREE
    return dirname


@pytest.fixture(scope="session")
def prod_env_state_tree_root_dir(state_tree_root_dir):
    """
    Fixture which returns the salt prod environment state tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = state_tree_root_dir / "prod"
    dirname.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_PRODENV_STATE_TREE = str(dirname.resolve())
    return dirname


@pytest.fixture(scope="session")
def base_env_pillar_tree_root_dir(pillar_tree_root_dir):
    """
    Fixture which returns the salt base environment pillar tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = pillar_tree_root_dir / "base"
    dirname.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_PILLAR_TREE = str(dirname.resolve())
    RUNTIME_VARS.TMP_BASEENV_PILLAR_TREE = RUNTIME_VARS.TMP_PILLAR_TREE
    return dirname


@pytest.fixture(scope="session")
def prod_env_pillar_tree_root_dir(pillar_tree_root_dir):
    """
    Fixture which returns the salt prod environment pillar tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = pillar_tree_root_dir / "prod"
    dirname.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE = str(dirname.resolve())
    return dirname


@pytest.fixture(scope="session")
def salt_syndic_master_factory(
    request,
    salt_factories,
    base_env_state_tree_root_dir,
    base_env_pillar_tree_root_dir,
    prod_env_state_tree_root_dir,
    prod_env_pillar_tree_root_dir,
):
    root_dir = salt_factories.get_root_dir_for_daemon("syndic_master")
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(exist_ok=True)

    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "syndic_master")
    ) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

        tests_known_hosts_file = str(root_dir / "salt_ssh_known_hosts")
        with salt.utils.files.fopen(tests_known_hosts_file, "w") as known_hosts:
            known_hosts.write("")

    config_defaults["root_dir"] = str(root_dir)
    config_defaults["known_hosts_file"] = tests_known_hosts_file
    config_defaults["syndic_master"] = "localhost"
    config_defaults["transport"] = request.config.getoption("--transport")

    config_overrides = {}
    ext_pillar = []
    if salt.utils.platform.is_windows():
        ext_pillar.append(
            {"cmd_yaml": "type {}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))}
        )
    else:
        ext_pillar.append(
            {"cmd_yaml": "cat {}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))}
        )

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = str(root_dir / "extension_modules")
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(RUNTIME_VARS.FILES, "extension_modules"),
            extension_modules_path,
        )

    # Copy the autosign_file to the new  master root_dir
    autosign_file_path = str(root_dir / "autosign_file")
    shutil.copyfile(
        os.path.join(RUNTIME_VARS.FILES, "autosign_file"), autosign_file_path
    )
    # all read, only owner write
    autosign_file_permissions = (
        stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
    )
    os.chmod(autosign_file_path, autosign_file_permissions)

    config_overrides.update(
        {
            "ext_pillar": ext_pillar,
            "extension_modules": extension_modules_path,
            "file_roots": {
                "base": [
                    str(base_env_state_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "file", "base"),
                ],
                # Alternate root to test __env__ choices
                "prod": [
                    str(prod_env_state_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "file", "prod"),
                ],
            },
            "pillar_roots": {
                "base": [
                    str(base_env_pillar_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "pillar", "base"),
                ],
                "prod": [str(prod_env_pillar_tree_root_dir)],
            },
        }
    )

    factory = salt_factories.get_salt_master_daemon(
        "syndic_master",
        order_masters=True,
        config_defaults=config_defaults,
        config_overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    return factory


@pytest.fixture(scope="session")
def salt_syndic_factory(salt_factories, salt_syndic_master_factory):
    config_defaults = {"master": None, "minion": None, "syndic": None}
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "syndic")) as rfh:
        opts = yaml.deserialize(rfh.read())

        opts["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
        opts["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
        opts["transport"] = salt_syndic_master_factory.config["transport"]
        config_defaults["syndic"] = opts
    factory = salt_syndic_master_factory.get_salt_syndic_daemon(
        "syndic",
        config_defaults=config_defaults,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    return factory


@pytest.fixture(scope="session")
def salt_master_factory(
    salt_factories,
    salt_syndic_master_factory,
    base_env_state_tree_root_dir,
    base_env_pillar_tree_root_dir,
    prod_env_state_tree_root_dir,
    prod_env_pillar_tree_root_dir,
):
    root_dir = salt_factories.get_root_dir_for_daemon("master")
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(exist_ok=True)

    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "master")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

        tests_known_hosts_file = str(root_dir / "salt_ssh_known_hosts")
        with salt.utils.files.fopen(tests_known_hosts_file, "w") as known_hosts:
            known_hosts.write("")

    config_defaults["root_dir"] = str(root_dir)
    config_defaults["known_hosts_file"] = tests_known_hosts_file
    config_defaults["syndic_master"] = "localhost"
    config_defaults["transport"] = salt_syndic_master_factory.config["transport"]
    config_defaults["reactor"] = [
        {"salt/test/reactor": [os.path.join(RUNTIME_VARS.FILES, "reactor-test.sls")]}
    ]

    config_overrides = {}
    ext_pillar = []
    if salt.utils.platform.is_windows():
        ext_pillar.append(
            {"cmd_yaml": "type {}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))}
        )
    else:
        ext_pillar.append(
            {"cmd_yaml": "cat {}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))}
        )
    ext_pillar.append(
        {
            "file_tree": {
                "root_dir": os.path.join(RUNTIME_VARS.PILLAR_DIR, "base", "file_tree"),
                "follow_dir_links": False,
                "keep_newline": True,
            }
        }
    )
    config_overrides["pillar_opts"] = True

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = str(root_dir / "extension_modules")
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(RUNTIME_VARS.FILES, "extension_modules"),
            extension_modules_path,
        )

    # Copy the autosign_file to the new  master root_dir
    autosign_file_path = str(root_dir / "autosign_file")
    shutil.copyfile(
        os.path.join(RUNTIME_VARS.FILES, "autosign_file"), autosign_file_path
    )
    # all read, only owner write
    autosign_file_permissions = (
        stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
    )
    os.chmod(autosign_file_path, autosign_file_permissions)

    config_overrides.update(
        {
            "ext_pillar": ext_pillar,
            "extension_modules": extension_modules_path,
            "file_roots": {
                "base": [
                    str(base_env_state_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "file", "base"),
                ],
                # Alternate root to test __env__ choices
                "prod": [
                    str(prod_env_state_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "file", "prod"),
                ],
            },
            "pillar_roots": {
                "base": [
                    str(base_env_pillar_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "pillar", "base"),
                ],
                "prod": [str(prod_env_pillar_tree_root_dir)],
            },
        }
    )

    # Let's copy over the test cloud config files and directories into the running master config directory
    for entry in os.listdir(RUNTIME_VARS.CONF_DIR):
        if not entry.startswith("cloud"):
            continue
        source = os.path.join(RUNTIME_VARS.CONF_DIR, entry)
        dest = str(conf_dir / entry)
        if os.path.isdir(source):
            shutil.copytree(source, dest)
        else:
            shutil.copyfile(source, dest)

    factory = salt_syndic_master_factory.get_salt_master_daemon(
        "master",
        config_defaults=config_defaults,
        config_overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    return factory


@pytest.fixture(scope="session")
def salt_minion_factory(salt_master_factory):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "minion")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = salt_master_factory.config["transport"]

    config_overrides = {
        "file_roots": salt_master_factory.config["file_roots"].copy(),
        "pillar_roots": salt_master_factory.config["pillar_roots"].copy(),
    }

    virtualenv_binary = get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary
    factory = salt_master_factory.get_salt_minion_daemon(
        "minion",
        config_defaults=config_defaults,
        config_overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    factory.register_after_terminate_callback(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )
    return factory


@pytest.fixture(scope="session")
def salt_sub_minion_factory(salt_master_factory):
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "sub_minion")
    ) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = salt_master_factory.config["transport"]

    config_overrides = {
        "file_roots": salt_master_factory.config["file_roots"].copy(),
        "pillar_roots": salt_master_factory.config["pillar_roots"].copy(),
    }

    virtualenv_binary = get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary
    factory = salt_master_factory.get_salt_minion_daemon(
        "sub_minion",
        config_defaults=config_defaults,
        config_overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    factory.register_after_terminate_callback(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )
    return factory


@pytest.fixture(scope="session")
def salt_proxy_factory(salt_factories, salt_master_factory):
    proxy_minion_id = "proxytest"
    root_dir = salt_factories.get_root_dir_for_daemon(proxy_minion_id)
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(parents=True, exist_ok=True)
    RUNTIME_VARS.TMP_PROXY_CONF_DIR = str(conf_dir)

    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "proxy")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

    config_defaults["root_dir"] = str(root_dir)
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = salt_master_factory.config["transport"]

    factory = salt_master_factory.get_salt_proxy_minion_daemon(
        proxy_minion_id,
        config_defaults=config_defaults,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    factory.register_after_terminate_callback(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )
    return factory


@pytest.fixture(scope="session")
def salt_cli(salt_master_factory):
    return salt_master_factory.get_salt_cli()


@pytest.fixture(scope="session")
def salt_cp_cli(salt_master_factory):
    return salt_master_factory.get_salt_cp_cli()


@pytest.fixture(scope="session")
def salt_key_cli(salt_master_factory):
    return salt_master_factory.get_salt_key_cli()


@pytest.fixture(scope="session")
def salt_run_cli(salt_master_factory):
    return salt_master_factory.get_salt_run_cli()


@pytest.fixture(scope="session")
def salt_ssh_cli(salt_master_factory):
    return salt_master_factory.get_salt_ssh_cli()


@pytest.fixture(scope="session")
def salt_call_cli(salt_minion_factory):
    return salt_minion_factory.get_salt_call_cli()


@pytest.fixture(scope="session", autouse=True)
def bridge_pytest_and_runtests(
    reap_stray_processes,
    salt_factories,
    salt_syndic_master_factory,
    salt_syndic_factory,
    salt_master_factory,
    salt_minion_factory,
    salt_sub_minion_factory,
    sshd_config_dir,
):
    # Make sure unittest2 uses the pytest generated configuration
    RUNTIME_VARS.RUNTIME_CONFIGS["master"] = freeze(salt_master_factory.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["minion"] = freeze(salt_minion_factory.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["sub_minion"] = freeze(salt_sub_minion_factory.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["syndic_master"] = freeze(
        salt_syndic_master_factory.config
    )
    RUNTIME_VARS.RUNTIME_CONFIGS["syndic"] = freeze(salt_syndic_factory.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["client_config"] = freeze(
        salt.config.client_config(salt_master_factory.config["conf_file"])
    )

    # Make sure unittest2 classes know their paths
    RUNTIME_VARS.TMP_ROOT_DIR = str(salt_factories.root_dir.resolve())
    RUNTIME_VARS.TMP_CONF_DIR = os.path.dirname(salt_master_factory.config["conf_file"])
    RUNTIME_VARS.TMP_MINION_CONF_DIR = os.path.dirname(
        salt_minion_factory.config["conf_file"]
    )
    RUNTIME_VARS.TMP_SUB_MINION_CONF_DIR = os.path.dirname(
        salt_sub_minion_factory.config["conf_file"]
    )
    RUNTIME_VARS.TMP_SYNDIC_MASTER_CONF_DIR = os.path.dirname(
        salt_syndic_master_factory.config["conf_file"]
    )
    RUNTIME_VARS.TMP_SYNDIC_MINION_CONF_DIR = os.path.dirname(
        salt_syndic_factory.config["conf_file"]
    )
    RUNTIME_VARS.TMP_SSH_CONF_DIR = str(sshd_config_dir)


@pytest.fixture(scope="session")
def sshd_config_dir(salt_factories):
    config_dir = salt_factories.get_root_dir_for_daemon("sshd")
    yield config_dir
    shutil.rmtree(str(config_dir), ignore_errors=True)


@pytest.fixture(scope="module")
def sshd_server(salt_factories, sshd_config_dir, salt_master):
    sshd_config_dict = {
        "Protocol": "2",
        # Turn strict modes off so that we can operate in /tmp
        "StrictModes": "no",
        # Logging
        "SyslogFacility": "AUTH",
        "LogLevel": "INFO",
        # Authentication:
        "LoginGraceTime": "120",
        "PermitRootLogin": "without-password",
        "PubkeyAuthentication": "yes",
        # Don't read the user's ~/.rhosts and ~/.shosts files
        "IgnoreRhosts": "yes",
        "HostbasedAuthentication": "no",
        # To enable empty passwords, change to yes (NOT RECOMMENDED)
        "PermitEmptyPasswords": "no",
        # Change to yes to enable challenge-response passwords (beware issues with
        # some PAM modules and threads)
        "ChallengeResponseAuthentication": "no",
        # Change to no to disable tunnelled clear text passwords
        "PasswordAuthentication": "no",
        "X11Forwarding": "no",
        "X11DisplayOffset": "10",
        "PrintMotd": "no",
        "PrintLastLog": "yes",
        "TCPKeepAlive": "yes",
        "AcceptEnv": "LANG LC_*",
        "Subsystem": "sftp /usr/lib/openssh/sftp-server",
        "UsePAM": "yes",
    }
    factory = salt_factories.get_sshd_daemon(
        sshd_config_dict=sshd_config_dict, config_dir=sshd_config_dir,
    )
    # We also need a salt-ssh roster config file
    roster_path = pathlib.Path(salt_master.config_dir) / "roster"
    roster_contents = textwrap.dedent(
        """\
        localhost:
          host: 127.0.0.1
          port: {}
          user: {}
          mine_functions:
            test.arg: ['itworked']
        """.format(
            factory.listen_port, RUNTIME_VARS.RUNNING_TESTS_USER
        )
    )
    if salt.utils.platform.is_darwin():
        roster_contents += "  set_path: $PATH:/usr/local/bin/\n"
    log.debug(
        "Writing to configuration file %s. Configuration:\n%s",
        roster_path,
        roster_contents,
    )
    with salt.utils.files.fopen(str(roster_path), "w") as wfh:
        wfh.write(roster_contents)

    with factory.started():
        yield factory
    if roster_path.exists():
        roster_path.unlink()


# <---- Salt Factories -----------------------------------------------------------------------------------------------


# ----- From Filenames Test Selection ------------------------------------------------------------------------------->
def _match_to_test_file(match):
    parts = match.split(".")
    parts[-1] += ".py"
    return TESTS_DIR.joinpath(*parts).relative_to(CODE_DIR)


def from_filenames_collection_modifyitems(config, items):
    from_filenames = config.getoption("--from-filenames")
    if not from_filenames:
        # Don't do anything
        return

    test_categories_paths = (
        (TESTS_DIR / "integration").relative_to(CODE_DIR),
        (TESTS_DIR / "multimaster").relative_to(CODE_DIR),
        (TESTS_DIR / "unit").relative_to(CODE_DIR),
        (PYTESTS_DIR / "e2e").relative_to(CODE_DIR),
        (PYTESTS_DIR / "functional").relative_to(CODE_DIR),
        (PYTESTS_DIR / "integration").relative_to(CODE_DIR),
        (PYTESTS_DIR / "unit").relative_to(CODE_DIR),
    )

    test_module_paths = set()
    from_filenames_listing = set()
    for path in [pathlib.Path(path.strip()) for path in from_filenames.split(",")]:
        if path.is_absolute():
            # In this case, this path is considered to be a file containing a line separated list
            # of files to consider
            with salt.utils.files.fopen(str(path)) as rfh:
                for line in rfh:
                    line_path = pathlib.Path(line.strip())
                    if not line_path.exists():
                        continue
                    from_filenames_listing.add(line_path)
            continue
        from_filenames_listing.add(path)

    filename_map = yaml.deserialize((TESTS_DIR / "filename_map.yml").read_text())
    # Let's add the match all rule
    for rule, matches in filename_map.items():
        if rule == "*":
            for match in matches:
                test_module_paths.add(_match_to_test_file(match))
            break

    # Let's now go through the list of files gathered
    for filename in from_filenames_listing:
        if str(filename).startswith("tests/"):
            # Tests in the listing don't require additional matching and will be added to the
            # list of tests to run
            test_module_paths.add(filename)
            continue
        if filename.name == "setup.py" or str(filename).startswith("salt/"):
            if path.name == "__init__.py":
                # No direct macthing
                continue
            # Now let's try a direct match between the passed file and possible test modules
            for test_categories_path in test_categories_paths:
                test_module_path = test_categories_path / "test_{}".format(path.name)
                if test_module_path.is_file():
                    test_module_paths.add(test_module_path)
                    continue

            # Do we have an entry in tests/filename_map.yml
            for rule, matches in filename_map.items():
                if rule == "*":
                    continue
                elif "|" in rule:
                    # This is regex
                    if re.match(rule, str(filename)):
                        for match in matches:
                            test_module_paths.add(_match_to_test_file(match))
                elif "*" in rule or "\\" in rule:
                    # Glob matching
                    for filerule in CODE_DIR.glob(rule):
                        if not filerule.exists():
                            continue
                        filerule = filerule.relative_to(CODE_DIR)
                        if filerule != filename:
                            continue
                        for match in matches:
                            test_module_paths.add(_match_to_test_file(match))
                else:
                    if str(filename) != rule:
                        continue
                    # Direct file paths as rules
                    filerule = pathlib.Path(rule)
                    if not filerule.exists():
                        continue
                    for match in matches:
                        test_module_paths.add(_match_to_test_file(match))
            continue
        else:
            log.debug("Don't know what to do with path %s", filename)

    selected = []
    deselected = []
    for item in items:
        itempath = pathlib.Path(str(item.fspath)).resolve().relative_to(CODE_DIR)
        if itempath in test_module_paths:
            selected.append(item)
        else:
            deselected.append(item)

    items[:] = selected
    if deselected:
        config.hook.pytest_deselected(items=deselected)


# <---- From Filenames Test Selection --------------------------------------------------------------------------------


# ----- Custom Fixtures --------------------------------------------------------------------------------------------->
@pytest.fixture(scope="session")
def reap_stray_processes():
    # Run tests
    yield

    children = psutil.Process(os.getpid()).children(recursive=True)
    if not children:
        log.info("No astray processes found")
        return

    def on_terminate(proc):
        log.debug("Process %s terminated with exit code %s", proc, proc.returncode)

    if children:
        # Reverse the order, sublings first, parents after
        children.reverse()
        log.warning(
            "Test suite left %d astray processes running. Killing those processes:\n%s",
            len(children),
            pprint.pformat(children),
        )

        _, alive = psutil.wait_procs(children, timeout=3, callback=on_terminate)
        for child in alive:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                continue

        _, alive = psutil.wait_procs(alive, timeout=3, callback=on_terminate)
        if alive:
            # Give up
            for child in alive:
                log.warning(
                    "Process %s survived SIGKILL, giving up:\n%s",
                    child,
                    pprint.pformat(child.as_dict()),
                )


@pytest.fixture(scope="session")
def sminion():
    return create_sminion()


@pytest.fixture(scope="session")
def grains(sminion):
    return sminion.opts["grains"].copy()


@pytest.fixture
def ssl_webserver(integration_files_dir, scope="module"):
    """
    spins up an https webserver.
    """
    if sys.version_info < (3, 5, 3):
        pytest.skip("Python versions older than 3.5.3 do not define `ssl.PROTOCOL_TLS`")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS)
    context.load_cert_chain(
        str(integration_files_dir / "https" / "cert.pem"),
        str(integration_files_dir / "https" / "key.pem"),
    )

    webserver = Webserver(root=str(integration_files_dir), ssl_opts=context)
    webserver.start()
    yield webserver
    webserver.stop()


# <---- Custom Fixtures ----------------------------------------------------------------------------------------------
