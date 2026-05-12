"""
Manage X509 Certificates

.. versionadded:: 2015.8.0

:depends: M2Crypto

.. deprecated:: 3006.0

.. warning::
    This module has been deprecated and will be removed
    in Salt 3009 (Potassium). Please migrate to the replacement
    modules. For breaking changes between both versions,
    you can refer to the :ref:`x509_v2 execution module docs <x509-setup>`.

    They have become the default ``x509`` modules in Salt 3008.0 (Argon).
    Until they are removed, you can still revert to the deprecated modules
    by setting ``features: {x509_v2: false}`` in your minion configuration.


This module can enable managing a complete PKI infrastructure including creating private keys, CAs,
certificates and CRLs. It includes the ability to generate a private key on a server, and have the
corresponding public key sent to a remote CA to create a CA signed certificate. This can be done in
a secure manner, where private keys are always generated locally and never moved across the network.

Here is a simple example scenario. In this example ``ca`` is the ca server,
and ``www`` is a web server that needs a certificate signed by ``ca``.

For remote signing, peers must be permitted to remotely call the
:mod:`sign_remote_certificate <salt.modules.x509.sign_remote_certificate>` function.


/etc/salt/master.d/peer.conf

.. code-block:: yaml

    peer:
      .*:
        - x509.sign_remote_certificate


/srv/salt/top.sls

.. code-block:: yaml

    base:
      '*':
        - cert
      'ca':
        - ca
      'www':
        - www


This state creates the CA key, certificate and signing policy. It also publishes the certificate to
the mine where it can be easily retrieved by other minions.

/srv/salt/ca.sls

.. code-block:: yaml

    /etc/salt/minion.d/x509.conf:
      file.managed:
        - source: salt://x509.conf

    restart-salt-minion:
      cmd.run:
        - name: 'salt-call service.restart salt-minion'
        - bg: True
        - onchanges:
          - file: /etc/salt/minion.d/x509.conf

    /etc/pki:
      file.directory

    /etc/pki/issued_certs:
      file.directory

    /etc/pki/ca.key:
      x509.private_key_managed:
        - bits: 4096
        - backup: True

    /etc/pki/ca.crt:
      x509.certificate_managed:
        - signing_private_key: /etc/pki/ca.key
        - CN: ca.example.com
        - C: US
        - ST: Utah
        - L: Salt Lake City
        - basicConstraints: "critical CA:true"
        - keyUsage: "critical cRLSign, keyCertSign"
        - subjectKeyIdentifier: hash
        - authorityKeyIdentifier: keyid,issuer:always
        - days_valid: 3650
        - days_remaining: 0
        - backup: True
        - require:
          - file: /etc/pki


The signing policy defines properties that override any property requested or included in a CRL. It also
can define a restricted list of minions which are allowed to remotely invoke this signing policy.

/srv/salt/x509.conf

.. code-block:: yaml

    mine_functions:
      x509.get_pem_entries: [/etc/pki/ca.crt]

    x509_signing_policies:
      www:
        - minions: 'www'
        - signing_private_key: /etc/pki/ca.key
        - signing_cert: /etc/pki/ca.crt
        - C: US
        - ST: Utah
        - L: Salt Lake City
        - basicConstraints: "critical CA:false"
        - keyUsage: "critical keyEncipherment"
        - subjectKeyIdentifier: hash
        - authorityKeyIdentifier: keyid,issuer:always
        - days_valid: 90
        - copypath: /etc/pki/issued_certs/


This state will instruct all minions to trust certificates signed by our new CA.
Using Jinja to strip newlines from the text avoids dealing with newlines in the rendered YAML,
and the  :mod:`sign_remote_certificate <salt.states.x509.sign_remote_certificate>` state will
handle properly formatting the text before writing the output.

/srv/salt/cert.sls

.. code-block:: jinja

    /usr/local/share/ca-certificates:
      file.directory

    /usr/local/share/ca-certificates/intca.crt:
      x509.pem_managed:
        - text: {{ salt['mine.get']('ca', 'x509.get_pem_entries')['ca']['/etc/pki/ca.crt']|replace('\\n', '') }}


This state creates a private key then requests a certificate signed by ca according to the www policy.

/srv/salt/www.sls

.. code-block:: yaml

    /etc/pki/www.crt:
      x509.private_key_managed:
        - name: /etc/pki/www.key
        - bits: 4096
        - backup: True

    /etc/pki/www.crt:
      x509.certificate_managed:
        - ca_server: ca
        - signing_policy: www
        - public_key: /etc/pki/www.key
        - CN: www.example.com
        - days_remaining: 30
        - backup: True

This other state creates a private key then requests a certificate signed by ca
according to the www policy but adds a strict date range for the certificate to
be considered valid.

/srv/salt/www-time-limited.sls

.. code-block:: yaml

    /etc/pki/www-time-limited.crt:
      x509.certificate_managed:
        - ca_server: ca
        - signing_policy: www
        - public_key: /etc/pki/www-time-limited.key
        - CN: www.example.com
        - not_before: 2019-05-05 00:00:00
        - not_after: 2020-05-05 14:30:00
        - backup: True

"""

