"""
Validate the mac-keychain module
"""

import os

import pytest

import salt.utils.versions
from salt.exceptions import CommandExecutionError
from tests.support.runtests import RUNTIME_VARS

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="function")
def setup_teardown_vars(salt_call_cli, base_env_state_tree_root_dir):
    cert = os.path.join(RUNTIME_VARS.FILES, "file", "base", "certs", "salttest.p12")
    cert_alias = "Salt Test"
    passwd = "salttest"

    try:
        yield cert, cert_alias, passwd
    finally:
        ret = salt_call_cli.run("keychain.list_certs")
        certs_list = ret.data
        if cert_alias in certs_list:
            salt_call_cli.run("keychain.uninstall", cert_alias)


def test_mac_keychain_install(setup_teardown_vars, salt_call_cli):
    """
    Tests that attempts to install a certificate
    """

    cert = setup_teardown_vars[0]
    cert_alias = setup_teardown_vars[1]
    passwd = setup_teardown_vars[2]

    ret = salt_call_cli.run("keychain.install", cert, passwd)
    install_cert = ret.data
    assert install_cert
    assert install_cert == "1 identity imported."

    # check to ensure the cert was installed
    ret = salt_call_cli.run("keychain.list_certs")
    certs_list = ret.data
    assert cert_alias in certs_list


def test_mac_keychain_uninstall(setup_teardown_vars, salt_call_cli):
    """
    Tests that attempts to uninstall a certificate
    """

    cert = setup_teardown_vars[0]
    cert_alias = setup_teardown_vars[1]
    passwd = setup_teardown_vars[2]

    salt_call_cli.run("keychain.install", cert, passwd)
    ret = salt_call_cli.run("keychain.list_certs")
    certs_list = ret.data

    if cert_alias not in certs_list:
        salt_call_cli.run("keychain.uninstall", cert_alias)
        pytest.skip("Failed to install keychain")

    # uninstall cert
    salt_call_cli.run("keychain.uninstall", cert_alias)
    ret = salt_call_cli.run("keychain.list_certs")
    certs_list = ret.data

    # check to ensure the cert was uninstalled
    try:
        assert cert_alias not in str(certs_list)
    except CommandExecutionError:
        salt_call_cli.run("keychain.uninstall", cert_alias)


@pytest.mark.skip_if_binaries_missing("openssl")
def test_mac_keychain_get_friendly_name(setup_teardown_vars, salt_call_cli, shell):
    """
    Test that attempts to get friendly name of a cert
    """
    cert = setup_teardown_vars[0]
    cert_alias = setup_teardown_vars[1]
    passwd = setup_teardown_vars[2]

    salt_call_cli.run("keychain.install", cert, passwd)
    ret = salt_call_cli.run("keychain.list_certs")
    certs_list = ret.data
    if cert_alias not in certs_list:
        salt_call_cli.run("keychain.uninstall", cert_alias)
        pytest.skip("Failed to install keychain")

    ret = shell.run("openssl", "version")
    assert ret.stdout
    openssl_version = ret.stdout.split()[1]

    # openssl versions under 3.0.0 do not include legacy flag
    if salt.utils.versions.compare(ver1=openssl_version, oper="<", ver2="3.0.0"):
        ret = salt_call_cli.run(
            "keychain.get_friendly_name", cert, passwd, legacy=False
        )
    else:
        ret = salt_call_cli.run("keychain.get_friendly_name", cert, passwd, legacy=True)

    get_name = ret.data
    assert get_name == cert_alias


def test_mac_keychain_get_default_keychain(salt_call_cli):
    """
    Test that attempts to get the default keychain
    """
    ret = salt_call_cli.run("keychain.get_default_keychain")
    salt_get_keychain = ret.data
    ret = salt_call_cli.run("cmd.run", "security default-keychain -d user")
    sys_get_keychain = ret.data
    assert salt_get_keychain == sys_get_keychain


def test_mac_keychain_list_certs(salt_call_cli):
    """
    Test that attempts to list certs
    """
    cert_default = "com.apple.systemdefault"
    ret = salt_call_cli.run("keychain.list_certs")
    certs = ret.data
    assert cert_default in certs
