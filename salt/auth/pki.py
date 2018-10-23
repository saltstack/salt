# -*- coding: utf-8 -*-
# Majority of code shamelessly stolen from
# http://www.v13.gr/blog/?p=303
'''
Authenticate via a PKI certificate.

.. note::

    This module is Experimental and should be used with caution

Provides an authenticate function that will allow the caller to authenticate
a user via their public cert against a pre-defined Certificate Authority.

TODO: Add a 'ca_dir' option to configure a directory of CA files, a la Apache.

:depends:    - pyOpenSSL module
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import third party libs
# pylint: disable=import-error
try:
    try:
        from M2Crypto import X509
        HAS_M2 = True
    except ImportError:
        HAS_M2 = False
        try:
            from Cryptodome.Util import asn1
        except ImportError:
            from Crypto.Util import asn1
        import OpenSSL
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
# pylint: enable=import-error

# Import salt libs
import salt.utils.files

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Requires newer pycrypto and pyOpenSSL
    '''
    if HAS_DEPS:
        return True
    return False


def auth(username, password, **kwargs):
    '''
    Returns True if the given user cert (password is the cert contents)
    was issued by the CA and if cert's Common Name is equal to username.

    Returns False otherwise.

    ``username``: we need it to run the auth function from CLI/API;
                  it should be in master config auth/acl
    ``password``: contents of user certificate (pem-encoded user public key);
                  why "password"? For CLI, it's the only available name

    Configure the CA cert in the master config file:

    .. code-block:: yaml

        external_auth:
          pki:
            ca_file: /etc/pki/tls/ca_certs/trusted-ca.crt
            your_user:
              - .*
    '''
    pem = password
    cacert_file = __salt__['config.get']('external_auth:pki:ca_file')

    log.debug('Attempting to authenticate via pki.')
    log.debug('Using CA file: %s', cacert_file)
    log.debug('Certificate contents: %s', pem)

    if HAS_M2:
        cert = X509.load_cert_string(pem, X509.FORMAT_PEM)
        cacert = X509.load_cert(cacert_file, X509.FORMAT_PEM)
        if cert.verify(cacert.get_pubkey()):
            log.info('Successfully authenticated certificate: {0}'.format(pem))
            return True
        else:
            log.info('Failed to authenticate certificate: {0}'.format(pem))
            return False

    c = OpenSSL.crypto
    cert = c.load_certificate(c.FILETYPE_PEM, pem)

    with salt.utils.files.fopen(cacert_file) as f:
        cacert = c.load_certificate(c.FILETYPE_PEM, f.read())

    # Get the signing algorithm
    algo = cert.get_signature_algorithm()

    # Get the ASN1 format of the certificate
    cert_asn1 = c.dump_certificate(c.FILETYPE_ASN1, cert)

    # Decode the certificate
    der = asn1.DerSequence()
    der.decode(cert_asn1)

    # The certificate has three parts:
    # - certificate
    # - signature algorithm
    # - signature
    # http://usefulfor.com/nothing/2009/06/10/x509-certificate-basics/
    der_cert = der[0]
    #der_algo = der[1]
    der_sig = der[2]

    # The signature is a BIT STRING (Type 3)
    # Decode that as well
    der_sig_in = asn1.DerObject()
    der_sig_in.decode(der_sig)

    # Get the payload
    sig0 = der_sig_in.payload

    # Do the following to see a validation error for tests
    # der_cert=der_cert[:20]+'1'+der_cert[21:]

    # First byte is the number of unused bits. This should be 0
    # http://msdn.microsoft.com/en-us/library/windows/desktop/bb540792(v=vs.85).aspx
    if sig0[0] != '\x00':
        raise Exception('Number of unused bits is strange')
    # Now get the signature itself
    sig = sig0[1:]

    # And verify the certificate
    try:
        c.verify(cacert, sig, der_cert, algo)
        assert dict(cert.get_subject().get_components())['CN'] == username, "Certificate's CN should match the username"
        log.info('Successfully authenticated certificate: %s', pem)
        return True
    except (OpenSSL.crypto.Error, AssertionError):
        log.info('Failed to authenticate certificate: %s', pem)
    return False
