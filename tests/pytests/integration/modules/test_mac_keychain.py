"""
Validate the mac-keychain module
"""

import pytest

from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="function")
def setup_teardown_vars(salt_call_cli, base_env_state_tree_root_dir):
    cert = str(base_env_state_tree_root_dir / "certs" / "salttest.p12")
    cert_alias = "Salt Test"
    passwd = "salttest"

    try:
        yield cert, cert_alias, passwd
    finally:
        certs_list = salt_call_cli.run("keychain.list_certs")
        if cert_alias in certs_list:
            salt_call_cli.run("keychain.uninstall", cert_alias)


def test_mac_keychain_install(setup_teardown_vars, salt_call_cli):
    """
    Tests that attempts to install a certificate
    """

    cert = setup_teardown_vars[0]
    cert_alias = setup_teardown_vars[1]
    passwd = setup_teardown_vars[2]

    install_cert = salt_call_cli.run("keychain.install", cert, passwd)
    assert install_cert

    # check to ensure the cert was installed
    certs_list = salt_call_cli.run("keychain.list_certs")
    assert cert_alias in certs_list


def test_mac_keychain_uninstall(setup_teardown_vars, salt_call_cli):
    """
    Tests that attempts to uninstall a certificate
    """

    cert = setup_teardown_vars[0]
    cert_alias = setup_teardown_vars[1]
    passwd = setup_teardown_vars[2]

    salt_call_cli.run("keychain.install", cert, passwd)
    certs_list = salt_call_cli.run("keychain.list_certs")

    if cert_alias not in certs_list:
        salt_call_cli.run("keychain.uninstall", cert_alias)
        pytest.skip("Failed to install keychain")

    # uninstall cert
    salt_call_cli.run("keychain.uninstall", cert_alias)
    certs_list = salt_call_cli.run("keychain.list_certs")

    # check to ensure the cert was uninstalled
    try:
        assert cert_alias not in str(certs_list)
    except CommandExecutionError:
        salt_call_cli.run("keychain.uninstall", cert_alias)


def test_mac_keychain_get_friendly_name(setup_teardown_vars, salt_call_cli):
    """
    Test that attempts to get friendly name of a cert
    """
    cert = setup_teardown_vars[0]
    cert_alias = setup_teardown_vars[1]
    passwd = setup_teardown_vars[2]

    salt_call_cli.run("keychain.install", cert, passwd)
    certs_list = salt_call_cli.run("keychain.list_certs")
    if cert_alias not in certs_list:
        salt_call_cli.run("keychain.uninstall", cert_alias)
        pytest.skip("Failed to install keychain")

    get_name = salt_call_cli.run("keychain.get_friendly_name", cert, passwd)
    assert get_name == cert_alias


def test_mac_keychain_get_default_keychain(salt_call_cli):
    """
    Test that attempts to get the default keychain
    """
    salt_get_keychain = salt_call_cli.run("keychain.get_default_keychain")
    sys_get_keychain = salt_call_cli.run("cmd.run", "security default-keychain -d user")
    assert salt_get_keychain == sys_get_keychain


def test_mac_keychain_list_certs(salt_call_cli):
    """
    Test that attempts to list certs
    """
    cert_default = "com.apple.systemdefault"
    certs = salt_call_cli.run("keychain.list_certs")
    assert cert_default in certs
