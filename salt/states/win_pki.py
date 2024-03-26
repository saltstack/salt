"""
Microsoft certificate management via the Pki PowerShell module.

:platform:      Windows

.. versionadded:: 2016.11.0
"""

_DEFAULT_CONTEXT = "LocalMachine"
_DEFAULT_FORMAT = "cer"
_DEFAULT_STORE = "My"


def __virtual__():
    """
    Load only on minions that have the win_pki module.
    """
    if "win_pki.get_stores" in __salt__:
        return True
    return (False, "win_pki module could not be loaded")


def import_cert(
    name,
    cert_format=_DEFAULT_FORMAT,
    context=_DEFAULT_CONTEXT,
    store=_DEFAULT_STORE,
    exportable=True,
    password="",
    saltenv="base",
):
    """
    Import the certificate file into the given certificate store.

    :param str name: The path of the certificate file to import.
    :param str cert_format: The certificate format. Specify 'cer' for X.509, or 'pfx' for PKCS #12.
    :param str context: The name of the certificate store location context.
    :param str store: The name of the certificate store.
    :param bool exportable: Mark the certificate as exportable. Only applicable to pfx format.
    :param str password: The password of the certificate. Only applicable to pfx format.
    :param str saltenv: The environment the file resides in.

    Example of usage with only the required arguments:

    .. code-block:: yaml

        site0-cert-imported:
            win_pki.import_cert:
                - name: salt://win/webserver/certs/site0.cer

    Example of usage specifying all available arguments:

    .. code-block:: yaml

        site0-cert-imported:
            win_pki.import_cert:
                - name: salt://win/webserver/certs/site0.pfx
                - cert_format: pfx
                - context: LocalMachine
                - store: My
                - exportable: True
                - password: TestPassword
                - saltenv: base
    """
    ret = {"name": name, "changes": dict(), "comment": "", "result": None}

    store_path = rf"Cert:\{context}\{store}"

    cached_source_path = __salt__["cp.cache_file"](name, saltenv)
    current_certs = __salt__["win_pki.get_certs"](context=context, store=store)
    if password:
        cert_props = __salt__["win_pki.get_cert_file"](
            name=cached_source_path, cert_format=cert_format, password=password
        )
    else:
        cert_props = __salt__["win_pki.get_cert_file"](
            name=cached_source_path, cert_format=cert_format
        )

    if cert_props["thumbprint"] in current_certs:
        ret["comment"] = "Certificate '{}' already contained in store: {}".format(
            cert_props["thumbprint"], store_path
        )
        ret["result"] = True
    elif __opts__["test"]:
        ret["comment"] = "Certificate '{}' will be imported into store: {}".format(
            cert_props["thumbprint"], store_path
        )
        ret["changes"] = {"old": None, "new": cert_props["thumbprint"]}
    else:
        ret["changes"] = {"old": None, "new": cert_props["thumbprint"]}
        ret["result"] = __salt__["win_pki.import_cert"](
            name=name,
            cert_format=cert_format,
            context=context,
            store=store,
            exportable=exportable,
            password=password,
            saltenv=saltenv,
        )
        if ret["result"]:
            ret["comment"] = "Certificate '{}' imported into store: {}".format(
                cert_props["thumbprint"], store_path
            )
        else:
            ret["comment"] = (
                "Certificate '{}' unable to be imported into store: {}".format(
                    cert_props["thumbprint"], store_path
                )
            )
    return ret


def remove_cert(name, thumbprint, context=_DEFAULT_CONTEXT, store=_DEFAULT_STORE):
    """
    Remove the certificate from the given certificate store.

    :param str thumbprint: The thumbprint value of the target certificate.
    :param str context: The name of the certificate store location context.
    :param str store: The name of the certificate store.

    Example of usage with only the required arguments:

    .. code-block:: yaml

        site0-cert-removed:
            win_pki.remove_cert:
                - thumbprint: 9988776655443322111000AAABBBCCCDDDEEEFFF

    Example of usage specifying all available arguments:

    .. code-block:: yaml

        site0-cert-removed:
            win_pki.remove_cert:
                - thumbprint: 9988776655443322111000AAABBBCCCDDDEEEFFF
                - context: LocalMachine
                - store: My
    """
    ret = {"name": name, "changes": dict(), "comment": "", "result": None}

    store_path = rf"Cert:\{context}\{store}"
    current_certs = __salt__["win_pki.get_certs"](context=context, store=store)

    if thumbprint not in current_certs:
        ret["comment"] = "Certificate '{}' already removed from store: {}".format(
            thumbprint, store_path
        )
        ret["result"] = True
    elif __opts__["test"]:
        ret["comment"] = "Certificate '{}' will be removed from store: {}".format(
            thumbprint, store_path
        )
        ret["changes"] = {"old": thumbprint, "new": None}
    else:
        ret["changes"] = {"old": thumbprint, "new": None}
        ret["result"] = __salt__["win_pki.remove_cert"](
            thumbprint=thumbprint, context=context, store=store
        )
        if ret["result"]:
            ret["comment"] = "Certificate '{}' removed from store: {}".format(
                thumbprint, store_path
            )
        else:
            ret["comment"] = (
                "Certificate '{}' unable to be removed from store: {}".format(
                    thumbprint, store_path
                )
            )
    return ret
