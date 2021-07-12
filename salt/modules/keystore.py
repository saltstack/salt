"""
Module to interact with keystores
"""


import logging
import os
from datetime import datetime

from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

__virtualname__ = "keystore"


try:
    import jks
    import OpenSSL

    has_depends = True
except ImportError:
    has_depends = False


def __virtual__():
    """
    Check dependencies
    """
    if has_depends is False:
        msg = "jks unavailable: {} execution module cant be loaded ".format(
            __virtualname__
        )
        return False, msg
    return __virtualname__


def _parse_cert(alias, public_cert, return_cert=False):
    ASN1 = OpenSSL.crypto.FILETYPE_ASN1
    PEM = OpenSSL.crypto.FILETYPE_PEM
    cert_data = {}
    sha1 = public_cert.digest(b"sha1")

    cert_pem = OpenSSL.crypto.dump_certificate(PEM, public_cert)
    raw_until = public_cert.get_notAfter()
    date_until = datetime.strptime(raw_until, "%Y%m%d%H%M%SZ")
    string_until = date_until.strftime("%B %d %Y")

    raw_start = public_cert.get_notBefore()
    date_start = datetime.strptime(raw_start, "%Y%m%d%H%M%SZ")
    string_start = date_start.strftime("%B %d %Y")

    if return_cert:
        cert_data["pem"] = cert_pem
    cert_data["alias"] = alias
    cert_data["sha1"] = sha1
    cert_data["valid_until"] = string_until
    cert_data["valid_start"] = string_start
    cert_data["expired"] = date_until < datetime.now()

    return cert_data


def list(keystore, passphrase, alias=None, return_cert=False):
    """
    Lists certificates in a keytool managed keystore.


    :param keystore: The path to the keystore file to query
    :param passphrase: The passphrase to use to decode the keystore
    :param alias: (Optional) If found, displays details on only this key
    :param return_certs: (Optional) Also return certificate PEM.

    .. warning::

        There are security implications for using return_cert to return decrypted certificates.

    CLI Example:

    .. code-block:: bash

        salt '*' keystore.list /usr/lib/jvm/java-8/jre/lib/security/cacerts changeit
        salt '*' keystore.list /usr/lib/jvm/java-8/jre/lib/security/cacerts changeit debian:verisign_-_g5.pem

    """
    ASN1 = OpenSSL.crypto.FILETYPE_ASN1
    PEM = OpenSSL.crypto.FILETYPE_PEM
    decoded_certs = []
    entries = []

    keystore = jks.KeyStore.load(keystore, passphrase)

    if alias:
        # If alias is given, look it up and build expected data structure
        entry_value = keystore.entries.get(alias)
        if entry_value:
            entries = [(alias, entry_value)]
    else:
        entries = keystore.entries.items()

    if entries:
        for entry_alias, cert_enc in entries:
            entry_data = {}
            if isinstance(cert_enc, jks.PrivateKeyEntry):
                cert_result = cert_enc.cert_chain[0][1]
                entry_data["type"] = "PrivateKeyEntry"
            elif isinstance(cert_enc, jks.TrustedCertEntry):
                cert_result = cert_enc.cert
                entry_data["type"] = "TrustedCertEntry"
            else:
                raise CommandExecutionError(
                    "Unsupported EntryType detected in keystore"
                )

            # Detect if ASN1 binary, otherwise assume PEM
            if "\x30" in cert_result[0]:
                public_cert = OpenSSL.crypto.load_certificate(ASN1, cert_result)
            else:
                public_cert = OpenSSL.crypto.load_certificate(PEM, cert_result)

            entry_data.update(_parse_cert(entry_alias, public_cert, return_cert))
            decoded_certs.append(entry_data)

    return decoded_certs


def add(name, keystore, passphrase, certificate, private_key=None):
    """
    Adds certificates to an existing keystore or creates a new one if necesssary.

    :param name: alias for the certificate
    :param keystore: The path to the keystore file to query
    :param passphrase: The passphrase to use to decode the keystore
    :param certificate: The PEM public certificate to add to keystore. Can be a string for file.
    :param private_key: (Optional for TrustedCert) The PEM private key to add to the keystore

    CLI Example:

    .. code-block:: bash

        salt '*' keystore.add aliasname /tmp/test.store changeit /tmp/testcert.crt
        salt '*' keystore.add aliasname /tmp/test.store changeit certificate="-----BEGIN CERTIFICATE-----SIb...BM=-----END CERTIFICATE-----"
        salt '*' keystore.add keyname /tmp/test.store changeit /tmp/512.cert private_key=/tmp/512.key

    """
    ASN1 = OpenSSL.crypto.FILETYPE_ASN1
    PEM = OpenSSL.crypto.FILETYPE_PEM
    certs_list = []
    if os.path.isfile(keystore):
        keystore_object = jks.KeyStore.load(keystore, passphrase)
        for alias, loaded_cert in keystore_object.entries.items():
            certs_list.append(loaded_cert)

    try:
        cert_string = __salt__["x509.get_pem_entry"](certificate)
    except SaltInvocationError:
        raise SaltInvocationError(
            "Invalid certificate file or string: {}".format(certificate)
        )

    if private_key:
        # Accept PEM input format, but convert to DES for loading into new keystore
        key_string = __salt__["x509.get_pem_entry"](private_key)
        loaded_cert = OpenSSL.crypto.load_certificate(PEM, cert_string)
        loaded_key = OpenSSL.crypto.load_privatekey(PEM, key_string)
        dumped_cert = OpenSSL.crypto.dump_certificate(ASN1, loaded_cert)
        dumped_key = OpenSSL.crypto.dump_privatekey(ASN1, loaded_key)

        new_entry = jks.PrivateKeyEntry.new(name, [dumped_cert], dumped_key, "rsa_raw")
    else:
        new_entry = jks.TrustedCertEntry.new(name, cert_string)

    certs_list.append(new_entry)

    keystore_object = jks.KeyStore.new("jks", certs_list)
    keystore_object.save(keystore, passphrase)
    return True


def remove(name, keystore, passphrase):
    """
    Removes a certificate from an existing keystore.
    Returns True if remove was successful, otherwise False

    :param name: alias for the certificate
    :param keystore: The path to the keystore file to query
    :param passphrase: The passphrase to use to decode the keystore

    CLI Example:

    .. code-block:: bash

        salt '*' keystore.remove aliasname /tmp/test.store changeit
    """
    certs_list = []
    keystore_object = jks.KeyStore.load(keystore, passphrase)
    for alias, loaded_cert in keystore_object.entries.items():
        if name not in alias:
            certs_list.append(loaded_cert)

    if len(keystore_object.entries) != len(certs_list):
        # Entry has been removed, save keystore updates
        keystore_object = jks.KeyStore.new("jks", certs_list)
        keystore_object.save(keystore, passphrase)
        return True
    else:
        # No alias found, notify user
        return False
