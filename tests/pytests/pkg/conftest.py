import logging
import os
import pathlib
import shutil
import subprocess
import sys

import pytest
import yaml
from pytestskipmarkers.utils import platform
from saltfactories.utils import random_string

import salt.config
import salt.utils.files
from tests.conftest import CODE_DIR, FIPS_TESTRUN
from tests.support.pkg import ApiRequest, SaltMaster, SaltMasterWindows, SaltPkgInstall

log = logging.getLogger(__name__)

# Variable defining a FIPS test run or not
FIPS_TESTRUN = os.environ.get("FIPS_TESTRUN", "0") == "1"


@pytest.fixture(scope="session")
def version(install_salt):
    """
    get version number from artifact
    """
    return install_salt.version


@pytest.fixture(scope="session", autouse=True)
def _system_up_to_date(
    grains,
    shell,
):
    if grains["os_family"] == "Debian":
        ret = shell.run("apt", "update")
        assert ret.returncode == 0
        env = os.environ.copy()
        env["DEBIAN_FRONTEND"] = "noninteractive"
        ret = shell.run(
            "apt",
            "upgrade",
            "-y",
            "-o",
            "DPkg::Options::=--force-confdef",
            "-o",
            "DPkg::Options::=--force-confold",
            env=env,
        )
        assert ret.returncode == 0
    elif grains["os_family"] == "Redhat":
        ret = shell.run("yum", "update", "-y")
        assert ret.returncode == 0


