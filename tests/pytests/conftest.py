"""
    tests.pytests.conftest
    ~~~~~~~~~~~~~~~~~~~~~~
"""
import functools
import inspect
import logging
import os
import shutil
import stat

import attr
import pytest
import salt.ext.tornado.ioloop
import salt.utils.files
import salt.utils.platform
from salt.serializers import yaml
from saltfactories.utils import random_string
from saltfactories.utils.ports import get_unused_localhost_port
from tests.support.helpers import get_virtualenv_binary_path
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def salt_minion_id():
    return random_string("minion-")


@pytest.fixture(scope="session")
def salt_sub_minion_id():
    return random_string("sub-minion-")


@pytest.fixture(scope="session")
def sdb_etcd_port():
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def vault_port():
    return get_unused_localhost_port()


@attr.s(slots=True, frozen=True)
class ReactorEvent:
    sls_path = attr.ib()
    tag = attr.ib()
    event_tag = attr.ib()


@pytest.fixture(scope="session")
def reactor_event(tmp_path_factory):

    reactor_tag = "salt/event/test"
    event_tag = random_string("test/reaction/")
    reactors_dir = tmp_path_factory.mktemp("reactors")
    reactor_test_contents = """
    reactor-test:
      runner.event.send:
        - args:
          - tag: {}
          - data:
              test_reaction: True
    """.format(
        event_tag
    )
    try:
        with pytest.helpers.temp_file(
            "reactor-test.sls", reactor_test_contents, reactors_dir
        ) as reactor_file_path:
            yield ReactorEvent(reactor_file_path, reactor_tag, event_tag)
    finally:
        shutil.rmtree(str(reactors_dir), ignore_errors=True)


@pytest.fixture(scope="session")
def master_id():
    master_id = random_string("master-")
    yield master_id


@pytest.fixture(scope="session")
def salt_master_factory(
    request,
    salt_factories,
    salt_minion_id,
    salt_sub_minion_id,
    base_env_state_tree_root_dir,
    base_env_pillar_tree_root_dir,
    prod_env_state_tree_root_dir,
    prod_env_pillar_tree_root_dir,
    ext_pillar_file_tree_root_dir,
    sdb_etcd_port,
    vault_port,
    reactor_event,
    master_id,
):
    root_dir = salt_factories.get_root_dir_for_daemon(master_id)
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
    config_defaults["transport"] = request.config.getoption("--transport")
    config_defaults["reactor"] = [
        {reactor_event.tag: [str(reactor_event.sls_path)]},
    ]

    nodegroups = {
        "min": salt_minion_id,
        "sub_min": salt_sub_minion_id,
        "mins": "N@min or N@sub_min",
        "list_nodegroup": [salt_minion_id, salt_sub_minion_id],
        "multiline_nodegroup": [salt_minion_id, "or", salt_sub_minion_id],
        "one_minion_list": [salt_minion_id],
        "redundant_minions": "N@min or N@mins",
        "nodegroup_loop_a": "N@nodegroup_loop_b",
        "nodegroup_loop_b": "N@nodegroup_loop_a",
        "missing_minion": "L@{},ghostminion".format(salt_minion_id),
        "list_group": "N@multiline_nodegroup",
        "one_list_group": "N@one_minion_list",
        "list_group2": "N@list_nodegroup",
    }
    config_defaults["nodegroups"] = nodegroups
    config_defaults["sdbetcd"] = {
        "driver": "etcd",
        "etcd.host": "127.0.0.1",
        "etcd.port": sdb_etcd_port,
    }
    config_defaults["vault"] = {
        "url": "http://127.0.0.1:{}".format(vault_port),
        "auth": {"method": "token", "token": "testsecret", "uses": 0},
        "policies": ["testpolicy"],
    }

    # Config settings to test `event_return`
    config_defaults["returner_dirs"] = []
    config_defaults["returner_dirs"].append(
        os.path.join(RUNTIME_VARS.FILES, "returners")
    )
    config_defaults["event_return"] = "runtests_noop"
    config_overrides = {"pytest-master": {"log": {"level": "DEBUG"}}}
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
                "root_dir": str(ext_pillar_file_tree_root_dir),
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

    factory = salt_factories.salt_master_daemon(
        master_id,
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    return factory


@pytest.fixture(scope="session")
def salt_minion_factory(salt_master_factory, salt_minion_id, sdb_etcd_port, vault_port):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "minion")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = salt_master_factory.config["transport"]
    config_defaults["sdbetcd"] = {
        "driver": "etcd",
        "etcd.host": "127.0.0.1",
        "etcd.port": sdb_etcd_port,
    }
    config_defaults["vault"] = {
        "url": "http://127.0.0.1:{}".format(vault_port),
        "auth": {"method": "token", "token": "testsecret", "uses": 0},
        "policies": ["testpolicy"],
    }

    config_overrides = {
        "file_roots": salt_master_factory.config["file_roots"].copy(),
        "pillar_roots": salt_master_factory.config["pillar_roots"].copy(),
    }

    virtualenv_binary = get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary
    factory = salt_master_factory.salt_minion_daemon(
        salt_minion_id,
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )
    return factory


