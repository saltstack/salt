"""
Grain that reports which CA certificate store Salt is using for outbound
HTTPS/TLS connections.

.. versionadded:: 3008.0

Possible values for the ``ca_truststore`` grain:

``certifi``
    Default.  Salt uses the ``certifi`` CA bundle (or a system bundle on
    Linux when one is found at a well-known path).

``os``
    Salt has successfully injected the native OS certificate store via
    ``pip-system-certs`` (requires ``use_os_truststore: True`` in the minion
    configuration and the ``pip-system-certs`` package installed).
"""

import logging

import salt.utils.ostruststore

log = logging.getLogger(__name__)

__virtualname__ = "truststore"


def __virtual__():
    return __virtualname__


def ca_truststore():
    """
    Return the active CA trust store name as the ``ca_truststore`` grain.

    Example grain value::

        ca_truststore: certifi

    or, when OS trust store is active::

        ca_truststore: os
    """
    return {"ca_truststore": salt.utils.ostruststore.active_store_name(__opts__)}