def pytest_addoption(parser):
    """
    register argparse-style options and ini-style config values.
    """
    test_selection_group = parser.getgroup("Tests Runtime Selection")
    test_selection_group.addoption(
        "--pkg-system-service",
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
        "--downgrade",
        default=False,
        action="store_true",
        help="Install current version and then downgrade to the previous version and run tests",
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
        "--prev-version",
        action="store",
        help="Test an upgrade from the version specified.",
    )
    test_selection_group.addoption(
        "--use-prev-version",
        action="store_true",
        help="Tells the test suite to validate the version using the previous version (for downgrades)",
    )
    test_selection_group.addoption(
        "--download-pkgs",
        default=False,
        action="store_true",
        help="Test package download tests",
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
    selected = []
    deselected = []
    pkg_tests_path = pathlib.Path(__file__).parent

    if config.getoption("--upgrade"):
        for item in items:
            if str(item.fspath).startswith(str(pkg_tests_path / "upgrade")):
                selected.append(item)
            else:
                deselected.append(item)
    elif config.getoption("--downgrade"):
        for item in items:
            if str(item.fspath).startswith(str(pkg_tests_path / "downgrade")):
                selected.append(item)
            else:
                deselected.append(item)
    elif config.getoption("--download-pkgs"):
        for item in items:
            if str(item.fspath).startswith(str(pkg_tests_path / "download")):
                selected.append(item)
            else:
                deselected.append(item)
    else:
        exclude_paths = (
            str(pkg_tests_path / "upgrade"),
            str(pkg_tests_path / "downgrade"),
            str(pkg_tests_path / "download"),
        )
        for item in items:
            if str(item.fspath).startswith(exclude_paths):
                deselected.append(item)
            else:
                selected.append(item)

    if deselected:
        # Selection changed
        items[:] = selected
        config.hook.pytest_deselected(items=deselected)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """
    Fixtures injection based on markers or test skips based on CLI arguments
    """
    pkg_tests_path = pathlib.Path(__file__).parent
    if (
        str(item.fspath).startswith(str(pkg_tests_path / "download"))
        and item.config.getoption("--download-pkgs") is False
    ):
        raise pytest.skip.Exception(
            "The package download tests are disabled. Pass '--download-pkgs' to pytest "
            "to enable them.",
            _use_item_location=True,
        )

    for key in ("upgrade", "downgrade"):
        if (
            str(item.fspath).startswith(str(pkg_tests_path / key))
            and item.config.getoption(f"--{key}") is False
        ):
            raise pytest.skip.Exception(
                f"The package {key} tests are disabled. Pass '--{key}' to pytest "
                "to enable them.",
                _use_item_location=True,
            )


@pytest.fixture(scope="session")
def salt_factories_root_dir(request, tmp_path_factory):
    root_dir = SaltPkgInstall.salt_factories_root_dir(
        request.config.getoption("--pkg-system-service")
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
        "system_service": True,
    }


@pytest.fixture(scope="session")
def install_salt(request, salt_factories_root_dir):
    with SaltPkgInstall(
        conf_dir=salt_factories_root_dir / "etc" / "salt",
        pkg_system_service=request.config.getoption("--pkg-system-service"),
        upgrade=request.config.getoption("--upgrade"),
        downgrade=request.config.getoption("--downgrade"),
        no_uninstall=request.config.getoption("--no-uninstall"),
        no_install=request.config.getoption("--no-install"),
        prev_version=request.config.getoption("--prev-version"),
        use_prev_version=request.config.getoption("--use-prev-version"),
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session")
def salt_factories(salt_factories, salt_factories_root_dir):
    salt_factories.root_dir = salt_factories_root_dir
    return salt_factories


@pytest.fixture(scope="session")
def salt_master(salt_factories, install_salt, pkg_tests_account):
    """
    Start up a master
    """
    if platform.is_windows():
        state_tree = "C:/salt/srv/salt"
        pillar_tree = "C:/salt/srv/pillar"
    elif platform.is_darwin():
        state_tree = "/opt/srv/salt"
        pillar_tree = "/opt/srv/pillar"
    else:
        state_tree = "/srv/salt"
        pillar_tree = "/srv/pillar"

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
        "file_roots": {
            "base": [
                state_tree,
            ]
        },
        "pillar_roots": {
            "base": [
                pillar_tree,
            ]
        },
        "rest_cherrypy": {
            "port": 8000,
            "disable_ssl": True,
        },
        "netapi_enable_clients": ["local"],
        "external_auth": {
            "auto": {
                pkg_tests_account.username: [
                    ".*",
                ],
            },
        },
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
        "open_mode": True,
    }
    salt_user_in_config_file = False
    master_config = install_salt.config_path / "master"
    if master_config.exists() and master_config.stat().st_size:
        with salt.utils.files.fopen(master_config) as fp:
            data = yaml.safe_load(fp)
            if data is None:
                # File exists but is mostly commented out
                data = {}
            user_in_config_file = data.get("user")
            if user_in_config_file and user_in_config_file == "salt":
                salt_user_in_config_file = True
                # We are testing a different user, so we need to test the system
                # configs, or else permissions will not be correct.
                config_overrides["user"] = user_in_config_file
                config_overrides["log_file"] = salt.config.DEFAULT_MASTER_OPTS.get(
                    "log_file"
                )
                config_overrides["root_dir"] = salt.config.DEFAULT_MASTER_OPTS.get(
                    "root_dir"
                )
                config_overrides["key_logfile"] = salt.config.DEFAULT_MASTER_OPTS.get(
                    "key_logfile"
                )
                config_overrides["pki_dir"] = salt.config.DEFAULT_MASTER_OPTS.get(
                    "pki_dir"
                )
                config_overrides["api_logfile"] = salt.config.DEFAULT_API_OPTS.get(
                    "api_logfile"
                )
                config_overrides["api_pidfile"] = salt.config.DEFAULT_API_OPTS.get(
                    "api_pidfile"
                )
                # verify files were set with correct owner/group
                verify_files = [
                    pathlib.Path("/etc", "salt", "pki", "master"),
                    pathlib.Path("/etc", "salt", "master.d"),
                    pathlib.Path("/var", "cache", "salt", "master"),
                ]
                for _file in verify_files:
                    if _file.owner() != "salt":
                        log.warning(
                            "The owner of '%s' is '%s' when it should be 'salt'",
                            _file,
                            _file.owner(),
                        )
                    if _file.group() != "salt":
                        log.warning(
                            "The group of '%s' is '%s' when it should be 'salt'",
                            _file,
                            _file.group(),
                        )

    master_script = False
    if platform.is_windows():
        master_script = True

    if master_script:
        salt_factories.system_service = False
        salt_factories.generate_scripts = True
        scripts_dir = salt_factories.root_dir / "Scripts"
        scripts_dir.mkdir(exist_ok=True)
        salt_factories.scripts_dir = scripts_dir
        python_executable = install_salt.install_dir / "Scripts" / "python.exe"
        salt_factories.python_executable = python_executable
        factory = salt_factories.salt_master_daemon(
            random_string("master-"),
            defaults=config_defaults,
            overrides=config_overrides,
            factory_class=SaltMasterWindows,
            salt_pkg_install=install_salt,
        )
        salt_factories.system_service = True
    else:
        factory = salt_factories.salt_master_daemon(
            random_string("master-"),
            defaults=config_defaults,
            overrides=config_overrides,
            factory_class=SaltMaster,
            salt_pkg_install=install_salt,
        )
    factory.after_terminate(pytest.helpers.remove_stale_master_key, factory)
    if salt_user_in_config_file:
        # Salt factories calls salt.utils.verify.verify_env
        # which sets root perms on /etc/salt/pki/master since we are running
        # the test suite as root, but we want to run Salt master as salt
        # We ensure those permissions where set by the package earlier
        subprocess.run(
            [
                "chown",
                "-R",
                "salt:salt",
                str(pathlib.Path("/etc", "salt", "pki", "master")),
            ],
            check=True,
        )

        if not platform.is_windows() and not platform.is_darwin():
            # The engines_dirs is created in .nox path. We need to set correct perms
            # for the user running the Salt Master
            check_paths = [state_tree, pillar_tree, CODE_DIR / ".nox"]
            for path in check_paths:
                if os.path.exists(path) is False:
                    continue
                subprocess.run(["chown", "-R", "salt:salt", str(path)], check=False)

    with factory.started(start_timeout=start_timeout):
        yield factory


@pytest.fixture(scope="session")
def salt_minion(salt_factories, salt_master, install_salt):
    """
    Start up a minion
    """
    start_timeout = None
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
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        "open_mode": True,
    }
    if platform.is_windows():
        config_overrides["winrepo_dir"] = (
            rf"{salt_factories.root_dir}\srv\salt\win\repo"
        )
        config_overrides["winrepo_dir_ng"] = (
            rf"{salt_factories.root_dir}\srv\salt\win\repo_ng"
        )
        config_overrides["winrepo_source_dir"] = r"salt://win/repo_ng"

    factory = salt_master.salt_minion_daemon(
        minion_id,
        overrides=config_overrides,
        defaults=config_defaults,
    )

    # Salt factories calls salt.utils.verify.verify_env
    # which sets root perms on /srv/salt and /srv/pillar since we are running
    # the test suite as root, but we want to run Salt master as salt
    if not platform.is_windows() and not platform.is_darwin():
        import pwd

        try:
            pwd.getpwnam("salt")
        except KeyError:
            # The salt user does not exist
            pass
        else:
            state_tree = "/srv/salt"
            pillar_tree = "/srv/pillar"
            check_paths = [state_tree, pillar_tree, CODE_DIR / ".nox"]
            for path in check_paths:
                if os.path.exists(path) is False:
                    continue
                subprocess.run(["chown", "-R", "salt:salt", str(path)], check=False)

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


