"""
Fixtures for upgrade tests.
"""

import logging
import os
import pathlib
import shutil
import subprocess
import textwrap

import packaging.version
import pytest
import yaml
from pytestskipmarkers.utils import platform
from saltfactories.utils import random_string

import salt.config
import salt.utils.files
from tests.conftest import CODE_DIR, FIPS_TESTRUN
from tests.support.pkg import SaltMaster, SaltMasterWindows, SaltPkgInstall

log = logging.getLogger(__name__)


@pytest.fixture
def install_salt_systemd(request, salt_factories_root_dir):
    if platform.is_windows():
        conf_dir = "c:/salt/etc/salt"
    else:
        conf_dir = salt_factories_root_dir / "etc" / "salt"
    with SaltPkgInstall(
        conf_dir=conf_dir,
        pkg_system_service=request.config.getoption("--pkg-system-service"),
        upgrade=request.config.getoption("--upgrade"),
        downgrade=request.config.getoption("--downgrade"),
        no_uninstall=False,
        no_install=request.config.getoption("--no-install"),
        prev_version=request.config.getoption("--prev-version"),
        use_prev_version=request.config.getoption("--use-prev-version"),
    ) as fixture:
        # XXX Force un-install for now
        fixture.no_uninstall = False
        yield fixture


@pytest.fixture
def salt_factories_systemd(salt_factories, salt_factories_root_dir):
    salt_factories.root_dir = salt_factories_root_dir
    return salt_factories


