from contextlib import ExitStack

import pytest

pytestmark = [
    pytest.mark.slow_test,
]


def get_module_types():
    module_types = [
        "clouds",
        "modules",
        "states",
        "grains",
        "renderers",
        "returners",
        "output",
        "proxy",
        "runners",
        "wheel",
        "engines",
        "thorium",
        "queues",
        "pillar",
        "utils",
        "sdb",
        "cache",
        "fileserver",
        "tops",
        "tokens",
        "serializers",
        "executors",
        "roster",
    ]
    return module_types


@pytest.fixture(params=get_module_types())
def module_type(request):
    yield request.param


@pytest.fixture
def module_sync_functions():
    yield {
        "clouds": "clouds",
        "modules": "modules",
        "states": "states",
        "grains": "grains",
        "renderers": "renderers",
        "returners": "returners",
        "output": "output",
        "proxy": "proxymodules",
        "runners": "runners",
        "wheel": "wheel",
        "engines": "engines",
        "thorium": "thorium",
        "queues": "queues",
        "pillar": "pillar",
        "utils": "utils",
        "sdb": "sdb",
        "cache": "cache",
        "fileserver": "fileserver",
        "tops": "tops",
        "tokens": "eauth_tokens",
        "serializers": "serializers",
        "executors": "executors",
        "roster": "roster",
    }


def test_sync(
    module_type, module_sync_functions, salt_run_cli, salt_minion, salt_master
):
    """
    Ensure modules are synced when various sync functions are called
    """
    module_name = "hello_sync_{}".format(module_type)
    module_contents = """
def __virtual__():
    return "hello"

def world():
    return "world"
"""

    test_moduledir = salt_master.state_tree.base.paths[0] / "_{}".format(module_type)
    test_moduledir.mkdir(parents=True, exist_ok=True)
    module_tempfile = salt_master.state_tree.base.temp_file(
        "_{}/{}.py".format(module_type, module_name), module_contents
    )

    with module_tempfile, test_moduledir:
        salt_cmd = "saltutil.sync_{}".format(module_sync_functions[module_type])
        ret = salt_run_cli.run(salt_cmd)
        assert ret.returncode == 0
        assert "{}.hello".format(module_type) in ret.stdout


def _write_module_dir_and_file(module_type, salt_minion, salt_master):
    """
    Write out dummy module to appropriate module location
    """
    module_name = "hello_sync_all"
    module_contents = """
def __virtual__():
    return "hello"

def world():
    return "world"
"""

    test_moduledir = salt_master.state_tree.base.paths[0] / "_{}".format(module_type)
    test_moduledir.mkdir(parents=True, exist_ok=True)

    module_tempfile = salt_master.state_tree.base.temp_file(
        "_{}/{}.py".format(module_type, module_name), module_contents
    )

    return module_tempfile


def test_sync_all(salt_run_cli, salt_minion, salt_master):
    """
    Ensure all modules are synced when sync_all function is called
    """

    with ExitStack() as stack:
        files = [
            stack.enter_context(
                _write_module_dir_and_file(_module_type, salt_minion, salt_master)
            )
            for _module_type in get_module_types()
        ]

        salt_cmd = "saltutil.sync_all"
        ret = salt_run_cli.run(salt_cmd)

        assert ret.returncode == 0
        for module_type in get_module_types():
            assert "{}.hello".format(module_type) in ret.stdout
