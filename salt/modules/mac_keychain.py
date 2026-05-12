"""
Install certificates into the keychain on Mac OS

.. versionadded:: 2016.3.0

"""

import logging
import re
import shlex

import salt.utils.platform

log = logging.getLogger(__name__)

__virtualname__ = "keychain"


def __virtual__():
    """
    Only work on Mac OS
    """
    if salt.utils.platform.is_darwin():
        return __virtualname__
    return (False, "Only available on Mac OS systems with pipes")


def install(
    cert,
    password,
    keychain="/Library/Keychains/System.keychain",
    allow_any=False,
    keychain_password=None,
):
    """
    Install a certificate

    cert
        The certificate to install

    password
        The password for the certificate being installed formatted in the way
        described for openssl command in the PASS PHRASE ARGUMENTS section.

        Note: The password given here will show up as plaintext in the job returned
        info.

    keychain
        The keychain to install the certificate to, this defaults to
        /Library/Keychains/System.keychain

    allow_any
        Allow any application to access the imported certificate without warning

    keychain_password
        If your keychain is likely to be locked pass the password and it will be unlocked
        before running the import

        Note: The password given here will show up as plaintext in the returned job
        info.

    CLI Example:

    .. code-block:: bash

        salt '*' keychain.install test.p12 test123
    """
    if keychain_password is not None:
        unlock_keychain(keychain, keychain_password)

    cmd = f"security import {cert} -P {password} -k {keychain}"
    if allow_any:
        cmd += " -A"
    return __salt__["cmd.run"](cmd)


def uninstall(
    cert_name, keychain="/Library/Keychains/System.keychain", keychain_password=None
):
    """
    Uninstall a certificate from a keychain

    cert_name
        The name of the certificate to remove

    keychain
        The keychain to install the certificate to, this defaults to
        /Library/Keychains/System.keychain

    keychain_password
        If your keychain is likely to be locked pass the password and it will be unlocked
        before running the import

        Note: The password given here will show up as plaintext in the returned job
        info.

    CLI Example:

    .. code-block:: bash

        salt '*' keychain.install test.p12 test123
    """
    if keychain_password is not None:
        unlock_keychain(keychain, keychain_password)

    cmd = f'security delete-certificate -c "{cert_name}" {keychain}'
    return __salt__["cmd.run"](cmd)


def list_certs(keychain="/Library/Keychains/System.keychain"):
    """
    List all of the installed certificates

    keychain
        The keychain to install the certificate to, this defaults to
        /Library/Keychains/System.keychain

    CLI Example:

    .. code-block:: bash

        salt '*' keychain.list_certs
    """
    cmd = (
        'security find-certificate -a {} | grep -o "alis.*" | '
        "grep -o '\\\"[-A-Za-z0-9.:() ]*\\\"'".format(shlex.quote(keychain))
    )
    out = __salt__["cmd.run"](cmd, python_shell=True)
    return out.replace('"', "").split("\n")


def get_friendly_name(cert, password, legacy=False):
    """
    Get the friendly name of the given certificate

    cert
        The certificate to install

    password
        The password for the certificate being installed formatted in the way
        described for openssl command in the PASS PHRASE ARGUMENTS section

        Note: The password given here will show up as plaintext in the returned job
        info.

    legacy
        Assume legacy format for certificate.

    CLI Example:

    .. code-block:: bash

        salt '*' keychain.get_friendly_name /tmp/test.p12 test123

        salt '*' keychain.get_friendly_name /tmp/test.p12 test123 legacy=True
    """
    openssl_cmd = "openssl pkcs12"
    if legacy:
        openssl_cmd = f"{openssl_cmd} -legacy"

    cmd = (
        "{} -in {} -passin pass:{} -info -nodes -nokeys 2> /dev/null | "
        "grep friendlyName:".format(
            openssl_cmd, shlex.quote(cert), shlex.quote(password)
        )
    )
    out = __salt__["cmd.run"](cmd, python_shell=True)
    return out.replace("friendlyName: ", "").strip()


def get_default_keychain(user=None, domain="user"):
    """
    Get the default keychain

    user
        The user to check the default keychain of

    domain
        The domain to use valid values are user|system|common|dynamic, the default is user

    CLI Example:

    .. code-block:: bash

        salt '*' keychain.get_default_keychain
    """
    cmd = f"security default-keychain -d {domain}"
    return __salt__["cmd.run"](cmd, runas=user)


def set_default_keychain(keychain, domain="user", user=None):
    """
    Set the default keychain

    keychain
        The location of the keychain to set as default

    domain
        The domain to use valid values are user|system|common|dynamic, the default is user

    user
        The user to set the default keychain as

    CLI Example:

    .. code-block:: bash

        salt '*' keychain.set_keychain /Users/fred/Library/Keychains/login.keychain
    """
    cmd = f"security default-keychain -d {domain} -s {keychain}"
    return __salt__["cmd.run"](cmd, runas=user)


def unlock_keychain(keychain, password):
    """
    Unlock the given keychain with the password

    keychain
        The keychain to unlock

    password
        The password to use to unlock the keychain.

        Note: The password given here will show up as plaintext in the returned job
        info.

    CLI Example:

    .. code-block:: bash

        salt '*' keychain.unlock_keychain /tmp/test.p12 test123
    """
    cmd = f"security unlock-keychain -p {password} {keychain}"
    __salt__["cmd.run"](cmd)


def get_hash(name, password=None):
    """
    Returns the hash of a certificate in the keychain.

    name
        The name of the certificate (which you can get from keychain.get_friendly_name) or the
        location of a p12 file.

    password
        The password that is used in the certificate. Only required if your passing a p12 file.
        Note: This will be outputted to logs

    CLI Example:

    .. code-block:: bash

        salt '*' keychain.get_hash /tmp/test.p12 test123
    """

    if ".p12" in name[-4:]:
        cmd = "openssl pkcs12 -in {0} -passin pass:{1} -passout pass:{1}".format(
            name, password
        )
    else:
        cmd = f'security find-certificate -c "{name}" -m -p'

    out = __salt__["cmd.run"](cmd)
    matches = re.search(
        "-----BEGIN CERTIFICATE-----(.*)-----END CERTIFICATE-----",
        out,
        re.DOTALL | re.MULTILINE,
    )
    if matches:
        return matches.group(1)
    else:
        return False
