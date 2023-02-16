import logging
import pathlib
import re
import shutil

import pytest
from pytestskipmarkers.utils import platform
from saltfactories.utils import cli_scripts, random_string
from saltfactories.utils.tempfiles import SaltPillarTree, SaltStateTree

from tests.support.helpers import (
    ARTIFACTS_DIR,
    CODE_DIR,
    TESTS_DIR,
    ApiRequest,
    SaltMaster,
    SaltMasterWindows,
    SaltPkgInstall,
    TestUser,
)

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def version(install_salt):
    """
    get version number from artifact
    """
    return install_salt.get_version(version_only=True)


def pytest_addoption(parser):
    """
    register argparse-style options and ini-style config values.
    """
    test_selection_group = parser.getgroup("Tests Runtime Selection")
    test_selection_group.addoption(
        "--system-service",
        default=False,
        action="store_true",
        help="Run the daemons as system services",
    )
    test_selection_group.addoption(
        "--upgrade",
        default=False,
        action="store_true",
        help="Install previous version and then upgrade then run tests",
    )
    test_selection_group.addoption(
        "--no-install",
        default=False,
        action="store_true",
        help="Do not install salt and use a previous install Salt package",
    )
    test_selection_group.addoption(
        "--no-uninstall",
        default=False,
        action="store_true",
        help="Do not uninstall salt packages after test run is complete",
    )
    test_selection_group.addoption(
        "--classic",
        default=False,
        action="store_true",
        help="Test an upgrade from the classic packages.",
    )
    test_selection_group.addoption(
        "--prev-version",
        action="store",
        help="Test an upgrade from the version specified.",
    )


@pytest.fixture(scope="session")
def salt_factories_root_dir(request, tmp_path_factory):
    root_dir = SaltPkgInstall.salt_factories_root_dir(
        request.config.getoption("--system-service")
    )
    if root_dir is not None:
        yield root_dir
    else:
        if platform.is_darwin():
            root_dir = pathlib.Path("/tmp/salt-tests-tmpdir")
            root_dir.mkdir(mode=0o777, parents=True, exist_ok=True)
        else:
            root_dir = tmp_path_factory.mktemp("salt-tests")
        try:
            yield root_dir
        finally:
            shutil.rmtree(str(root_dir), ignore_errors=True)


@pytest.fixture(scope="session")
def salt_factories_config(salt_factories_root_dir):
    return {
        "code_dir": CODE_DIR,
        "root_dir": salt_factories_root_dir,
        "system_install": True,
    }


