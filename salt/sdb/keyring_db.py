"""
Keyring Database Module

:maintainer:    SaltStack
:maturity:      New
:depends:       keyring
:platform:      all

This module allows access to the keyring package using an ``sdb://`` URI. This
package is located at ``https://pypi.python.org/pypi/keyring``.

Care must be taken when using keyring. Not all keyend backends are supported on
all operating systems. Also, many backends require an agent to be running in
order to work. For instance, the "Secret Service" backend requires a compatible
agent such as ``gnome-keyring-daemon`` or ``kwallet`` to be running. The
keyczar backend does not seem to enjoy the benefits of an agent, and so using
it will require either that the password is typed in manually (which is
unreasonable for the salt-minion and salt-master daemons, especially in
production) or an agent is written for it.

Like all sdb modules, the keyring module requires a configuration profile to
be configured in either the minion or master configuration file. This profile
requires very little. In the example:

.. code-block:: yaml

    mykeyring:
      driver: keyring
      service: system

The ``driver`` refers to the keyring module, ``service`` refers to the service
that will be used inside of keyring (which may be likened unto a database
table) and ``mykeyring`` refers to the name that will appear in the URI:

.. code-block:: yaml

    password: sdb://mykeyring/mypassword

The underlying backend configuration must be configured via keyring itself. For
examples and documentation, see keyring:

https://pypi.python.org/pypi/keyring

.. versionadded:: 2014.1.4
"""

import logging

try:
    import keyring

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

log = logging.getLogger(__name__)

__func_alias__ = {"set_": "set"}

__virtualname__ = "keyring"


def __virtual__():
    """
    Only load the module if keyring is installed
    """
    if HAS_LIBS:
        return __virtualname__
    return False


def set_(key, value, service=None, profile=None):
    """
    Set a key/value pair in a keyring service
    """
    service = _get_service(service, profile)
    keyring.set_password(service, key, value)


def get(key, service=None, profile=None):
    """
    Get a value from a keyring service
    """
    service = _get_service(service, profile)
    return keyring.get_password(service, key)


def _get_service(service, profile):
    """
    Get a service name
    """
    if isinstance(profile, dict) and "service" in profile:
        return profile["service"]

    return service
