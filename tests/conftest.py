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
import sys
from functools import partial, wraps

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
from _pytest.mark.evaluate import MarkEvaluator
from salt.serializers import yaml
from tests.support.helpers import PRE_PYTEST_SKIP_OR_NOT, PRE_PYTEST_SKIP_REASON
from tests.support.pytest.helpers import *  # pylint: disable=unused-wildcard-import
from tests.support.runtests import RUNTIME_VARS
from tests.support.sminion import check_required_sminion_attributes, create_sminion

TESTS_DIR = pathlib.Path(__file__).resolve().parent
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
            "Select which transport to run the integration tests with, zeromq or tcp. Default: %default"
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
                if fixturedef.scope == "function":
                    continue
                try:
                    node_ids = fixturedef.node_ids
                except AttributeError:
                    node_ids = fixturedef.node_ids = set()
                node_ids.add(item.nodeid)
                try:
                    fixturedef.finish.__wrapped__
                except AttributeError:
                    original_func = fixturedef.finish

                    def wrapper(func, fixturedef):
                        @wraps(func)
                        def wrapped(self, request):
                            try:
                                return self._finished
                            except AttributeError:
                                if self.node_ids:
                                    if (
                                        not request.session.shouldfail
                                        and not request.session.shouldstop
                                    ):
                                        log.debug(
                                            "%s is still going to be used, not terminating it. "
                                            "Still in use on:\n%s",
                                            self,
                                            pprint.pformat(list(self.node_ids)),
                                        )
                                        return
                                log.debug("Finish called on %s", self)
                                try:
                                    return func(request)
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
            if fixturedef.scope == "function":
                continue
            used_fixture_defs.append(fixturedef)
    try:
        # Run the test
        yield
    finally:
        for fixturedef in used_fixture_defs:
            if item.nodeid in fixturedef.node_ids:
                fixturedef.node_ids.remove(item.nodeid)
            if not fixturedef.node_ids:
                # This fixture is not used in any more test functions
                fixturedef.finish(request)
    del request
    del used_fixture_defs


def pytest_runtest_teardown(item, nextitem):
    """
    called after ``pytest_runtest_call``.

    :arg nextitem: the scheduled-to-be-next test item (None if no further
                   test item is scheduled).  This argument can be used to
                   perform exact teardowns, i.e. calling just enough finalizers
                   so that nextitem only needs to call setup-functions.
    """
    # PyTest doesn't reset the capturing log handler when done with it.
    # Reset it to free used memory and python objects
    # We currently have PyTest's log_print setting set to false, if it was
    # set to true, the call bellow would make PyTest not print any logs at all.
    item.catch_log_handler.reset()


# <---- PyTest Tweaks ------------------------------------------------------------------------------------------------


# ----- Test Setup -------------------------------------------------------------------------------------------------->
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """
    Fixtures injection based on markers or test skips based on CLI arguments
    """
    integration_utils_tests_path = str(CODE_DIR / "tests" / "integration" / "utils")
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
        if not item.fspath.fnmatch(str(CODE_DIR / "tests" / "unit" / "*")):
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
def log_server_host(request):
    return "0.0.0.0"


@pytest.fixture(scope="session")
def salt_factories_config(log_server_host, log_server_port, log_server_level):
    """
    Return a dictionary with the keyworkd arguments for SaltFactoriesManager
    """
    return {
        "executable": sys.executable,
        "code_dir": str(CODE_DIR),
        "inject_coverage": MAYBE_RUN_COVERAGE,
        "inject_sitecustomize": MAYBE_RUN_COVERAGE,
        "start_timeout": 120
        if (os.environ.get("JENKINS_URL") or os.environ.get("CI"))
        else 60,
        "log_server_host": log_server_host,
        "log_server_port": log_server_port,
        "log_server_level": log_server_level,
    }


# <---- Pytest Helpers -----------------------------------------------------------------------------------------------

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
        (CODE_DIR / "tests" / "integration").relative_to(CODE_DIR),
        (CODE_DIR / "tests" / "multimaster").relative_to(CODE_DIR),
        (CODE_DIR / "tests" / "unit").relative_to(CODE_DIR),
        (CODE_DIR / "tests" / "pytests" / "e2e").relative_to(CODE_DIR),
        (CODE_DIR / "tests" / "pytests" / "functional").relative_to(CODE_DIR),
        (CODE_DIR / "tests" / "pytests" / "integration").relative_to(CODE_DIR),
        (CODE_DIR / "tests" / "pytests" / "unit").relative_to(CODE_DIR),
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

    filename_map = yaml.deserialize(
        (CODE_DIR / "tests" / "filename_map.yml").read_text()
    )
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

# ----- Custom Grains Mark Evaluator -------------------------------------------------------------------------------->
class GrainsMarkEvaluator(MarkEvaluator):
    _cached_grains = None

    def _getglobals(self):
        item_globals = super()._getglobals()
        if GrainsMarkEvaluator._cached_grains is None:
            sminion = create_sminion()
            GrainsMarkEvaluator._cached_grains = sminion.opts["grains"].copy()
        item_globals["grains"] = GrainsMarkEvaluator._cached_grains.copy()
        return item_globals


# Patch PyTest's skipping MarkEvaluator to use our GrainsMarkEvaluator
_pytest.skipping.MarkEvaluator = GrainsMarkEvaluator
# <---- Custom Grains Mark Evaluator ---------------------------------------------------------------------------------


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
def grains(request):
    sminion = create_sminion()
    return sminion.opts["grains"].copy()


# <---- Custom Fixtures ----------------------------------------------------------------------------------------------
