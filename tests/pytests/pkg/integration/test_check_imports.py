import logging
import subprocess

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

    # Import required for all OS'es
    for import_name in [
        "jinja2",
        "telnetlib",
        "yaml",
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


def test_check_imports(salt_cli, salt_minion, state_name):
    """
    Test imports
    """
    ret = salt_cli.run("state.sls", state_name, minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert ret.data
    result = MultiStateResult(raw=ret.data)
    for state_ret in result:
        assert state_ret.result is True