import copy
import datetime
import logging
import os
import re

import salt.exceptions
import salt.utils.versions

try:
    from M2Crypto.RSA import RSAError
except ImportError:
    pass

log = logging.getLogger(__name__)


def __virtual__():
    """
    only load this module if the corresponding execution module is loaded
    """
    if __opts__["features"].get("x509_v2", True):
        return (False, "Superseded, using x509_v2")
    if "x509.get_pem_entry" in __salt__:
        salt.utils.versions.warn_until(
            3009,
            "The x509 modules are deprecated. Please migrate to the replacement "
            "modules (x509_v2). They are the default from Salt 3008 (Argon) onwards.",
        )
        return "x509"
    else:
        return (False, "Could not load x509 state: m2crypto unavailable")


def _revoked_to_list(revs):
    """
    Turn the mess of OrderedDicts and Lists into a list of dicts for
    use in the CRL module.
    """
    list_ = []

    for rev in revs:
        for props in rev.values():
            dict_ = {}
            for prop in props:
                for propname, val in prop.items():
                    if isinstance(val, datetime.datetime):
                        val = val.strftime("%Y-%m-%d %H:%M:%S")
                    dict_[propname] = val
            list_.append(dict_)

    return list_


def _get_file_args(name, **kwargs):
    valid_file_args = [
        "user",
        "group",
        "mode",
        "makedirs",
        "dir_mode",
        "backup",
        "create",
        "follow_symlinks",
        "check_cmd",
    ]
    file_args = {}
    extra_args = {}
    for k, v in kwargs.items():
        if k in valid_file_args:
            file_args[k] = v
        else:
            extra_args[k] = v
    file_args["name"] = name
    return file_args, extra_args


def _check_private_key(name, bits=2048, passphrase=None, new=False, overwrite=False):
    current_bits = 0
    if os.path.isfile(name):
        try:
            current_bits = __salt__["x509.get_private_key_size"](
                private_key=name, passphrase=passphrase
            )
        except salt.exceptions.SaltInvocationError:
            pass
        except RSAError:
            if not overwrite:
                raise salt.exceptions.CommandExecutionError(
                    "The provided passphrase cannot decrypt the private key."
                )

    return current_bits == bits and not new


def private_key_managed(
    name,
    bits=2048,
    passphrase=None,
    cipher="aes_128_cbc",
    new=False,
    overwrite=False,
    verbose=True,
    **kwargs,
):
    """
    Manage a private key's existence.

    name:
        Path to the private key

    bits:
        Key length in bits. Default 2048.

    passphrase:
        Passphrase for encrypting the private key.

    cipher:
        Cipher for encrypting the private key.

    new:
        Always create a new key. Defaults to ``False``.
        Combining new with :mod:`prereq <salt.states.requsities.preqreq>`
        can allow key rotation whenever a new certificate is generated.

    overwrite:
        Overwrite an existing private key if the provided passphrase cannot decrypt it.

    verbose:
        Provide visual feedback on stdout, dots while key is generated.
        Default is True.

        .. versionadded:: 2016.11.0

    kwargs:
        Any kwargs supported by file.managed are supported.

    Example:

    The JINJA templating in this example ensures a private key is generated if the file doesn't exist
    and that a new private key is generated whenever the certificate that uses it is to be renewed.

    .. code-block:: jinja

        /etc/pki/www.key:
          x509.private_key_managed:
            - bits: 4096
            - new: True
            {% if salt['file.file_exists']('/etc/pki/www.key') -%}
            - prereq:
              - x509: /etc/pki/www.crt
            {%- endif %}
    """
    file_args, kwargs = _get_file_args(name, **kwargs)
    new_key = False
    if _check_private_key(
        name, bits=bits, passphrase=passphrase, new=new, overwrite=overwrite
    ):
        file_args["contents"] = __salt__["x509.get_pem_entry"](
            name, pem_type="(?:RSA )?PRIVATE KEY"
        )
    else:
        new_key = True
        file_args["contents"] = __salt__["x509.create_private_key"](
            text=True, bits=bits, passphrase=passphrase, cipher=cipher, verbose=verbose
        )

    # Ensure the key contents are a string before passing it along
    file_args["contents"] = salt.utils.stringutils.to_str(file_args["contents"])

    ret = __states__["file.managed"](**file_args)
    if ret["changes"] and new_key:
        ret["changes"] = {"new": "New private key generated"}

    return ret