@pytest.fixture
def master_systemd(salt_factories_systemd, install_salt_systemd, pkg_tests_account):
    """
    Start up a master
    """
    if platform.is_windows():
        state_tree = r"C:\salt\srv\salt"
        pillar_tree = r"C:\salt\srv\pillar"
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
            str(salt_factories_systemd.get_salt_engines_path()),
        ],
        "log_handlers_dirs": [
            str(salt_factories_systemd.get_salt_log_handlers_path()),
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
    master_config = install_salt_systemd.config_path / "master"
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
        salt_factories_systemd.system_service = False
        salt_factories_systemd.generate_scripts = True
        scripts_dir = salt_factories_systemd.root_dir / "Scripts"
        scripts_dir.mkdir(exist_ok=True)
        salt_factories_systemd.scripts_dir = scripts_dir
        python_executable = install_salt_systemd.install_dir / "Scripts" / "python.exe"
        salt_factories_systemd.python_executable = python_executable
        factory = salt_factories_systemd.salt_master_daemon(
            "pkg-test-master",
            defaults=config_defaults,
            overrides=config_overrides,
            factory_class=SaltMasterWindows,
            salt_pkg_install=install_salt_systemd,
        )
        salt_factories_systemd.system_service = True
    else:
        factory = salt_factories_systemd.salt_master_daemon(
            "pkg-test-master",
            defaults=config_defaults,
            overrides=config_overrides,
            factory_class=SaltMaster,
            salt_pkg_install=install_salt_systemd,
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


@pytest.fixture
def minion_systemd(salt_factories_systemd, master_systemd, install_salt_systemd):
    """
    Start up a minion
    """
    start_timeout = None
    minion_id = random_string("minion-")
    # Since the daemons are "packaged" with tiamat, the salt plugins provided
    # by salt-factories won't be discovered. Provide the required `*_dirs` on
    # the configuration so that they can still be used.
    config_defaults = {
        "engines_dirs": master_systemd.config["engines_dirs"].copy(),
        "log_handlers_dirs": master_systemd.config["log_handlers_dirs"].copy(),
    }
    if platform.is_darwin():
        config_defaults["enable_fqdns_grains"] = False
    config_overrides = {
        "id": minion_id,
        "file_roots": master_systemd.config["file_roots"].copy(),
        "pillar_roots": master_systemd.config["pillar_roots"].copy(),
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    if platform.is_windows():
        config_overrides["winrepo_dir"] = (
            rf"{salt_factories_systemd.root_dir}\srv\salt\win\repo"
        )
        config_overrides["winrepo_dir_ng"] = (
            rf"{salt_factories_systemd.root_dir}\srv\salt\win\repo_ng"
        )
        config_overrides["winrepo_source_dir"] = r"salt://win/repo_ng"

    factory = master_systemd.salt_minion_daemon(
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

    if platform.is_windows():
        minion_pki = pathlib.Path("c:/salt/etc/salt/pki")
        if minion_pki.exists():
            salt.utils.files.rm_rf(minion_pki)

        # Work around missing WMIC until 3008.10 has been released. Not sure
        # why this doesn't work anymore on the master branch when it was enough
        # on 3006.x and 3007.x. We had to add similar logic in
        # tests/support/pkg.py to fix the upgrade/downgrade tests on master.
        grainsdir = pathlib.Path("c:/salt/etc/grains")
        grainsdir.mkdir(exist_ok=True)
        shutil.copy(r"salt\grains\disks.py", grainsdir)

        grainsdir = pathlib.Path(
            r"C:\Program Files\Salt Project\Salt\Lib\site-packages\salt\grains"
        )
        shutil.copy(r"salt\grains\disks.py", grainsdir)

    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, master_systemd, factory.id
    )
    with factory.started(start_timeout=start_timeout):
        yield factory


@pytest.fixture
def call_cli(minion_systemd):
    return minion_systemd.salt_call_cli()


@pytest.fixture
def salt_systemd_overrides():
    """
    Fixture to create systemd overrides for salt-api, salt-minion, and
    salt-master services.

    This is required because the pytest-salt-factories engine does not
    stop cleanly if you only kill the process. This leaves the systemd
    service in a failed state.
    """

    systemd_dir = pathlib.Path("/etc/systemd/system")
    conf_name = "override.conf"
    contents = textwrap.dedent(
        """
        [Service]
        KillMode=control-group
        TimeoutStopSec=10
        SuccessExitStatus=SIGKILL
        """
    )
    assert not (systemd_dir / "salt-api.service.d" / conf_name).exists()

    with pytest.helpers.temp_file(
        name=conf_name, directory=systemd_dir / "salt-api.service.d", contents=contents
    ), pytest.helpers.temp_file(
        name=conf_name,
        directory=systemd_dir / "salt-minion.service.d",
        contents=contents,
    ), pytest.helpers.temp_file(
        name=conf_name,
        directory=systemd_dir / "salt-master.service.d",
        contents=contents,
    ):
        yield
    assert not (systemd_dir / "salt-api.service.d" / conf_name).exists()


@pytest.fixture
def salt_systemd_setup(
    call_cli, install_salt_systemd, salt_systemd_overrides, debian_disable_policy_rcd
):
    """
    Fixture install previous version and set systemd for salt packages
    to enabled and active

    This fixture is function scoped, so it will be run for each test
    """

    upgrade_version = packaging.version.parse(install_salt_systemd.artifact_version)
    test_list = ["salt-api", "salt-minion", "salt-master"]

    # We should have a previous version installed, but if not then use install_previous
    ret = call_cli.run("--local", "test.version")
    assert ret.returncode == 0
    installed_minion_version = packaging.version.parse(ret.data)
    if installed_minion_version >= upgrade_version:
        # Install previous version, downgrading if necessary
        install_salt_systemd.install_previous(downgrade=True)

    # Verify that the previous version is installed
    ret = call_cli.run("--local", "test.version")
    assert ret.returncode == 0
    installed_minion_version = packaging.version.parse(ret.data)
    assert installed_minion_version < upgrade_version
    previous_version = installed_minion_version

    # Ensure known state for systemd services - enabled
    for test_item in test_list:
        test_cmd = f"systemctl enable {test_item}"
        ret = call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

    # Run tests
    yield

    # Verify that the new version is installed after the test
    ret = call_cli.run("--local", "test.version")
    assert ret.returncode == 0
    installed_minion_version = packaging.version.parse(ret.data)
    assert installed_minion_version == upgrade_version

    # Reset systemd services to their preset states
    for test_item in test_list:
        test_cmd = f"systemctl preset {test_item}"
        ret = call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

    # Install previous version, downgrading if necessary
    install_salt_systemd.install_previous(downgrade=True)

    # Ensure services are started on debian/ubuntu
    if install_salt_systemd.distro_name in ["debian", "ubuntu"]:
        install_salt_systemd.restart_services()

    # For debian/ubuntu, ensure pinning file is for major version of previous
    # version, not minor
    if install_salt_systemd.distro_name in ["debian", "ubuntu"]:
        pref_file = pathlib.Path("/etc", "apt", "preferences.d", "salt-pin-1001")
        pref_file.parent.mkdir(exist_ok=True)
        pin = f"{previous_version.major}.*"
        with salt.utils.files.fopen(pref_file, "w") as fp:
            fp.write(f"Package: salt-*\n" f"Pin: version {pin}\n" f"Pin-Priority: 1001")


@pytest.fixture
def salt_systemd_mask_services(call_cli):
    """
    Fixture to mask systemd services for salt-api, salt-minion, and
    salt-master services.

    This is required to test the preservation of masked state during upgrades.
    """

    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl mask {test_item}"
        ret = call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

    yield

    # Cleanup: unmask the services after the test
    for test_item in test_list:
        test_cmd = f"systemctl unmask {test_item}"
        ret = call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0