@pytest.fixture(scope="session")
def install_salt(request, salt_factories_root_dir):
    with SaltPkgInstall(
        conf_dir=salt_factories_root_dir / "etc" / "salt",
        system_service=request.config.getoption("--system-service"),
        upgrade=request.config.getoption("--upgrade"),
        no_uninstall=request.config.getoption("--no-uninstall"),
        no_install=request.config.getoption("--no-install"),
        classic=request.config.getoption("--classic"),
        prev_version=request.config.getoption("--prev-version"),
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session")
def salt_factories(salt_factories, salt_factories_root_dir):
    salt_factories.root_dir = salt_factories_root_dir
    return salt_factories


@pytest.fixture(scope="session")
def state_tree():
    if platform.is_windows():
        file_root = pathlib.Path("C:/salt/srv/salt")
    elif platform.is_darwin():
        file_root = pathlib.Path("/opt/srv/salt")
    else:
        file_root = pathlib.Path("/srv/salt")
    envs = {
        "base": [
            str(file_root),
            str(TESTS_DIR / "files"),
        ],
    }
    tree = SaltStateTree(envs=envs)
    test_sls_contents = """
    test_foo:
      test.succeed_with_changes:
          - name: foo
    """
    states_sls_contents = """
    update:
      pkg.installed:
        - name: bash
    salt_dude:
      user.present:
        - name: dude
        - fullname: Salt Dude
    """
    win_states_sls_contents = """
    create_empty_file:
      file.managed:
        - name: C://salt/test/txt
    salt_dude:
      user.present:
        - name: dude
        - fullname: Salt Dude
    """
    with tree.base.temp_file("test.sls", test_sls_contents), tree.base.temp_file(
        "states.sls", states_sls_contents
    ), tree.base.temp_file("win_states.sls", win_states_sls_contents):
        yield tree


@pytest.fixture(scope="session")
def pillar_tree():
    """
    Add pillar files
    """
    if platform.is_windows():
        pillar_root = pathlib.Path("C:/salt/srv/pillar")
    elif platform.is_darwin():
        pillar_root = pathlib.Path("/opt/srv/pillar")
    else:
        pillar_root = pathlib.Path("/srv/pillar")
    pillar_root.mkdir(mode=0o777, parents=True, exist_ok=True)
    tree = SaltPillarTree(
        envs={
            "base": [
                str(pillar_root),
            ]
        },
    )
    top_file_contents = """
    base:
      '*':
        - test
    """
    test_file_contents = """
    info: test
    """
    with tree.base.temp_file("top.sls", top_file_contents), tree.base.temp_file(
        "test.sls", test_file_contents
    ):
        yield tree


@pytest.fixture(scope="module")
def sls(state_tree):
    """
    Add an sls file
    """
    test_sls_contents = """
    test_foo:
      test.succeed_with_changes:
          - name: foo
    """
    states_sls_contents = """
    update:
      pkg.installed:
        - name: bash
    salt_dude:
      user.present:
        - name: dude
        - fullname: Salt Dude
    """
    win_states_sls_contents = """
    create_empty_file:
      file.managed:
        - name: C://salt/test/txt
    salt_dude:
      user.present:
        - name: dude
        - fullname: Salt Dude
    """
    with state_tree.base.temp_file(
        "tests.sls", test_sls_contents
    ), state_tree.base.temp_file(
        "states.sls", states_sls_contents
    ), state_tree.base.temp_file(
        "win_states.sls", win_states_sls_contents
    ):
        yield


@pytest.fixture(scope="session")
def salt_master(salt_factories, install_salt, state_tree, pillar_tree):
    """
    Start up a master
    """
    start_timeout = None
    # Since the daemons are "packaged" with tiamat, the salt plugins provided
    # by salt-factories won't be discovered. Provide the required `*_dirs` on
    # the configuration so that they can still be used.
    config_defaults = {
        "engines_dirs": [
            str(salt_factories.get_salt_engines_path()),
        ],
        "log_handlers_dirs": [
            str(salt_factories.get_salt_log_handlers_path()),
        ],
    }
    if platform.is_darwin():
        config_defaults["enable_fqdns_grains"] = False
    config_overrides = {
        "timeout": 30,
        "file_roots": state_tree.as_dict(),
        "pillar_roots": pillar_tree.as_dict(),
        "rest_cherrypy": {"port": 8000, "disable_ssl": True},
        "netapi_enable_clients": ["local"],
        "external_auth": {"auto": {"saltdev": [".*"]}},
    }
    if (platform.is_windows() or platform.is_darwin()) and install_salt.singlebin:
        start_timeout = 240
        # For every minion started we have to accept it's key.
        # On windows, using single binary, it has to decompress it and run the command. Too slow.
        # So, just in this scenario, use open mode
        config_overrides["open_mode"] = True
    master_script = False
    if platform.is_windows():
        if install_salt.classic:
            master_script = True
        # this check will need to be changed to install_salt.relenv
        # once the package version returns 3006 and not 3005 on master
        elif not install_salt.upgrade:
            master_script = True

    if master_script:
        salt_factories.system_install = False
        scripts_dir = salt_factories.root_dir / "Scripts"
        scripts_dir.mkdir(exist_ok=True)
        salt_factories.scripts_dir = scripts_dir
        config_overrides["open_mode"] = True
        python_executable = install_salt.bin_dir / "Scripts" / "python.exe"
        if install_salt.classic:
            python_executable = install_salt.bin_dir / "python.exe"
        factory = salt_factories.salt_master_daemon(
            random_string("master-"),
            defaults=config_defaults,
            overrides=config_overrides,
            factory_class=SaltMasterWindows,
            salt_pkg_install=install_salt,
            python_executable=python_executable,
        )
        salt_factories.system_install = True
    else:
        factory = salt_factories.salt_master_daemon(
            random_string("master-"),
            defaults=config_defaults,
            overrides=config_overrides,
            factory_class=SaltMaster,
            salt_pkg_install=install_salt,
        )
    factory.after_terminate(pytest.helpers.remove_stale_master_key, factory)
    with factory.started(start_timeout=start_timeout):
        yield factory


@pytest.fixture(scope="session")
def salt_minion(salt_factories, salt_master, install_salt):
    """
    Start up a minion
    """
    start_timeout = None
    if (platform.is_windows() or platform.is_darwin()) and install_salt.singlebin:
        start_timeout = 240
    minion_id = random_string("minion-")
    # Since the daemons are "packaged" with tiamat, the salt plugins provided
    # by salt-factories won't be discovered. Provide the required `*_dirs` on
    # the configuration so that they can still be used.
    config_defaults = {
        "engines_dirs": salt_master.config["engines_dirs"].copy(),
        "log_handlers_dirs": salt_master.config["log_handlers_dirs"].copy(),
    }
    if platform.is_darwin():
        config_defaults["enable_fqdns_grains"] = False
    config_overrides = {
        "id": minion_id,
        "file_roots": salt_master.config["file_roots"].copy(),
        "pillar_roots": salt_master.config["pillar_roots"].copy(),
    }
    if platform.is_windows():
        config_overrides[
            "winrepo_dir"
        ] = rf"{salt_factories.root_dir}\srv\salt\win\repo"
        config_overrides[
            "winrepo_dir_ng"
        ] = rf"{salt_factories.root_dir}\srv\salt\win\repo_ng"
        config_overrides["winrepo_source_dir"] = r"salt://win/repo_ng"
    factory = salt_master.salt_minion_daemon(
        minion_id,
        overrides=config_overrides,
        defaults=config_defaults,
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    with factory.started(start_timeout=start_timeout):
        yield factory


@pytest.fixture(scope="module")
def salt_cli(salt_master):
    return salt_master.salt_cli()


@pytest.fixture(scope="module")
def salt_key_cli(salt_master):
    return salt_master.salt_key_cli()


@pytest.fixture(scope="module")
def salt_call_cli(salt_minion):
    return salt_minion.salt_call_cli()


@pytest.fixture(scope="module")
def test_account(salt_call_cli):
    with TestUser(salt_call_cli=salt_call_cli) as account:
        yield account


@pytest.fixture(scope="module")
def salt_api(salt_master, install_salt):
    """
    start up and configure salt_api
    """
    start_timeout = None
    if platform.is_windows() and install_salt.singlebin:
        start_timeout = 240
    factory = salt_master.salt_api_daemon()
    with factory.started(start_timeout=start_timeout):
        yield factory


@pytest.fixture(scope="module")
def api_request(test_account, salt_api):
    with ApiRequest(salt_api=salt_api, test_account=test_account) as session:
        yield session