def csr_managed(name, **kwargs):
    """
    Manage a Certificate Signing Request

    name:
        Path to the CSR

    properties:
        The properties to be added to the certificate request, including items like subject, extensions
        and public key. See above for valid properties.

    kwargs:
        Any arguments supported by :py:func:`file.managed <salt.states.file.managed>` are supported.

    Example:

    .. code-block:: yaml

        /etc/pki/mycert.csr:
          x509.csr_managed:
             - private_key: /etc/pki/mycert.key
             - CN: www.example.com
             - C: US
             - ST: Utah
             - L: Salt Lake City
             - keyUsage: 'critical dataEncipherment'
    """
    try:
        old = __salt__["x509.read_csr"](name)
    except salt.exceptions.SaltInvocationError:
        old = f"{name} is not a valid csr."

    file_args, kwargs = _get_file_args(name, **kwargs)
    file_args["contents"] = __salt__["x509.create_csr"](text=True, **kwargs)

    ret = __states__["file.managed"](**file_args)
    if ret["changes"]:
        new = __salt__["x509.read_csr"](file_args["contents"])
        if old != new:
            ret["changes"] = {"Old": old, "New": new}

    return ret


def _certificate_info_matches(cert_info, required_cert_info, check_serial=False):
    """
    Return true if the provided certificate information matches the
    required certificate information, i.e. it has the required common
    name, subject alt name, organization, etc.

    cert_info should be a dict as returned by x509.read_certificate.
    required_cert_info should be a dict as returned by x509.create_certificate with testrun=True.
    """
    # don't modify the incoming dicts
    cert_info = copy.deepcopy(cert_info)
    required_cert_info = copy.deepcopy(required_cert_info)

    ignored_keys = [
        "Not Before",
        "Not After",
        "SHA1 Finger Print",
        "SHA-256 Finger Print",
        # The integrity of the issuer is checked elsewhere
        "Issuer Public Key",
    ]
    if __opts__["fips_mode"] is False:
        ignored_keys.append("MD5 Finger Print")
    for key in ignored_keys:
        cert_info.pop(key, None)
        required_cert_info.pop(key, None)

    if not check_serial:
        cert_info.pop("Serial Number", None)
        required_cert_info.pop("Serial Number", None)
        try:
            cert_info["X509v3 Extensions"]["authorityKeyIdentifier"] = re.sub(
                r"serial:([0-9A-F]{2}:)*[0-9A-F]{2}",
                "serial:--",
                cert_info["X509v3 Extensions"]["authorityKeyIdentifier"],
            )
            required_cert_info["X509v3 Extensions"]["authorityKeyIdentifier"] = re.sub(
                r"serial:([0-9A-F]{2}:)*[0-9A-F]{2}",
                "serial:--",
                required_cert_info["X509v3 Extensions"]["authorityKeyIdentifier"],
            )
        except KeyError:
            pass

    diff = []
    for k, v in required_cert_info.items():
        # cert info comes as byte string
        if isinstance(v, str):
            v = salt.utils.stringutils.to_bytes(v)
        try:
            if v != cert_info[k]:
                if k == "Subject Hash":
                    # If we failed the subject hash check but the subject matches, then this is
                    # likely a certificate generated under Python 2 where sorting differs and thus
                    # the hash also differs
                    if required_cert_info["Subject"] != cert_info["Subject"]:
                        diff.append(k)
                elif k == "Issuer Hash":
                    # If we failed the issuer hash check but the issuer matches, then this is
                    # likely a certificate generated under Python 2 where sorting differs and thus
                    # the hash also differs
                    if required_cert_info["Issuer"] != cert_info["Issuer"]:
                        diff.append(k)
                elif k == "X509v3 Extensions":
                    v_ext = v.copy()
                    cert_info_ext = cert_info[k].copy()
                    # DirName depends on ordering which was different on certificates created
                    # under Python 2. Remove that from the comparisson
                    try:
                        v_ext["authorityKeyIdentifier"] = re.sub(
                            r"DirName:([^\n]+)",
                            "Dirname:--",
                            v_ext["authorityKeyIdentifier"],
                        )
                        cert_info_ext["authorityKeyIdentifier"] = re.sub(
                            r"DirName:([^\n]+)",
                            "Dirname:--",
                            cert_info_ext["authorityKeyIdentifier"],
                        )
                    except KeyError:
                        pass
                    if v_ext != cert_info_ext:
                        diff.append(k)
                else:
                    diff.append(k)
        except KeyError:
            diff.append(k)

    return len(diff) == 0, diff


