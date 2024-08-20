"""
Installing of certificates to the Windows Certificate Manager
=============================================================

Install certificates to the Windows Certificate Manager

.. code-block:: yaml

    salt://certs/cert.cer:
      certutil.add_store:
        - store: TrustedPublisher
"""

import logging

import salt.utils.platform

log = logging.getLogger(__name__)
__virtualname__ = "certutil"


def __virtual__():
    """
    Only work on Windows
    """
    if salt.utils.platform.is_windows():
        return __virtualname__
    return (False, "Only Windows supported")


def add_store(name, store, saltenv="base"):
    """
    Store a certificate to the given certificate store

    Args:

        name (str):
            The path to the certificate to add to the store. This is either the
            path to a local file or a file from the file server in the form of
            ``salt://path/to/file``

        store (str):
            The certificate store to add the certificate to

        saltenv (str):
            The salt environment to use. This is ignored if the path is local

    Returns:
        dict: A dictionary containing the results

    CLI Example:

    .. code-block:: yaml

        add_certificate:
          certutil.add_store:
            name: salt://web_cert.cer
            store: TrustedPublisher
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    cert_file = __salt__["cp.cache_file"](name, saltenv)
    if cert_file is False:
        ret["comment"] = f"Certificate file not found: {name}"
        ret["result"] = False
        return ret

    cert_serial = __salt__["certutil.get_cert_serial"](name)
    if cert_serial is None:
        ret["comment"] = f"Invalid certificate file: {name}"
        ret["result"] = False
        return ret

    old_serials = __salt__["certutil.get_stored_cert_serials"](store=store)
    if cert_serial in old_serials:
        ret["comment"] = f"Certificate already present: {name}"
        return ret

    if __opts__["test"]:
        ret["comment"] = f"Certificate will be added: {name}"
        ret["result"] = None
        return ret

    retcode = __salt__["certutil.add_store"](name, store, retcode=True)
    if retcode != 0:
        ret["comment"] = f"Error adding certificate: {name}"
        ret["result"] = False
        return ret

    new_serials = __salt__["certutil.get_stored_cert_serials"](store=store)
    if cert_serial in new_serials:
        ret["changes"]["added"] = name
        ret["comment"] = f"Added certificate: {name}"
    else:
        ret["comment"] = f"Failed to add certificate: {name}"
        ret["result"] = False

    return ret


def del_store(name, store, saltenv="base"):
    """
    Remove a certificate from the given certificate store

    Args:

        name (str):
            The path to the certificate to remove from the store. This is either
            the path to a local file or a file from the file server in the form
            of ``salt://path/to/file``

        store (str):
            The certificate store to remove the certificate from

        saltenv (str):
            The salt environment to use. This is ignored if the path is local

    Returns:
        dict: A dictionary containing the results

    CLI Example:

    .. code-block:: yaml

        remove_certificate:
          certutil.del_store:
            name: salt://web_cert.cer
            store: TrustedPublisher
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    cert_file = __salt__["cp.cache_file"](name, saltenv)
    if cert_file is False:
        ret["comment"] = f"Certificate file not found: {name}"
        ret["result"] = False
        return ret

    cert_serial = __salt__["certutil.get_cert_serial"](name)
    if cert_serial is None:
        ret["comment"] = f"Invalid certificate file: {name}"
        ret["result"] = False
        return ret

    old_serials = __salt__["certutil.get_stored_cert_serials"](store=store)
    if cert_serial not in old_serials:
        ret["comment"] = f"Certificate already absent: {name}"
        return ret

    if __opts__["test"]:
        ret["comment"] = f"Certificate will be removed: {name}"
        ret["result"] = None
        return ret

    retcode = __salt__["certutil.del_store"](name, store, retcode=True)
    if retcode != 0:
        ret["comment"] = f"Error removing certificate: {name}"
        ret["result"] = False
        return ret

    new_serials = __salt__["certutil.get_stored_cert_serials"](store=store)
    if cert_serial not in new_serials:
        ret["changes"]["removed"] = name
        ret["comment"] = f"Removed certificate: {name}"
    else:
        ret["comment"] = f"Failed to remove certificate: {name}"
        ret["result"] = False

    return ret
