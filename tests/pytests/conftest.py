"""
    tests.pytests.conftest
    ~~~~~~~~~~~~~~~~~~~~~~
"""

import asyncio
import functools
import inspect
import logging
import os
import pathlib
import shutil
import ssl
import stat
import sys
import tempfile
import types

import attr
import pytest
import tornado.ioloop
from pytestshellutils.utils import ports
from saltfactories.utils import random_string

import salt.utils.files
import salt.utils.platform
from salt.serializers import yaml
from tests.conftest import FIPS_TESTRUN
from tests.support.helpers import Webserver, get_virtualenv_binary_path
from tests.support.pytest.helpers import TestAccount
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def salt_auth_account_1_factory():
    return TestAccount(username="saltdev-auth-1")


@pytest.fixture(scope="session")
def salt_auth_account_2_factory():
    return TestAccount(username="saltdev-auth-2", group_name="saltops")


@pytest.fixture(scope="session")
def salt_netapi_account_factory():
    return TestAccount(username="saltdev-netapi")


@pytest.fixture(scope="session")
def salt_eauth_account_factory():
    return TestAccount(username="saltdev-eauth")


@pytest.fixture(scope="session")
def salt_auto_account_factory():
    return TestAccount(username="saltdev_auto", password="saltdev")


@pytest.fixture(scope="session")
def salt_minion_id():
    return random_string("minion-")


@pytest.fixture(scope="session")
def salt_sub_minion_id():
    return random_string("sub-minion-")


@pytest.fixture(scope="session")
def sdb_etcd_port():
    return ports.get_unused_localhost_port()


@pytest.fixture(scope="session")
def vault_port():
    return ports.get_unused_localhost_port()


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
    salt_auth_account_1_factory,
    salt_auth_account_2_factory,
    salt_netapi_account_factory,
    salt_eauth_account_factory,
    salt_auto_account_factory,
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
        "missing_minion": f"L@{salt_minion_id},ghostminion",
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
        "url": f"http://127.0.0.1:{vault_port}",
        "auth": {"method": "token", "token": "testsecret", "uses": 0},
        "policies": ["testpolicy"],
    }

    # Config settings to test `event_return`
    config_defaults["returner_dirs"] = []
    config_defaults["returner_dirs"].append(
        os.path.join(RUNTIME_VARS.FILES, "returners")
    )
    config_defaults["event_return"] = "runtests_noop"
    config_overrides = {
        "pytest-master": {"log": {"level": "DEBUG"}},
        "fips_mode": FIPS_TESTRUN,
    }
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
    config_overrides["external_auth"] = {
        "pam": {
            salt_auth_account_1_factory.username: ["test.*"],
            f"{salt_auth_account_2_factory.group_name}%": [
                "@wheel",
                "@runner",
                "test.*",
            ],
            salt_netapi_account_factory.username: ["@wheel", "@runner", "test.*"],
            salt_eauth_account_factory.username: ["@wheel", "@runner", "test.*"],
        },
        "auto": {
            salt_netapi_account_factory.username: [
                "@wheel",
                "@runner",
                "test.*",
                "grains.*",
            ],
            salt_auto_account_factory.username: ["@wheel", "@runner", "test.*"],
            "*": ["@wheel", "@runner", "test.*"],
        },
    }

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
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
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
        "url": f"http://127.0.0.1:{vault_port}",
        "auth": {"method": "token", "token": "testsecret", "uses": 0},
        "policies": ["testpolicy"],
    }

    config_overrides = {
        "file_roots": salt_master_factory.config["file_roots"].copy(),
        "pillar_roots": salt_master_factory.config["pillar_roots"].copy(),
        "fips_mode": FIPS_TESTRUN,
    }

    virtualenv_binary = get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary
    factory = salt_master_factory.salt_minion_daemon(
        salt_minion_id,
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
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
        "fips_mode": FIPS_TESTRUN,
    }

    virtualenv_binary = get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary
    factory = salt_master_factory.salt_minion_daemon(
        salt_sub_minion_id,
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
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
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
        start_timeout=240,
    )
    factory.before_start(pytest.helpers.remove_stale_proxy_minion_cache_file, factory)
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_proxy_minion_cache_file, factory
    )
    return factory


@pytest.fixture(scope="session")
def salt_delta_proxy_factory(salt_factories, salt_master_factory):
    proxy_minion_id = random_string("delta-proxy-test-")
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
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
        start_timeout=240,
    )

    for minion_id in [factory.id] + pytest.helpers.proxy.delta_proxy_minion_ids():
        factory.before_start(
            pytest.helpers.remove_stale_proxy_minion_cache_file, factory, minion_id
        )
        factory.after_terminate(
            pytest.helpers.remove_stale_minion_key, salt_master_factory, minion_id
        )
        factory.after_terminate(
            pytest.helpers.remove_stale_proxy_minion_cache_file, factory, minion_id
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
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
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
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, temp_salt_master, factory.id
    )
    return factory


