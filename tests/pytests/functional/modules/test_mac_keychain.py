"""
Validate the mac-keychain module
"""

import os

import pytest

import salt.utils.versions
from tests.support.runtests import RUNTIME_VARS

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="module")
def cmd(modules):
    return modules.cmd


@pytest.fixture(scope="module")
def keychain(modules):
    return modules.keychain


@pytest.fixture(scope="function", autouse=True)
def setup_teardown_vars(keychain, base_env_state_tree_root_dir):
    cert = os.path.join(RUNTIME_VARS.FILES, "file", "base", "certs", "salttest.p12")
    cert_alias = "Salt Test"
    passwd = "salttest"

    try:
        yield cert, cert_alias, passwd
    finally:
        certs_list = keychain.list_certs()
        if cert_alias in certs_list:
            keychain.uninstall(cert_alias)


def test_mac_keychain_install(keychain, setup_teardown_vars):
    """
    Tests that attempts to install a certificate
    """

    cert = setup_teardown_vars[0]
    cert_alias = setup_teardown_vars[1]
    passwd = setup_teardown_vars[2]

    install_cert = keychain.install(cert, passwd)
    assert install_cert
    assert install_cert == "1 identity imported."

    # check to ensure the cert was installed
    certs_list = keychain.list_certs()
    assert cert_alias in certs_list


def test_mac_keychain_uninstall(keychain, setup_teardown_vars):
    """
    Tests that attempts to uninstall a certificate
    """

    cert = setup_teardown_vars[0]
    cert_alias = setup_teardown_vars[1]
    passwd = setup_teardown_vars[2]

    keychain.install(cert, passwd)
    certs_list = keychain.list_certs()

    if cert_alias not in certs_list:
        keychain.uninstall(cert_alias)
        pytest.skip("Failed to install keychain")

    # uninstall cert
    keychain.uninstall(cert_alias)
    certs_list = keychain.list_certs()

    # check to ensure the cert was uninstalled
    assert cert_alias not in str(certs_list)


@pytest.mark.skip_if_binaries_missing("openssl")
def test_mac_keychain_get_friendly_name(keychain, shell, setup_teardown_vars):
    """
    Test that attempts to get friendly name of a cert
    """
    cert = setup_teardown_vars[0]
    cert_alias = setup_teardown_vars[1]
    passwd = setup_teardown_vars[2]

    keychain.install(cert, passwd)
    certs_list = keychain.list_certs()
    if cert_alias not in certs_list:
        keychain.uninstall(cert_alias)
        pytest.skip("Failed to install keychain")

    ret = shell.run("openssl", "version")
    assert ret.stdout
    openssl_version = ret.stdout.split()[1]

    # openssl versions under 3.0.0 do not include legacy flag
    if salt.utils.versions.compare(ver1=openssl_version, oper="<", ver2="3.0.0"):
        get_name = keychain.get_friendly_name(cert, passwd, legacy=False)
    else:
        get_name = keychain.get_friendly_name(cert, passwd, legacy=True)

    assert get_name == cert_alias


def test_mac_keychain_get_default_keychain(keychain, cmd, setup_teardown_vars):
    """
    Test that attempts to get the default keychain
    """
    sys_get_keychain = keychain.get_default_keychain()
    salt_get_keychain = cmd.run("security default-keychain -d user")
    assert salt_get_keychain == sys_get_keychain


def test_mac_keychain_list_certs(keychain, setup_teardown_vars):
    """
    Test that attempts to list certs
    """
    cert_default = "com.apple.systemdefault"
    certs = keychain.list_certs()
    assert cert_default in certs
