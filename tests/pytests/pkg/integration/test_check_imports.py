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

def run():
    config = {}
    for test_import in [
        'templates', 'platform', 'cli', 'executors', 'config', 'wheel', 'netapi',
        'cache', 'proxy', 'transport', 'metaproxy', 'modules', 'tokens', 'matchers',
        'acl', 'auth', 'log', 'engines', 'client', 'returners', 'runners', 'tops',
        'output', 'daemons', 'thorium', 'renderers', 'states', 'cloud', 'roster',
        'beacons', 'pillar', 'spm', 'utils', 'sdb', 'fileserver', 'defaults',
        'ext', 'queues', 'grains', 'serializers'
    ]:
        try:
            import_name = "salt.{}".format(test_import)
            importlib.import_module(import_name)
            config['test_imports_succeeded'] = {
                'test.succeed_without_changes': [
                    {
                        'name': import_name
                    },
                ],
            }
        except ModuleNotFoundError as err:
            config['test_imports_failed'] = {
                'test.fail_without_changes': [
                    {
                        'name': import_name,
                        'comment': "The imports test failed. The error was: {}".format(err)
                    },
                ],
            }

    for stdlib_import in ["telnetlib"]:
        try:
            importlib.import_module(stdlib_import)
            config['stdlib_imports_succeeded'] = {
                'test.succeed_without_changes': [
                    {
                        'name': stdlib_import
                    },
                ],
            }
        except ModuleNotFoundError as err:
            config['stdlib_imports_failed'] = {
                'test.fail_without_changes': [
                    {
                        'name': stdlib_import,
                        'comment': "The stdlib imports test failed. The error was: {}".format(err)
                    },
                ],
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