@pytest.fixture(scope="session")
def get_python_executable():
    """
    Return the path to the python executable.

    This is particularly important when running the test suite within a virtualenv, while trying
    to create virtualenvs on windows.
    """
    try:
        if salt.utils.platform.is_windows():
            python_binary = os.path.join(
                sys.real_prefix, os.path.basename(sys.executable)
            )
        else:
            python_binary = os.path.join(
                sys.real_prefix, "bin", os.path.basename(sys.executable)
            )
            if not os.path.exists(python_binary):
                if not python_binary[-1].isdigit():
                    versioned_python_binary = "{}{}".format(
                        python_binary, *sys.version_info
                    )
                    log.info(
                        "Python binary could not be found at %s. Trying %s",
                        python_binary,
                        versioned_python_binary,
                    )
                    if os.path.exists(versioned_python_binary):
                        python_binary = versioned_python_binary
        if not os.path.exists(python_binary):
            log.warning("Python binary could not be found at %s", python_binary)
            python_binary = None
    except AttributeError:
        # We're not running inside a virtualenv
        python_binary = sys.executable
    return python_binary


@pytest.fixture
def tmp_path_world_rw(request):
    """
    Temporary path which is world read/write for tests that run under a different account
    """
    tempdir_path = pathlib.Path(basetemp=tempfile.gettempdir()).resolve()
    path = tempdir_path / f"world-rw-{id(request.node)}"
    path.mkdir(exist_ok=True)
    path.chmod(0o777)
    try:
        yield path
    finally:
        shutil.rmtree(str(path), ignore_errors=True)


@pytest.fixture(scope="session")
def bridge_pytest_and_runtests():
    """
    We're basically overriding the same fixture defined in tests/conftest.py
    """


@pytest.fixture(scope="session")
def this_txt_file(integration_files_dir):
    contents = "test"
    with pytest.helpers.temp_file("this.txt", contents, integration_files_dir) as path:
        sha256sum = salt.utils.hashutils.get_hash(str(path), form="sha256")
        with pytest.helpers.temp_file(
            "this.txt.sha256", sha256sum, integration_files_dir
        ):
            yield types.SimpleNamespace(name="this.txt", path=path, sha256=sha256sum)


@pytest.fixture(scope="module")
def ssl_webserver(integration_files_dir, this_txt_file):
    """
    spins up an https webserver.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(
        str(integration_files_dir / "https" / "cert.pem"),
        str(integration_files_dir / "https" / "key.pem"),
    )

    with Webserver(root=str(integration_files_dir), ssl_opts=context) as webserver:
        yield webserver


@pytest.fixture(scope="module")
def webserver(integration_files_dir, this_txt_file):
    """
    spins up an http webserver.
    """
    with Webserver(root=str(integration_files_dir)) as webserver:
        yield webserver


# ----- Async Test Fixtures ----------------------------------------------------------------------------------------->
# This is based on https://github.com/eukaryote/pytest-tornasync
# The reason why we don't use that pytest plugin instead is because it has
# tornado as a dependency, and we need to use the tornado we ship with salt


def get_test_timeout(pyfuncitem):
    default_timeout = 30
    marker = pyfuncitem.get_closest_marker("async_timeout")
    if marker:
        if marker.args:
            raise pytest.UsageError(
                "The 'async_timeout' marker does not accept any arguments "
                "only 'seconds' as a keyword argument"
            )
        return marker.kwargs.get("seconds") or default_timeout
    return default_timeout


@pytest.hookimpl(tryfirst=True)
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


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    if not inspect.iscoroutinefunction(pyfuncitem.obj):
        return

    funcargs = pyfuncitem.funcargs
    testargs = {arg: funcargs[arg] for arg in pyfuncitem._fixtureinfo.argnames}

    try:
        loop = funcargs["io_loop"]
    except KeyError:
        loop = tornado.ioloop.IOLoop.current()

    __tracebackhide__ = True

    loop.asyncio_loop.run_until_complete(
        asyncio.wait_for(
            CoroTestFunction(pyfuncitem.obj, testargs)(),
            timeout=get_test_timeout(pyfuncitem),
        )
    )
    return True


@pytest.fixture
def io_loop():
    """
    Create new io loop for each test, and tear it down after.
    """
    asyncio_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(asyncio_loop)
    loop = tornado.ioloop.IOLoop.current()
    try:
        yield loop
    finally:
        loop.close(all_fds=True)  # Also closes asyncio_loop
        asyncio.set_event_loop(None)


# <---- Async Test Fixtures ------------------------------------------------------------------------------------------


# ----- Helpers ----------------------------------------------------------------------------------------------------->
@pytest.helpers.proxy.register
def delta_proxy_minion_ids():
    return [
        "dummy_proxy_one",
        "dummy_proxy_two",
        "dummy_proxy_three",
        "dummy_proxy_four",
    ]


# <---- Helpers ------------------------------------------------------------------------------------------------------
