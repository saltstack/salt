# -*- coding: utf-8 -*-
"""
Manage X509 Certificates

.. versionadded:: 2015.8.0

:depends: M2Crypto

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

    salt-minion:
      service.running:
        - enable: True
        - listen:
          - file: /etc/salt/minion.d/signing_policies.conf

    /etc/salt/minion.d/signing_policies.conf:
      file.managed:
        - source: salt://signing_policies.conf

    /etc/pki:
      file.directory

    /etc/pki/issued_certs:
      file.directory

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
        - managed_private_key:
            name: /etc/pki/ca.key
            bits: 4096
            backup: True
        - require:
          - file: /etc/pki

    mine.send:
      module.run:
        - func: x509.get_pem_entries
        - kwargs:
            glob_path: /etc/pki/ca.crt
        - onchanges:
          - x509: /etc/pki/ca.crt


The signing policy defines properties that override any property requested or included in a CRL. It also
can define a restricted list of minions which are allowed to remotely invoke this signing policy.

/srv/salt/signing_policies.conf

.. code-block:: yaml

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
      x509.certificate_managed:
        - ca_server: ca
        - signing_policy: www
        - public_key: /etc/pki/www.key
        - CN: www.example.com
        - days_remaining: 30
        - backup: True
        - managed_private_key:
            name: /etc/pki/www.key
            bits: 4096
            backup: True

"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import copy
import datetime
import os
import re

# Import Salt Libs
import salt.exceptions

# Import 3rd-party libs
from salt.ext import six

try:
    from M2Crypto.RSA import RSAError
except ImportError:
    pass


def __virtual__():
    """
    only load this module if the corresponding execution module is loaded
    """
    if "x509.get_pem_entry" in __salt__:
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
        for rev_name, props in six.iteritems(rev):  # pylint: disable=unused-variable
            dict_ = {}
            for prop in props:
                for propname, val in six.iteritems(prop):
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
    **kwargs
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
        Combining new with :mod:`prereq <salt.states.requsities.preqreq>`, or when used as part of a `managed_private_key` can allow key rotation whenever a new certificate is generated.

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
            name, pem_type="RSA PRIVATE KEY"
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
        old = "{0} is not a valid csr.".format(name)

    file_args, kwargs = _get_file_args(name, **kwargs)
    file_args["contents"] = __salt__["x509.create_csr"](text=True, **kwargs)

    ret = __states__["file.managed"](**file_args)
    if ret["changes"]:
        new = __salt__["x509.read_csr"](file_args["contents"])
        if old != new:
            ret["changes"] = {"Old": old, "New": new}

    return ret


def certificate_managed(
    name, days_remaining=90, managed_private_key=None, append_certs=None, **kwargs
):
    """
    Manage a Certificate

    name
        Path to the certificate

    days_remaining : 90
        The minimum number of days remaining when the certificate should be
        recreated. A value of 0 disables automatic renewal.

    managed_private_key
        Manages the private key corresponding to the certificate. All of the
        arguments supported by :py:func:`x509.private_key_managed
        <salt.states.x509.private_key_managed>` are supported. If `name` is not
        specified or is the same as the name of the certificate, the private
        key and certificate will be written together in the same file.

    append_certs:
        A list of certificates to be appended to the managed file.

    kwargs:
        Any arguments supported by :py:func:`x509.create_certificate
        <salt.modules.x509.create_certificate>` or :py:func:`file.managed
        <salt.states.file.managed>` are supported.

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

    file_args, kwargs = _get_file_args(name, **kwargs)

    rotate_private_key = False
    new_private_key = False
    if managed_private_key:
        private_key_args = {
            "name": name,
            "new": False,
            "overwrite": False,
            "bits": 2048,
            "passphrase": None,
            "cipher": "aes_128_cbc",
            "verbose": True,
        }
        private_key_args.update(managed_private_key)
        kwargs["public_key_passphrase"] = private_key_args["passphrase"]

        if private_key_args["new"]:
            rotate_private_key = True
            private_key_args["new"] = False

        if _check_private_key(
            private_key_args["name"],
            bits=private_key_args["bits"],
            passphrase=private_key_args["passphrase"],
            new=private_key_args["new"],
            overwrite=private_key_args["overwrite"],
        ):
            private_key = __salt__["x509.get_pem_entry"](
                private_key_args["name"], pem_type="RSA PRIVATE KEY"
            )
        else:
            new_private_key = True
            private_key = __salt__["x509.create_private_key"](
                text=True,
                bits=private_key_args["bits"],
                passphrase=private_key_args["passphrase"],
                cipher=private_key_args["cipher"],
                verbose=private_key_args["verbose"],
            )

        kwargs["public_key"] = private_key

    current_days_remaining = 0
    current_comp = {}

    if os.path.isfile(name):
        try:
            current = __salt__["x509.read_certificate"](certificate=name)
            current_comp = copy.deepcopy(current)
            if "serial_number" not in kwargs:
                current_comp.pop("Serial Number")
                if "signing_cert" not in kwargs:
                    try:
                        current_comp["X509v3 Extensions"][
                            "authorityKeyIdentifier"
                        ] = re.sub(
                            r"serial:([0-9A-F]{2}:)*[0-9A-F]{2}",
                            "serial:--",
                            current_comp["X509v3 Extensions"]["authorityKeyIdentifier"],
                        )
                    except KeyError:
                        pass
            current_comp.pop("Not Before")
            current_comp.pop("MD5 Finger Print")
            current_comp.pop("SHA1 Finger Print")
            current_comp.pop("SHA-256 Finger Print")
            current_notafter = current_comp.pop("Not After")
            current_days_remaining = (
                datetime.datetime.strptime(current_notafter, "%Y-%m-%d %H:%M:%S")
                - datetime.datetime.now()
            ).days
            if days_remaining == 0:
                days_remaining = current_days_remaining - 1
        except salt.exceptions.SaltInvocationError:
            current = "{0} is not a valid Certificate.".format(name)
    else:
        current = "{0} does not exist.".format(name)

    if "ca_server" in kwargs and "signing_policy" not in kwargs:
        raise salt.exceptions.SaltInvocationError(
            "signing_policy must be specified if ca_server is."
        )

    new = __salt__["x509.create_certificate"](testrun=True, **kwargs)

    if isinstance(new, dict):
        new_comp = copy.deepcopy(new)
        new.pop("Issuer Public Key")
        if "serial_number" not in kwargs:
            new_comp.pop("Serial Number")
            if "signing_cert" not in kwargs:
                try:
                    new_comp["X509v3 Extensions"]["authorityKeyIdentifier"] = re.sub(
                        r"serial:([0-9A-F]{2}:)*[0-9A-F]{2}",
                        "serial:--",
                        new_comp["X509v3 Extensions"]["authorityKeyIdentifier"],
                    )
                except KeyError:
                    pass
        new_comp.pop("Not Before")
        new_comp.pop("Not After")
        new_comp.pop("MD5 Finger Print")
        new_comp.pop("SHA1 Finger Print")
        new_comp.pop("SHA-256 Finger Print")
        new_issuer_public_key = new_comp.pop("Issuer Public Key")
    else:
        new_comp = new

    new_certificate = False
    if (
        current_comp == new_comp
        and current_days_remaining > days_remaining
        and __salt__["x509.verify_signature"](name, new_issuer_public_key)
    ):
        certificate = __salt__["x509.get_pem_entry"](name, pem_type="CERTIFICATE")
    else:
        if rotate_private_key and not new_private_key:
            new_private_key = True
            private_key = __salt__["x509.create_private_key"](
                text=True,
                bits=private_key_args["bits"],
                verbose=private_key_args["verbose"],
            )
            kwargs["public_key"] = private_key
        new_certificate = True
        certificate = __salt__["x509.create_certificate"](text=True, **kwargs)

    file_args["contents"] = ""
    private_ret = {}
    if managed_private_key:
        if private_key_args["name"] == name:
            file_args["contents"] = private_key
        else:
            private_file_args = copy.deepcopy(file_args)
            unique_private_file_args, _ = _get_file_args(**private_key_args)
            private_file_args.update(unique_private_file_args)
            private_file_args["contents"] = private_key
            private_ret = __states__["file.managed"](**private_file_args)
            if not private_ret["result"]:
                return private_ret

    file_args["contents"] += salt.utils.stringutils.to_str(certificate)

    if not append_certs:
        append_certs = []
    for append_cert in append_certs:
        file_args["contents"] += __salt__["x509.get_pem_entry"](
            append_cert, pem_type="CERTIFICATE"
        )

    file_args["show_changes"] = False
    ret = __states__["file.managed"](**file_args)

    if ret["changes"]:
        ret["changes"] = {"Certificate": ret["changes"]}
    else:
        ret["changes"] = {}
    if private_ret and private_ret["changes"]:
        ret["changes"]["Private Key"] = private_ret["changes"]
    if new_private_key:
        ret["changes"]["Private Key"] = "New private key generated"
    if new_certificate:
        ret["changes"]["Certificate"] = {
            "Old": current,
            "New": __salt__["x509.read_certificate"](certificate=certificate),
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
    **kwargs
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
            current = "{0} is not a valid CRL.".format(name)
    else:
        current = "{0} does not exist.".format(name)

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