def _certificate_days_remaining(cert_info):
    """
    Get the days remaining on a certificate, defaulting to 0 if an error occurs.
    """
    try:
        expiry = cert_info["Not After"]
        return (
            datetime.datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            - datetime.datetime.now()
        ).days
    except KeyError:
        return 0


def _certificate_is_valid(name, days_remaining, append_certs, **cert_spec):
    """
    Return True if the given certificate file exists, is a certificate, matches the given specification,
    and has the required days remaining.

    If False, also provide a message explaining why.
    """
    if not os.path.isfile(name):
        return False, f"{name} does not exist", {}

    try:
        cert_info = __salt__["x509.read_certificate"](certificate=name)
        required_cert_info = __salt__["x509.create_certificate"](
            testrun=True, **cert_spec
        )
        if not isinstance(required_cert_info, dict):
            raise salt.exceptions.SaltInvocationError(
                "Unable to create new certificate: x509 module error: {}".format(
                    required_cert_info
                )
            )

        try:
            issuer_public_key = required_cert_info["Issuer Public Key"]
            # Verify the certificate has been signed by the ca_server or private_signing_key
            if not __salt__["x509.verify_signature"](name, issuer_public_key):
                errmsg = (
                    "Certificate is not signed by private_signing_key"
                    if "signing_private_key" in cert_spec
                    else "Certificate is not signed by the requested issuer"
                )
                return False, errmsg, cert_info
        except KeyError:
            return (
                False,
                "New certificate does not include signing information",
                cert_info,
            )

        matches, diff = _certificate_info_matches(
            cert_info, required_cert_info, check_serial="serial_number" in cert_spec
        )
        if not matches:
            return (
                False,
                "Certificate properties are different: {}".format(", ".join(diff)),
                cert_info,
            )

        actual_days_remaining = _certificate_days_remaining(cert_info)
        if days_remaining != 0 and actual_days_remaining < days_remaining:
            return (
                False,
                "Certificate needs renewal: {} days remaining but it needs to be at"
                " least {}".format(actual_days_remaining, days_remaining),
                cert_info,
            )

        return True, "", cert_info
    except salt.exceptions.SaltInvocationError as e:
        return False, f"{name} is not a valid certificate: {str(e)}", {}


def _certificate_file_managed(ret, file_args):
    """
    Run file.managed and merge the result with an existing return dict.
    The overall True/False result will be the result of the file.managed call.
    """
    file_ret = __states__["file.managed"](**file_args)

    ret["result"] = file_ret["result"]
    if ret["result"]:
        ret["comment"] = "Certificate {} is valid and up to date".format(ret["name"])
    else:
        ret["comment"] = file_ret["comment"]

    if file_ret["changes"]:
        ret["changes"] = {"File": file_ret["changes"]}

    return ret


