# -*- coding: utf-8 -*-
"""
Installing of certificates to the keychain
==========================================

Install certificats to the macOS keychain

.. code-block:: yaml

    /mnt/test.p12:
      keychain.installed:
        - password: test123
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging
import os

# Import Salt libs
import salt.utils.platform

log = logging.getLogger(__name__)
__virtualname__ = "keychain"


def __virtual__():
    """
    Only work on Mac OS
    """
    if salt.utils.platform.is_darwin():
        return __virtualname__
    return False


def installed(name, password, keychain="/Library/Keychains/System.keychain", **kwargs):
    """
    Install a p12 certificate file into the macOS keychain

    name
        The certificate to install

    password
        The password for the certificate being installed formatted in the way
        described for openssl command in the PASS PHRASE ARGUMENTS section

    keychain
        The keychain to install the certificate to, this defaults to
        /Library/Keychains/System.keychain

    allow_any
        Allow any application to access the imported certificate without warning

    keychain_password
        If your keychain is likely to be locked pass the password and it will be unlocked
        before running the import

    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    if "http" in name or "salt" in name:
        name = __salt__["cp.cache_file"](name)

    certs = __salt__["keychain.list_certs"](keychain)
    friendly_name = __salt__["keychain.get_friendly_name"](name, password)

    if friendly_name in certs:
        file_hash = __salt__["keychain.get_hash"](name, password)
        keychain_hash = __salt__["keychain.get_hash"](friendly_name)

        if file_hash != keychain_hash:
            out = __salt__["keychain.uninstall"](
                friendly_name,
                keychain,
                keychain_password=kwargs.get("keychain_password"),
            )
            if "unable" not in out:
                ret[
                    "comment"
                ] += "Found a certificate with the same name but different hash, removing it.\n"
                ret["changes"]["uninstalled"] = friendly_name

                # Reset the certs found
                certs = __salt__["keychain.list_certs"](keychain)
            else:
                ret["result"] = False
                ret[
                    "comment"
                ] += "Found an incorrect cert but was unable to uninstall it: {0}".format(
                    friendly_name
                )
                return ret

    if friendly_name not in certs:
        out = __salt__["keychain.install"](name, password, keychain, **kwargs)
        if "imported" in out:
            ret["changes"]["installed"] = friendly_name
        else:
            ret["result"] = False
            ret["comment"] += "Failed to install {0}".format(friendly_name)
    else:
        ret["comment"] += "{0} already installed.".format(friendly_name)

    return ret


def uninstalled(
    name,
    password,
    keychain="/Library/Keychains/System.keychain",
    keychain_password=None,
):
    """
    Uninstall a p12 certificate file from the macOS keychain

    name
        The certificate to uninstall, this can be a path for a .p12 or the friendly
        name

    password
        The password for the certificate being installed formatted in the way
        described for openssl command in the PASS PHRASE ARGUMENTS section

    cert_name
        The friendly name of the certificate, this can be used instead of giving a
        certificate

    keychain
        The keychain to remove the certificate from, this defaults to
        /Library/Keychains/System.keychain

    keychain_password
        If your keychain is likely to be locked pass the password and it will be unlocked
        before running the import

    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    certs = __salt__["keychain.list_certs"](keychain)

    if ".p12" in name:
        if "http" in name or "salt" in name:
            name = __salt__["cp.cache_file"](name)

        friendly_name = __salt__["keychain.get_friendly_name"](name, password)
    else:
        friendly_name = name

    if friendly_name in certs:
        out = __salt__["keychain.uninstall"](friendly_name, keychain, keychain_password)
        if "unable" not in out:
            ret["changes"]["uninstalled"] = friendly_name
        else:
            ret["result"] = False
            ret["comment"] += "Failed to uninstall {0}".format(friendly_name)
    else:
        ret["comment"] += "{0} already uninstalled.".format(friendly_name)

    return ret


def default_keychain(name, domain="user", user=None):
    """
    Set the default keychain to use

    name
        The chain in which to use as the default

    domain
        The domain to use valid values are user|system|common|dynamic, the default is user

    user
        The user to run as

    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    if not os.path.exists(name):
        ret["result"] = False
        ret["comment"] += "Keychain not found at {0}".format(name)
    else:
        out = __salt__["keychain.get_default_keychain"](user, domain)

        if name in out:
            ret["comment"] += "{0} was already the default keychain.".format(name)
        else:
            out = __salt__["keychain.set_default_keychain"](name, domain, user)
            if len(out) == 0:
                ret["changes"]["default"] = name
            else:
                ret["result"] = False
                ret["comment"] = "Failed to install keychain. {0}".format(out)

    return ret
