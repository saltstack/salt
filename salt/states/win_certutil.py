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
    Store a certificate to the given store

    name
        The certificate to store, this can use local paths
        or salt:// paths

    store
        The store to add the certificate to

    saltenv
        The salt environment to use, this is ignored if a local
        path is specified

    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    cert_file = __salt__["cp.cache_file"](name, saltenv)
    if cert_file is False:
        ret["result"] = False
        ret["comment"] += "Certificate file not found."
    else:
        cert_serial = __salt__["certutil.get_cert_serial"](cert_file)
        serials = __salt__["certutil.get_stored_cert_serials"](store)

        if cert_serial not in serials:
            retcode = __salt__["certutil.add_store"](name, store, retcode=True)
            if retcode == 0:
                ret["changes"]["added"] = name
            else:
                ret["result"] = False
                ret["comment"] += "Failed to store certificate {}".format(name)
        else:
            ret["comment"] += "{} already stored.".format(name)

    return ret


def del_store(name, store, saltenv="base"):
    """
    Remove a certificate in the given store

    name
        The certificate to remove, this can use local paths
        or salt:// paths

    store
        The store to remove the certificate from

    saltenv
        The salt environment to use, this is ignored if a local
        path is specified

    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    cert_file = __salt__["cp.cache_file"](name, saltenv)
    if cert_file is False:
        ret["result"] = False
        ret["comment"] += "Certificate file not found."
    else:
        cert_serial = __salt__["certutil.get_cert_serial"](cert_file)
        serials = __salt__["certutil.get_stored_cert_serials"](store)

        if cert_serial in serials:
            retcode = __salt__["certutil.del_store"](cert_file, store, retcode=True)
            if retcode == 0:
                ret["changes"]["removed"] = name
            else:
                ret["result"] = False
                ret["comment"] += "Failed to remove the certificate {}".format(name)
        else:
            ret["comment"] += "{} already removed.".format(name)

    return ret