@pytest.fixture(scope="session")
def pkg_tests_account():
    with pytest.helpers.create_account() as account:
        yield account


@pytest.fixture(scope="module")
def extras_pypath():
    extras_dir = "extras-{}.{}".format(*sys.version_info)
    if platform.is_windows():
        return pathlib.Path(
            os.getenv("ProgramFiles"), "Salt Project", "Salt", extras_dir
        )
    elif platform.is_darwin():
        return pathlib.Path("/opt", "salt", extras_dir)
    else:
        return pathlib.Path("/opt", "saltstack", "salt", extras_dir)


@pytest.fixture(scope="module")
def extras_pypath_bin(extras_pypath):
    return extras_pypath / "bin"


@pytest.fixture(scope="module")
def salt_api(salt_master, install_salt, extras_pypath):
    """
    start up and configure salt_api
    """
    shutil.rmtree(str(extras_pypath), ignore_errors=True)
    start_timeout = None
    factory = salt_master.salt_api_daemon()
    with factory.started(start_timeout=start_timeout):
        yield factory


@pytest.fixture(scope="module")
def api_request(pkg_tests_account, salt_api):
    with ApiRequest(
        port=salt_api.config["rest_cherrypy"]["port"], account=pkg_tests_account
    ) as session:
        yield session
