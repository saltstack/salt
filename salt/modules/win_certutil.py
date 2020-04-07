# -*- coding: utf-8 -*-
"""
This module allows you to install certificates into the windows certificate
manager.

.. code-block:: bash

    salt '*' certutil.add_store salt://cert.cer "TrustedPublisher"
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import re

# Import Salt Libs
import salt.utils.platform

log = logging.getLogger(__name__)
__virtualname__ = "certutil"


def __virtual__():
    """
    Only work on Windows
    """
    if salt.utils.platform.is_windows():
        return __virtualname__
    return False


def get_cert_serial(cert_file):
    """
    Get the serial number of a certificate file

    cert_file
        The certificate file to find the serial for

    CLI Example:

    .. code-block:: bash

        salt '*' certutil.get_cert_serial <certificate name>
    """
    cmd = "certutil.exe -silent -verify {0}".format(cert_file)
    out = __salt__["cmd.run"](cmd)
    # match serial number by paragraph to work with multiple languages
    matches = re.search(r":\s*(\w*)\r\n\r\n", out)
    if matches is not None:
        return matches.groups()[0].strip()
    else:
        return None


def get_stored_cert_serials(store):
    """
    Get all of the certificate serials in the specified store

    store
        The store to get all the certificate serials from

    CLI Example:

    .. code-block:: bash

        salt '*' certutil.get_stored_cert_serials <store>
    """
    cmd = "certutil.exe -store {0}".format(store)
    out = __salt__["cmd.run"](cmd)
    # match serial numbers by header position to work with multiple languages
    matches = re.findall(r"={16}\r\n.*:\s*(\w*)\r\n", out)
    return matches


def add_store(source, store, saltenv="base"):
    """
    Add the given cert into the given Certificate Store

    source
        The source certificate file this can be in the form
        salt://path/to/file

    store
        The certificate store to add the certificate to

    saltenv
        The salt environment to use this is ignored if the path
        is local

    CLI Example:

    .. code-block:: bash

        salt '*' certutil.add_store salt://cert.cer TrustedPublisher
    """
    cert_file = __salt__["cp.cache_file"](source, saltenv)
    cmd = "certutil.exe -addstore {0} {1}".format(store, cert_file)
    return __salt__["cmd.run"](cmd)


def del_store(source, store, saltenv="base"):
    """
    Delete the given cert into the given Certificate Store

    source
        The source certificate file this can be in the form
        salt://path/to/file

    store
        The certificate store to delete the certificate from

    saltenv
        The salt environment to use this is ignored if the path
        is local

    CLI Example:

    .. code-block:: bash

        salt '*' certutil.del_store salt://cert.cer TrustedPublisher
    """
    cert_file = __salt__["cp.cache_file"](source, saltenv)
    serial = get_cert_serial(cert_file)
    cmd = "certutil.exe -delstore {0} {1}".format(store, serial)
    return __salt__["cmd.run"](cmd)