def certificate_managed(name, days_remaining=90, append_certs=None, **kwargs):
    """
    Manage a Certificate

    name
        Path to the certificate

    days_remaining : 90
        Recreate the certificate if the number of days remaining on it
        are less than this number. The value should be less than
        ``days_valid``, otherwise the certificate will be recreated
        every time the state is run. A value of 0 disables automatic
        renewal.

    append_certs:
        A list of certificates to be appended to the managed file.
        They must be valid PEM files, otherwise an error will be thrown.

    kwargs:
        Any arguments supported by :py:func:`x509.create_certificate
        <salt.modules.x509.create_certificate>` or :py:func:`file.managed
        <salt.states.file.managed>` are supported.

    not_before:
        Initial validity date for the certificate. This date must be specified
        in the format '%Y-%m-%d %H:%M:%S'.

        .. versionadded:: 3001
    not_after:
        Final validity date for the certificate. This date must be specified in
        the format '%Y-%m-%d %H:%M:%S'.

        .. versionadded:: 3001

    Examples:

    .. code-block:: yaml

        /etc/pki/ca.crt:
          x509.certificate_managed:
            - signing_private_key: /etc/pki/ca.key
            - CN: ca.example.com
            - C: US
            - ST: Utah
            - L: Salt Lake City
            - basicConstraints: "critical CA:true"
            - keyUsage: "critical cRLSign, keyCertSign"
            - subjectKeyIdentifier: hash
            - authorityKeyIdentifier: keyid,issuer:always
            - days_valid: 3650
            - days_remaining: 0
            - backup: True


    .. code-block:: yaml

        /etc/ssl/www.crt:
          x509.certificate_managed:
            - ca_server: pki
            - signing_policy: www
            - public_key: /etc/ssl/www.key
            - CN: www.example.com
            - days_valid: 90
            - days_remaining: 30
            - backup: True

    """
    if "path" in kwargs:
        name = kwargs.pop("path")

    if "ca_server" in kwargs and "signing_policy" not in kwargs:
        raise salt.exceptions.SaltInvocationError(
            "signing_policy must be specified if ca_server is."
        )

    if (
        "public_key" not in kwargs
        and "signing_private_key" not in kwargs
        and "csr" not in kwargs
    ):
        raise salt.exceptions.SaltInvocationError(
            "public_key, signing_private_key, or csr must be specified."
        )

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    is_valid, invalid_reason, current_cert_info = _certificate_is_valid(
        name, days_remaining, append_certs, **kwargs
    )

    if is_valid:
        file_args, extra_args = _get_file_args(name, **kwargs)

        return _certificate_file_managed(ret, file_args)

    if __opts__["test"]:
        file_args, extra_args = _get_file_args(name, **kwargs)
        # Use empty contents for file.managed in test mode.
        # We don't want generate a new certificate, even in memory,
        # for security reasons.
        # Using an empty string instead of omitting it will at least
        # show the old certificate in the diff.
        file_args["contents"] = ""

        ret = _certificate_file_managed(ret, file_args)

        ret["result"] = None
        ret["comment"] = f"Certificate {name} will be created"
        ret["changes"]["Status"] = {
            "Old": invalid_reason,
            "New": "Certificate will be valid and up to date",
        }
        return ret

    contents = __salt__["x509.create_certificate"](text=True, **kwargs)
    # Check the module actually returned a cert and not an error message as a string
    try:
        __salt__["x509.read_certificate"](contents)
    except salt.exceptions.SaltInvocationError as e:
        ret["result"] = False
        ret["comment"] = (
            "An error occurred creating the certificate {}. The result returned from"
            " x509.create_certificate is not a valid PEM file:\n{}".format(name, str(e))
        )
        return ret

    if not append_certs:
        append_certs = []
    for append_file in append_certs:
        try:
            append_file_contents = __salt__["x509.get_pem_entry"](
                append_file, pem_type="CERTIFICATE"
            )
            contents += append_file_contents
        except salt.exceptions.SaltInvocationError as e:
            ret["result"] = False
            ret["comment"] = (
                "{} is not a valid certificate file, cannot append it to the"
                " certificate {}.\nThe error returned by the x509 module was:\n{}".format(
                    append_file, name, str(e)
                )
            )
            return ret

    file_args, extra_args = _get_file_args(name, **kwargs)
    file_args["contents"] = contents

    ret = _certificate_file_managed(ret, file_args)

    if ret["result"]:
        ret["changes"]["Certificate"] = {
            "Old": current_cert_info,
            "New": __salt__["x509.read_certificate"](certificate=name),
        }
        ret["changes"]["Status"] = {
            "Old": invalid_reason,
            "New": "Certificate is valid and up to date",
        }

    return ret


