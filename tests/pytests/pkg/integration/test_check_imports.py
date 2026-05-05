import logging
import subprocess
import time

import pytest
from pytestskipmarkers.utils import platform
from saltfactories.utils.functional import MultiStateResult

pytestmark = [
    pytest.mark.skip_on_windows,
]

log = logging.getLogger(__name__)


CHECK_IMPORTS_SLS_CONTENTS = """
#!py
import importlib
import sys

def run():
    config = {}
    for module in [
        '_logging',
        'acl',
        'auth',
        'beacons',
        'cache',
        'cli',
        'client',
        'cloud',
        'config',
        'daemons',
        'defaults',
        'engines',
        'executors',
        'ext',
        'fileserver',
        'grains',
        'matchers',
        'metaproxy',
        'modules',
        'netapi',
        'output',
        'pillar',
        'platform',
        'proxy',
        'queues',
        'renderers',
        'returners',
        'roster',
        'runners',
        'sdb',
        'serializers',
        'spm',
        'states',
        'templates',
        'thorium',
        'tokens',
        'tops',
        'transport',
        'utils',
        'wheel',
    ]:
        import_name = "salt.{}".format(module)
        try:
            importlib.import_module(import_name)
            config[import_name] = {
                'test.succeed_without_changes': [
                    {
                        "name": import_name,
                        'comment': "The '{}' import succeeded.".format(import_name)
                    }
                ]
            }
        except ModuleNotFoundError as err:
            config[import_name] = {
                'test.fail_without_changes': [
                    {
                        "name": import_name,
                        'comment': "The '{}' import failed. The error was: {}".format(import_name, err)
                    }
                ]
            }

    # Import required for all OS'es (telnetlib was removed from the stdlib in Python 3.13)
    core_libs = ["jinja2", "yaml"]
    if sys.version_info < (3, 13):
        core_libs.insert(1, "telnetlib")
    for import_name in core_libs:
        try:
            importlib.import_module(import_name)
            config[import_name] = {
                'test.succeed_without_changes': [
                    {
                        "name": import_name,
                        'comment': "The '{}' import succeeded.".format(import_name)
                    }
                ]
            }
        except ModuleNotFoundError as err:
            config[import_name] = {
                'test.fail_without_changes': [
                    {
                        "name": import_name,
                        'comment': "The '{}' import failed. The error was: {}".format(import_name, err)
                    }
                ]
            }

    # Windows specific requirements (I think, there may be some for other OSes in here)
    if sys.platform == "win32":
        for import_name in [
            "cffi",
            "clr_loader",
            "lxml",
            "pythonnet",
            "pytz",
            "pywintypes",
            "timelib",
            "win32",
            "wmi",
            "xmltodict",
        ]:
            try:
                importlib.import_module(import_name)
                config[import_name] = {
                    'test.succeed_without_changes': [
                        {
                            "name": import_name,
                            'comment': "The '{}' import succeeded.".format(import_name)
                        }
                    ]
                }
            except ModuleNotFoundError as err:
                config[import_name] = {
                    'test.fail_without_changes': [
                        {
                            "name": import_name,
                            'comment': "The '{}' import failed. The error was: {}".format(import_name, err)
                        }
                    ]
                }
    return config
"""


@pytest.fixture
def state_name(salt_master):
    name = "check-imports"
    with salt_master.state_tree.base.temp_file(
        f"{name}.sls", CHECK_IMPORTS_SLS_CONTENTS
    ):
        if not platform.is_windows() and not platform.is_darwin():
            subprocess.run(
                [
                    "chown",
                    "-R",
                    "salt:salt",
                    str(salt_master.state_tree.base.write_path),
                ],
                check=False,
            )
        yield name


def _ensure_factory_running(factory, attempts=3, poll_iterations=30, poll_seconds=2):
    """
    Wait for ``factory.is_running()`` to return True, restarting the daemon if
    it is not. Pkg-system-service tests on macOS run through ``launchctl``;
    the prior pkg-downgrade test in the same session calls
    ``launchctl bootout`` for ``com.saltstack.salt.{minion,master,...}``,
    which terminates the test framework's daemons. Re-bootstrap them on
    demand instead of letting the publish silently drop.
    """
    for _ in range(attempts):
        for _ in range(poll_iterations):
            if factory.is_running():
                return True
            time.sleep(poll_seconds)
        factory.start()
    return factory.is_running()


def test_check_imports(salt_cli, salt_minion, state_name):
    """
    Test imports
    """
    # ``factory.started()`` succeeded once at fixture setup; in pkg downgrade
    # scenarios the launchctl-managed daemon may have been booted out by a
    # later install_previous() step. Re-bootstrap if needed so the publish
    # does not silently time out.
    assert _ensure_factory_running(salt_minion)
    ret = salt_cli.run("state.sls", state_name, minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert ret.data
    result = MultiStateResult(raw=ret.data)
    for state_ret in result:
        assert state_ret.result is True
