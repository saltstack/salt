"""
This module allows you to install certificates into the windows certificate
manager.

.. code-block:: bash

    salt '*' certutil.add_store salt://cert.cer "TrustedPublisher"
"""

import logging
import os
import re

import salt.utils.platform
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)
__virtualname__ = "certutil"


def __virtual__():
    """
    Only works on Windows
    """
    if salt.utils.platform.is_windows():
        return __virtualname__
    return False, "Module win_certutil: module only works on Windows systems."


def get_cert_serial(cert_file, saltenv="base"):
    """
    Get the serial number of a certificate file

    cert_file (str):
        The certificate file to find the serial for. Can be a local file or a
        a file on the file server (``salt://``)

    Returns:
        str: The serial number of the certificate if found, otherwise None

    CLI Example:

    .. code-block:: bash

        salt '*' certutil.get_cert_serial <certificate name>
    """
    cert_file = __salt__["cp.cache_file"](cert_file, saltenv)

    # Since we're allowing a path, let's make sure it exists
    if not os.path.exists(cert_file):
        msg = f"cert_file not found: {cert_file}"
        raise CommandExecutionError(msg)

    cmd = f'certutil.exe -silent -verify "{cert_file}"'
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

    store (str):
        The store to get all the certificate serials from

    Returns:
        list: A list of serial numbers found, or an empty list if none found

    CLI Example:

    .. code-block:: bash

        salt '*' certutil.get_stored_cert_serials <store>
    """
    cmd = f'certutil.exe -store "{store}"'
    out = __salt__["cmd.run"](cmd)
    # match serial numbers by header position to work with multiple languages
    matches = re.findall(r"={16}\r\n.*:\s*(\w*)\r\n", out)
    return matches


def add_store(source, store, retcode=False, saltenv="base"):
    """
    Add the cert to the given Certificate Store

    source (str):
        The source certificate file. This is either the path to a local file or
        a file from the file server in the form of ``salt://path/to/file``

    store (str):
        The certificate store to add the certificate to

    retcode (bool):
        If ``True``, return the retcode instead of stdout. Default is ``False``

    saltenv (str):
        The salt environment to use. This is ignored if the path is local

    CLI Example:

    .. code-block:: bash

        salt '*' certutil.add_store salt://cert.cer TrustedPublisher
        salt '*' certutil.add_store C:\\path\\to\\local.cer TrustedPublisher
    """
    source = __salt__["cp.cache_file"](source, saltenv)

    # Since we're allowing a path, let's make sure it exists
    if not os.path.exists(source):
        msg = f"cert_file not found: {source}"
        raise CommandExecutionError(msg)

    cmd = f'certutil.exe -addstore {store} "{source}"'
    if retcode:
        return __salt__["cmd.retcode"](cmd)
    else:
        return __salt__["cmd.run"](cmd)


def del_store(source, store, retcode=False, saltenv="base"):
    """
    Delete the cert from the given Certificate Store

    source (str):
        The source certificate file. This is either the path to a local file or
        a file from the file server in the form of ``salt://path/to/file``

    store (str):
        The certificate store to delete the certificate from

    retcode (bool):
        If ``True``, return the retcode instead of stdout. Default is ``False``

    saltenv (str):
        The salt environment to use. This is ignored if the path is local

    CLI Example:

    .. code-block:: bash

        salt '*' certutil.del_store salt://cert.cer TrustedPublisher
        salt '*' certutil.del_store C:\\path\\to\\local.cer TrustedPublisher
    """
    source = __salt__["cp.cache_file"](source, saltenv)

    # Since we're allowing a path, let's make sure it exists
    if not os.path.exists(source):
        msg = f"cert_file not found: {source}"
        raise CommandExecutionError(msg)

    serial = get_cert_serial(source)
    cmd = f'certutil.exe -delstore {store} "{serial}"'
    if retcode:
        return __salt__["cmd.retcode"](cmd)
    else:
        return __salt__["cmd.run"](cmd)