def crl_managed(
    name,
    signing_private_key,
    signing_private_key_passphrase=None,
    signing_cert=None,
    revoked=None,
    days_valid=100,
    digest="",
    days_remaining=30,
    include_expired=False,
    **kwargs,
):
    """
    Manage a Certificate Revocation List

    name
        Path to the certificate

    signing_private_key
        The private key that will be used to sign the CRL. This is
        usually your CA's private key.

    signing_private_key_passphrase
        Passphrase to decrypt the private key.

    signing_cert
        The certificate of the authority that will be used to sign the CRL.
        This is usually your CA's certificate.

    revoked
        A list of certificates to revoke. Must include either a serial number or a
        the certificate itself. Can optionally include the revocation date and
        notAfter date from the certificate. See example below for details.

    days_valid : 100
        The number of days the certificate should be valid for.

    digest
        The digest to use for signing the CRL. This has no effect on versions
        of pyOpenSSL less than 0.14.

    days_remaining : 30
        The CRL should be automatically recreated if there are less than
        ``days_remaining`` days until the CRL expires. Set to 0 to disable
        automatic renewal.

    include_expired : False
        If ``True``, include expired certificates in the CRL.

    kwargs
        Any arguments supported by :py:func:`file.managed <salt.states.file.managed>` are supported.

    Example:

    .. code-block:: yaml

        /etc/pki/ca.crl:
          x509.crl_managed:
            - signing_private_key: /etc/pki/myca.key
            - signing_cert: /etc/pki/myca.crt
            - revoked:
              - compromized_Web_key:
                - certificate: /etc/pki/certs/badweb.crt
                - revocation_date: 2015-03-01 00:00:00
                - reason: keyCompromise
              - terminated_vpn_user:
                - serial_number: D6:D2:DC:D8:4D:5C:C0:F4
                - not_after: 2016-01-01 00:00:00
                - revocation_date: 2015-02-25 00:00:00
                - reason: cessationOfOperation
    """
    if revoked is None:
        revoked = []

    revoked = _revoked_to_list(revoked)

    current_days_remaining = 0
    current_comp = {}

    if os.path.isfile(name):
        try:
            current = __salt__["x509.read_crl"](crl=name)
            current_comp = current.copy()
            current_comp.pop("Last Update")
            current_notafter = current_comp.pop("Next Update")
            current_days_remaining = (
                datetime.datetime.strptime(current_notafter, "%Y-%m-%d %H:%M:%S")
                - datetime.datetime.now()
            ).days
            if days_remaining == 0:
                days_remaining = current_days_remaining - 1
        except salt.exceptions.SaltInvocationError:
            current = f"{name} is not a valid CRL."
    else:
        current = f"{name} does not exist."

    new_crl = __salt__["x509.create_crl"](
        text=True,
        signing_private_key=signing_private_key,
        signing_private_key_passphrase=signing_private_key_passphrase,
        signing_cert=signing_cert,
        revoked=revoked,
        days_valid=days_valid,
        digest=digest,
        include_expired=include_expired,
    )

    new = __salt__["x509.read_crl"](crl=new_crl)
    new_comp = new.copy()
    new_comp.pop("Last Update")
    new_comp.pop("Next Update")

    file_args, kwargs = _get_file_args(name, **kwargs)
    new_crl_created = False
    if (
        current_comp == new_comp
        and current_days_remaining > days_remaining
        and __salt__["x509.verify_crl"](name, signing_cert)
    ):
        file_args["contents"] = __salt__["x509.get_pem_entry"](
            name, pem_type="X509 CRL"
        )
    else:
        new_crl_created = True
        file_args["contents"] = new_crl

    ret = __states__["file.managed"](**file_args)
    if new_crl_created:
        ret["changes"] = {"Old": current, "New": __salt__["x509.read_crl"](crl=new_crl)}
    return ret


def pem_managed(name, text, backup=False, **kwargs):
    """
    Manage the contents of a PEM file directly with the content in text, ensuring correct formatting.

    name:
        The path to the file to manage

    text:
        The PEM formatted text to write.

    kwargs:
        Any arguments supported by :py:func:`file.managed <salt.states.file.managed>` are supported.
    """
    file_args, kwargs = _get_file_args(name, **kwargs)
    file_args["contents"] = __salt__["x509.get_pem_entry"](text=text)

    return __states__["file.managed"](**file_args)
