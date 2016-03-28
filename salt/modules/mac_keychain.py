# -*- coding: utf-8 -*-
'''
Install certificates into the keychain on Mac OS

.. versionadded:: 2016.3.0

'''

# Import python libs
from __future__ import absolute_import
import logging
import re

import shlex
try:
    import pipes
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)
__virtualname__ = 'keychain'

if hasattr(shlex, 'quote'):
    _quote = shlex.quote
elif HAS_DEPS and hasattr(pipes, 'quote'):
    _quote = pipes.quote
else:
    _quote = None


def __virtual__():
    '''
    Only work on Mac OS
    '''
    if salt.utils.is_darwin() and _quote is not None:
        return __virtualname__
    return False


def install(cert,
            password,
            keychain="/Library/Keychains/System.keychain",
            allow_any=False,
            keychain_password=None):
    '''
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
    '''
    if keychain_password is not None:
        unlock_keychain(keychain, keychain_password)

    cmd = 'security import {0} -P {1} -k {2}'.format(cert, password, keychain)
    if allow_any:
        cmd += ' -A'
    return __salt__['cmd.run'](cmd)


def uninstall(cert_name,
              keychain="/Library/Keychains/System.keychain",
              keychain_password=None):
    '''
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

    '''
    if keychain_password is not None:
        unlock_keychain(keychain, keychain_password)

    cmd = 'security delete-certificate -c "{0}" {1}'.format(cert_name, keychain)
    return __salt__['cmd.run'](cmd)


def list_certs(keychain="/Library/Keychains/System.keychain"):
    '''
    List all of the installed certificates

    keychain
        The keychain to install the certificate to, this defaults to
        /Library/Keychains/System.keychain

    CLI Example:

    .. code-block:: bash

        salt '*' keychain.list_certs

    '''
    cmd = 'security find-certificate -a {0} | grep -o "alis".*\\" | ' \
          'grep -o \'\\"[-A-Za-z0-9.:() ]*\\"\''.format(_quote(keychain))
    out = __salt__['cmd.run'](cmd, python_shell=True)
    return out.replace('"', '').split('\n')


def get_friendly_name(cert, password):
    '''
    Get the friendly name of the given certificate

    cert
        The certificate to install

    password
        The password for the certificate being installed formatted in the way
        described for openssl command in the PASS PHRASE ARGUMENTS section

        Note: The password given here will show up as plaintext in the returned job
        info.

    CLI Example:

    .. code-block:: bash

        salt '*' keychain.get_friendly_name /tmp/test.p12 test123

    '''
    cmd = 'openssl pkcs12 -in {0} -passin pass:{1} -info -nodes -nokeys 2> /dev/null | ' \
          'grep friendlyName:'.format(_quote(cert), _quote(password))
    out = __salt__['cmd.run'](cmd, python_shell=True)
    return out.replace("friendlyName: ", "").strip()


def get_default_keychain(user=None, domain="user"):
    '''
    Get the default keychain

    user
        The user to check the default keychain of

    domain
        The domain to use valid values are user|system|common|dynamic, the default is user

    CLI Example:

    .. code-block:: bash

        salt '*' keychain.get_default_keychain

    '''
    cmd = "security default-keychain -d {0}".format(domain)
    return __salt__['cmd.run'](cmd, runas=user)


def set_default_keychain(keychain, domain="user", user=None):
    '''
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

    '''
    cmd = "security default-keychain -d {0} -s {1}".format(domain, keychain)
    return __salt__['cmd.run'](cmd, runas=user)


def unlock_keychain(keychain, password):
    '''
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

    '''
    cmd = 'security unlock-keychain -p {0} {1}'.format(password, keychain)
    __salt__['cmd.run'](cmd)


def get_hash(name, password=None):
    '''
    Returns the hash of a certificate in the keychain.

    name
        The name of the certificate (which you can get from keychain.get_friendly_name) or the
        location of a p12 file.

    password
        The password that is used in the certificate. Only required if your passing a p12 file.
        Note: This will be outputted to logs
    '''

    if '.p12' in name[-4:]:
        cmd = 'openssl pkcs12 -in {0} -passin pass:{1} -passout pass:{1}'.format(name, password)
    else:
        cmd = 'security find-certificate -c "{0}" -m -p'.format(name)

    out = __salt__['cmd.run'](cmd)
    matches = re.search('-----BEGIN CERTIFICATE-----(.*)-----END CERTIFICATE-----', out, re.DOTALL | re.MULTILINE)
    if matches:
        return matches.group(1)
    else:
        return False