@pytest.fixture(scope="session")
def salt_sub_minion_factory(salt_master_factory, salt_sub_minion_id):
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
    factory = salt_master_factory.salt_minion_daemon(
        salt_sub_minion_id,
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )
    return factory


@pytest.fixture(scope="session")
def salt_proxy_factory(salt_master_factory):
    proxy_minion_id = random_string("proxytest-")

    config_overrides = {
        "file_roots": salt_master_factory.config["file_roots"].copy(),
        "pillar_roots": salt_master_factory.config["pillar_roots"].copy(),
    }

    factory = salt_master_factory.salt_proxy_minion_daemon(
        proxy_minion_id,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
        start_timeout=240,
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )
    return factory


@pytest.fixture(scope="session")
def salt_delta_proxy_factory(salt_factories, salt_master_factory):
    proxy_minion_id = random_string("proxytest-")
    root_dir = salt_factories.get_root_dir_for_daemon(proxy_minion_id)
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(parents=True, exist_ok=True)

    config_defaults = {
        "root_dir": str(root_dir),
        "hosts.file": os.path.join(
            RUNTIME_VARS.TMP, "hosts"
        ),  # Do we really need this for these tests?
        "aliases.file": os.path.join(
            RUNTIME_VARS.TMP, "aliases"
        ),  # Do we really need this for these tests?
        "transport": salt_master_factory.config["transport"],
        "user": salt_master_factory.config["user"],
        "metaproxy": "deltaproxy",
        "master": "127.0.0.1",
    }
    factory = salt_master_factory.salt_proxy_minion_daemon(
        proxy_minion_id,
        defaults=config_defaults,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
        start_timeout=240,
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )
    return factory


@pytest.fixture
def temp_salt_master(
    request,
    salt_factories,
):
    config_defaults = {
        "open_mode": True,
        "transport": request.config.getoption("--transport"),
    }
    factory = salt_factories.salt_master_daemon(
        random_string("temp-master-"),
        defaults=config_defaults,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    return factory


@pytest.fixture
def temp_salt_minion(temp_salt_master):
    config_defaults = {
        "open_mode": True,
        "transport": temp_salt_master.config["transport"],
    }
    factory = temp_salt_master.salt_minion_daemon(
        random_string("temp-minion-"),
        defaults=config_defaults,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, temp_salt_master, factory.id
    )
    return factory


@pytest.fixture(scope="session")
def bridge_pytest_and_runtests():
    """
    We're basically overriding the same fixture defined in tests/conftest.py
    """


# ----- Async Test Fixtures ----------------------------------------------------------------------------------------->
# This is based on https://github.com/eukaryote/pytest-tornasync
# The reason why we don't use that pytest plugin instead is because it has
# tornado as a dependency, and we need to use the tornado we ship with salt


def get_test_timeout(pyfuncitem):
    default_timeout = 30
    marker = pyfuncitem.get_closest_marker("timeout")
    if marker:
        return marker.kwargs.get("seconds") or default_timeout
    return default_timeout


@pytest.mark.tryfirst
def pytest_pycollect_makeitem(collector, name, obj):
    if collector.funcnamefilter(name) and inspect.iscoroutinefunction(obj):
        return list(collector._genfunctions(name, obj))


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    if inspect.iscoroutinefunction(item.obj):
        if "io_loop" not in item.fixturenames:
            # Append the io_loop fixture for the async functions
            item.fixturenames.append("io_loop")


class CoroTestFunction:
    def __init__(self, func, kwargs):
        self.func = func
        self.kwargs = kwargs
        functools.update_wrapper(self, func)

    async def __call__(self):
        ret = await self.func(**self.kwargs)
        return ret


@pytest.mark.tryfirst
def pytest_pyfunc_call(pyfuncitem):
    if not inspect.iscoroutinefunction(pyfuncitem.obj):
        return

    funcargs = pyfuncitem.funcargs
    testargs = {arg: funcargs[arg] for arg in pyfuncitem._fixtureinfo.argnames}

    try:
        loop = funcargs["io_loop"]
    except KeyError:
        loop = salt.ext.tornado.ioloop.IOLoop.current()

    loop.run_sync(
        CoroTestFunction(pyfuncitem.obj, testargs), timeout=get_test_timeout(pyfuncitem)
    )
    return True


@pytest.fixture
def io_loop():
    """
    Create new io loop for each test, and tear it down after.
    """
    loop = salt.ext.tornado.ioloop.IOLoop()
    loop.make_current()
    try:
        yield loop
    finally:
        loop.clear_current()
        loop.close(all_fds=True)


# <---- Async Test Fixtures ------------------------------------------------------------------------------------------
