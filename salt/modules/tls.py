# -*- coding: utf-8 -*-
'''
A salt module for SSL/TLS.
Can create a Certificate Authority (CA)
or use Self-Signed certificates.

:depends:   - PyOpenSSL Python module
:configuration: Add the following values in /etc/salt/minion for the CA module
    to function properly::

        ca.cert_base_path: '/etc/pki'
'''

# pylint: disable=C0103

# Import python libs
import os
import time
import datetime
import logging
import hashlib

HAS_SSL = False
try:
    import OpenSSL
    HAS_SSL = True
except ImportError:
    pass

# Import salt libs
import salt.utils


log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if the ca config options are set
    '''
    if HAS_SSL:
        return True
    return False


def cert_base_path(cacert_path=None):
    '''
    Return the base path for certs from CLI or from options

    cacert_path
        absolute path to ca certificates root directory

    CLI Example:

    .. code-block:: bash

        salt '*' tls.cert_base_path
    '''
    if not cacert_path:
        cacert_path = __salt__['config.option']('ca.contextual_cert_base_path')
    if not cacert_path:
        cacert_path = __salt__['config.option']('ca.cert_base_path')
    return cacert_path


def _cert_base_path(cacert_path=None):
    '''
    Retrocompatible wrapper
    '''
    return cert_base_path(cacert_path)


def set_ca_path(cacert_path):
    '''
    If wanted, store the aforementioned cacert_path in context
    to be used as the basepath for further operations

    CLI Example:

    .. code-block:: bash

        salt '*' tls.set_ca_path /etc/certs
    '''
    if cacert_path:
        __opts__['ca.contextual_cert_base_path'] = cacert_path
    return cert_base_path()


def _new_serial(ca_name, CN):
    '''
    Return a serial number in hex using md5sum, based upon the ca_name and
    CN values

    ca_name
        name of the CA
    CN
        common name in the request
    '''
    opts_hash_type = __opts__.get('hash_type', 'md5')
    hashtype = getattr(hashlib, opts_hash_type)
    hashnum = int(
            hashtype(
                '{0}_{1}_{2}'.format(
                    ca_name,
                    CN,
                    int(time.time()))
                ).hexdigest(),
            16
            )
    log.debug('Hashnum: {0}'.format(hashnum))

    # record the hash somewhere
    cachedir = __opts__['cachedir']
    log.debug('cachedir: {0}'.format(cachedir))
    serial_file = '{0}/{1}.serial'.format(cachedir, ca_name)
    with salt.utils.fopen(serial_file, 'a+') as ofile:
        ofile.write(str(hashnum))

    return hashnum


def _write_cert_to_database(ca_name, cert, cacert_path=None):
    '''
    write out the index.txt database file in the appropriate directory to
    track certificates

    ca_name
        name of the CA
    cert
        certificate to be recorded
    cacert_path
        absolute path to ca certificates root directory
    '''
    set_ca_path(cacert_path)
    index_file = "{0}/{1}/index.txt".format(cert_base_path(),
                                            ca_name)

    expire_date = cert.get_notAfter()
    serial_number = cert.get_serial_number()

    #gotta prepend a /
    subject = '/'

    # then we can add the rest of the subject
    subject += '/'.join(
            ['{0}={1}'.format(
                x, y
                ) for x, y in cert.get_subject().get_components()]
            )
    subject += '\n'

    index_data = 'V\t{0}\t\t{1}\tunknown\t{2}'.format(
            expire_date,
            serial_number,
            subject
            )

    with salt.utils.fopen(index_file, 'a+') as ofile:
        ofile.write(index_data)


def maybe_fix_ssl_version(ca_name, cacert_path=None):
    '''
    Check that the X509 version is correct
    (was incorrectly set in previous salt versions).
    This will fix the version if needed.

    ca_name
        ca authority name
    cacert_path
        absolute path to ca certificates root directory

    CLI Example:

    .. code-block:: bash

        salt '*' tls.maybe_fix_ssl_version test_ca /etc/certs
    '''
    set_ca_path(cacert_path)
    certp = '{0}/{1}/{2}_ca_cert.crt'.format(
        cert_base_path(),
            ca_name,
            ca_name)
    ca_keyp = '{0}/{1}/{2}_ca_cert.key'.format(
        cert_base_path(), ca_name, ca_name)
    with open(certp) as fic:
        cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM,
                                               fic.read())
        if cert.get_version() == 3:
            log.info(
                'Regenerating wrong x509 version '
                'for certificate {0}'.format(certp))
            with open(ca_keyp) as fic2:
                try:
                    # try to determine the key bits
                    key = OpenSSL.crypto.load_privatekey(
                        OpenSSL.crypto.FILETYPE_PEM, fic2.read())
                    bits = key.bits()
                except Exception:
                    bits = 2048
                try:
                    days = (datetime.datetime.strptime(cert.get_notAfter(),
                                                       '%Y%m%d%H%M%SZ') -
                            datetime.datetime.now()).days
                except (ValueError, TypeError):
                    days = 365
                subj = cert.get_subject()
                create_ca(
                    ca_name,
                    bits=bits,
                    days=days,
                    CN=subj.CN,
                    C=subj.C,
                    ST=subj.ST,
                    L=subj.L,
                    O=subj.O,
                    OU=subj.OU,
                    emailAddress=subj.emailAddress,
                    fixmode=True)


def ca_exists(ca_name, cacert_path=None):
    '''
    Verify whether a Certificate Authority (CA) already exists

    ca_name
        name of the CA

    CLI Example:

    .. code-block:: bash

        salt '*' tls.ca_exists test_ca /etc/certs
    '''
    set_ca_path(cacert_path)
    certp = '{0}/{1}/{2}_ca_cert.crt'.format(
            cert_base_path(),
            ca_name,
            ca_name)
    if os.path.exists(certp):
        maybe_fix_ssl_version(ca_name)
        return True
    return False


def _ca_exists(ca_name, cacert_path=None):
    '''Retrocompatible wrapper'''
    return ca_exists(ca_name, cacert_path)


def get_ca(ca_name, as_text=False, cacert_path=None):
    '''
    Get the certificate path or content

    ca_name
        name of the CA
    as_text
        if true, return the certificate content instead of the path
    cacert_path
        absolute path to ca certificates root directory

    CLI Example:

    .. code-block:: bash

        salt '*' tls.get_ca test_ca as_text=False cacert_path=/etc/certs
    '''
    set_ca_path(cacert_path)
    certp = '{0}/{1}/{2}_ca_cert.crt'.format(
            cert_base_path(),
            ca_name,
            ca_name)
    if not os.path.exists(certp):
        raise ValueError('Certificate does not exists for {0}'.format(ca_name))
    else:
        if as_text:
            with open(certp) as fic:
                certp = fic.read()
    return certp


def create_ca(ca_name,
              bits=2048,
              days=365,
              CN='localhost',
              C='US',
              ST='Utah',
              L='Salt Lake City',
              O='SaltStack',
              OU=None,
              emailAddress='xyz@pdq.net',
              fixmode=False,
              cacert_path=None):
    '''
    Create a Certificate Authority (CA)

    ca_name
        name of the CA
    bits
        number of RSA key bits, default is 2048
    days
        number of days the CA will be valid, default is 365
    CN
        common name in the request, default is "localhost"
    C
        country, default is "US"
    ST
        state, default is "Utah"
    L
        locality, default is "Centerville", the city where SaltStack originated
    O
        organization, default is "SaltStack"
    OU
        organizational unit, default is None
    emailAddress
        email address for the CA owner, default is 'xyz@pdq.net'
    cacert_path
        absolute path to ca certificates root directory

    Writes out a CA certificate based upon defined config values. If the file
    already exists, the function just returns assuming the CA certificate
    already exists.

    If the following values were set::

        ca.cert_base_path='/etc/pki'
        ca_name='koji'

    the resulting CA, and corresponding key, would be written in the following location::

        /etc/pki/koji/koji_ca_cert.crt
        /etc/pki/koji/koji_ca_cert.key

    CLI Example:

    .. code-block:: bash

        salt '*' tls.create_ca test_ca
    '''
    set_ca_path(cacert_path)
    certp = '{0}/{1}/{2}_ca_cert.crt'.format(
        cert_base_path(), ca_name, ca_name)
    ca_keyp = '{0}/{1}/{2}_ca_cert.key'.format(
        cert_base_path(), ca_name, ca_name)
    if (not fixmode) and ca_exists(ca_name):
        return (
            'Certificate for CA named "{0}" '
            'already exists').format(ca_name)

    if fixmode and not os.path.exists(certp):
        raise ValueError('{0} does not exists, can\'t fix'.format(certp))

    if not os.path.exists('{0}/{1}'.format(
        cert_base_path(), ca_name)
    ):
        os.makedirs('{0}/{1}'.format(cert_base_path(),
                                     ca_name))

    # try to reuse existing ssl key
    key = None
    if os.path.exists(ca_keyp):
        with open(ca_keyp) as fic2:
            # try to determine the key bits
            key = OpenSSL.crypto.load_privatekey(
                OpenSSL.crypto.FILETYPE_PEM, fic2.read())
    if not key:
        key = OpenSSL.crypto.PKey()
        key.generate_key(OpenSSL.crypto.TYPE_RSA, bits)

    ca = OpenSSL.crypto.X509()
    ca.set_version(2)
    ca.set_serial_number(_new_serial(ca_name, CN))
    ca.get_subject().C = C
    ca.get_subject().ST = ST
    ca.get_subject().L = L
    ca.get_subject().O = O
    if OU:
        ca.get_subject().OU = OU
    ca.get_subject().CN = CN
    ca.get_subject().emailAddress = emailAddress

    ca.gmtime_adj_notBefore(0)
    ca.gmtime_adj_notAfter(int(days) * 24 * 60 * 60)
    ca.set_issuer(ca.get_subject())
    ca.set_pubkey(key)

    ca.add_extensions([
        OpenSSL.crypto.X509Extension('basicConstraints', True,
                                     'CA:TRUE, pathlen:0'),
        OpenSSL.crypto.X509Extension('keyUsage', True,
                                     'keyCertSign, cRLSign'),
        OpenSSL.crypto.X509Extension('subjectKeyIdentifier', False, 'hash',
                                     subject=ca)])

    ca.add_extensions([
        OpenSSL.crypto.X509Extension(
            'authorityKeyIdentifier',
            False,
            'issuer:always,keyid:always',
            issuer=ca)])
    ca.sign(key, 'sha1')

    # alway backup existing keys in case
    keycontent = OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM,
                                                key)
    write_key = True
    if os.path.exists(ca_keyp):
        bck = "{0}.{1}".format(ca_keyp, datetime.datetime.now().strftime(
            "%Y%m%d%H%M%S"))
        with open(ca_keyp) as fic:
            old_key = fic.read().strip()
            if old_key.strip() == keycontent.strip():
                write_key = False
            else:
                log.info('Saving old CA ssl key in {0}'.format(bck))
                with open(bck, 'w') as bckf:
                    bckf.write(old_key)
                    os.chmod(bck, 0600)
    if write_key:
        ca_key = salt.utils.fopen(ca_keyp, 'w')
        ca_key.write(keycontent)
        ca_key.close()

    ca_crt = salt.utils.fopen(certp, 'w')
    ca_crt.write(
        OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, ca))
    ca_crt.close()

    _write_cert_to_database(ca_name, ca)

    ret = ('Created Private Key: "{1}/{2}/{3}_ca_cert.key." ').format(
        ca_name, cert_base_path(), ca_name, ca_name)
    ret += ('Created CA "{0}": "{1}/{2}/{3}_ca_cert.crt."').format(
        ca_name, cert_base_path(), ca_name, ca_name)

    return ret


def create_csr(ca_name,
               bits=2048,
               CN='localhost',
               C='US',
               ST='Utah',
               L='Salt Lake City',
               O='SaltStack',
               OU=None,
               emailAddress='xyz@pdq.net',
               subjectAltName=None,
               cacert_path=None):
    '''
    Create a Certificate Signing Request (CSR) for a
    particular Certificate Authority (CA)

    ca_name
        name of the CA
    bits
        number of RSA key bits, default is 2048
    CN
        common name in the request, default is "localhost"
    C
        country, default is "US"
    ST
        state, default is "Utah"
    L
        locality, default is "Centerville", the city where SaltStack originated
    O
        organization, default is "SaltStack"
        NOTE: Must the same as CA certificate or an error will be raised
    OU
        organizational unit, default is None
    emailAddress
        email address for the request, default is 'xyz@pdq.net'
    subjectAltName
        valid subjectAltNames in full form, e.g. to add DNS entry you would call
        this function with this value:  **['DNS:myapp.foo.comm']**
    cacert_path
        absolute path to ca certificates root directory

    Writes out a Certificate Signing Request (CSR) If the file already
    exists, the function just returns assuming the CSR already exists.

    If the following values were set::

        ca.cert_base_path='/etc/pki'
        ca_name='koji'
        CN='test.egavas.org'

    the resulting CSR, and corresponding key, would be written in the
    following location::

        /etc/pki/koji/certs/test.egavas.org.csr
        /etc/pki/koji/certs/test.egavas.org.key

    CLI Example:

    .. code-block:: bash

        salt '*' tls.create_csr test
    '''
    set_ca_path(cacert_path)

    if not ca_exists(ca_name):
        return ('Certificate for CA named "{0}" does not exist, please create '
                'it first.').format(ca_name)

    if not os.path.exists('{0}/{1}/certs/'.format(
        cert_base_path(),
        ca_name)
    ):
        os.makedirs("{0}/{1}/certs/".format(cert_base_path(),
                                            ca_name))

    csr_f = '{0}/{1}/certs/{2}.csr'.format(cert_base_path(),
                                           ca_name, CN)
    if os.path.exists(csr_f):
        return 'Certificate Request "{0}" already exists'.format(csr_f)

    key = OpenSSL.crypto.PKey()
    key.generate_key(OpenSSL.crypto.TYPE_RSA, bits)

    req = OpenSSL.crypto.X509Req()

    req.get_subject().C = C
    req.get_subject().ST = ST
    req.get_subject().L = L
    req.get_subject().O = O
    if OU:
        req.get_subject().OU = OU
    req.get_subject().CN = CN
    req.get_subject().emailAddress = emailAddress

    if subjectAltName:
        req.add_extensions([
            OpenSSL.crypto.X509Extension(
                'subjectAltName', False, ", ".join(subjectAltName))])
    req.set_pubkey(key)
    req.sign(key, 'sha1')

    # Write private key and request
    priv_key = salt.utils.fopen(
            '{0}/{1}/certs/{2}.key'.format(cert_base_path(),
                                           ca_name, CN),
            'w+'
            )
    priv_key.write(
            OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key)
            )
    priv_key.close()

    csr = salt.utils.fopen(csr_f, 'w+')
    csr.write(
            OpenSSL.crypto.dump_certificate_request(
                OpenSSL.crypto.FILETYPE_PEM,
                req
                )
            )
    csr.close()

    ret = 'Created Private Key: "{0}/{1}/certs/{2}.key." '.format(
                    cert_base_path(),
                    ca_name,
                    CN
                    )
    ret += 'Created CSR for "{0}": "{1}/{2}/certs/{3}.csr."'.format(
                    ca_name,
                    cert_base_path(),
                    ca_name,
                    CN
                    )

    return ret


def create_self_signed_cert(tls_dir='tls',
                            bits=2048,
                            days=365,
                            CN='localhost',
                            C='US',
                            ST='Utah',
                            L='Salt Lake City',
                            O='SaltStack',
                            OU=None,
                            emailAddress='xyz@pdq.net',
                            cacert_path=None):
    '''
    Create a Self-Signed Certificate (CERT)

    tls_dir
        location appended to the ca.cert_base_path, default is 'tls'
    bits
        number of RSA key bits, default is 2048
    CN
        common name in the request, default is "localhost"
    C
        country, default is "US"
    ST
        state, default is "Utah"
    L
        locality, default is "Centerville", the city where SaltStack originated
    O
        organization, default is "SaltStack"
        NOTE: Must the same as CA certificate or an error will be raised
    OU
        organizational unit, default is None
    emailAddress
        email address for the request, default is 'xyz@pdq.net'
    cacert_path
        absolute path to ca certificates root directory

    Writes out a Self-Signed Certificate (CERT). If the file already
    exists, the function just returns.

    If the following values were set::

        ca.cert_base_path='/etc/pki'
        tls_dir='koji'
        CN='test.egavas.org'

    the resulting CERT, and corresponding key, would be written in the
    following location::

        /etc/pki/koji/certs/test.egavas.org.crt
        /etc/pki/koji/certs/test.egavas.org.key

    CLI Example:

    .. code-block:: bash

        salt '*' tls.create_self_signed_cert

    Passing options from the command line:

    .. code-block:: bash

        salt 'minion' tls.create_self_signed_cert CN='test.mysite.org'
    '''
    set_ca_path(cacert_path)

    if not os.path.exists('{0}/{1}/certs/'.format(cert_base_path(), tls_dir)):
        os.makedirs("{0}/{1}/certs/".format(cert_base_path(),
                                            tls_dir))

    if os.path.exists(
            '{0}/{1}/certs/{2}.crt'.format(cert_base_path(),
                                           tls_dir, CN)
            ):
        return 'Certificate "{0}" already exists'.format(CN)

    key = OpenSSL.crypto.PKey()
    key.generate_key(OpenSSL.crypto.TYPE_RSA, bits)

    # create certificate
    cert = OpenSSL.crypto.X509()
    cert.set_version(2)

    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(int(days) * 24 * 60 * 60)

    cert.get_subject().C = C
    cert.get_subject().ST = ST
    cert.get_subject().L = L
    cert.get_subject().O = O
    if OU:
        cert.get_subject().OU = OU
    cert.get_subject().CN = CN
    cert.get_subject().emailAddress = emailAddress

    cert.set_serial_number(_new_serial(tls_dir, CN))
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, 'sha1')

    # Write private key and cert
    priv_key = salt.utils.fopen(
            '{0}/{1}/certs/{2}.key'.format(cert_base_path(),
                                           tls_dir, CN),
            'w+'
            )
    priv_key.write(
            OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key)
            )
    priv_key.close()

    crt = salt.utils.fopen('{0}/{1}/certs/{2}.crt'.format(
        cert_base_path(),
        tls_dir,
        CN
        ), 'w+')
    crt.write(
            OpenSSL.crypto.dump_certificate(
                OpenSSL.crypto.FILETYPE_PEM,
                cert
                )
            )
    crt.close()

    _write_cert_to_database(tls_dir, cert)

    ret = 'Created Private Key: "{0}/{1}/certs/{2}.key." '.format(
                    cert_base_path(),
                    tls_dir,
                    CN
                    )
    ret += 'Created Certificate: "{0}/{1}/certs/{2}.crt."'.format(
                    cert_base_path(),
                    tls_dir,
                    CN
                    )

    return ret


def create_ca_signed_cert(ca_name, CN, days=365, cacert_path=None):
    '''
    Create a Certificate (CERT) signed by a
    named Certificate Authority (CA)

    ca_name
        name of the CA
    CN
        common name matching the certificate signing request
    days
        number of days certificate is valid, default is 365 (1 year)

    Writes out a Certificate (CERT) If the file already
    exists, the function just returns assuming the CERT already exists.

    The CN *must* match an existing CSR generated by create_csr. If it
    does not, this method does nothing.
    cacert_path
        absolute path to ca certificates root directory

    If the following values were set::

        ca.cert_base_path='/etc/pki'
        ca_name='koji'
        CN='test.egavas.org'

    the resulting signed certificate would be written in the
    following location::

        /etc/pki/koji/certs/test.egavas.org.crt

    CLI Example:

    .. code-block:: bash

        salt '*' tls.create_ca_signed_cert test localhost
    '''
    set_ca_path(cacert_path)
    if os.path.exists(
            '{0}/{1}/{2}.crt'.format(cert_base_path(),
                                     ca_name, CN)
    ):
        return 'Certificate "{0}" already exists'.format(ca_name)

    try:
        maybe_fix_ssl_version(ca_name)
        ca_cert = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM,
                salt.utils.fopen('{0}/{1}/{2}_ca_cert.crt'.format(
                    cert_base_path(),
                    ca_name, ca_name
                    )).read()
                )
        ca_key = OpenSSL.crypto.load_privatekey(
                OpenSSL.crypto.FILETYPE_PEM,
                salt.utils.fopen('{0}/{1}/{2}_ca_cert.key'.format(
                    cert_base_path(),
                    ca_name,
                    ca_name
                    )).read()
                )
    except IOError:
        return 'There is no CA named "{0}"'.format(ca_name)

    try:
        req = OpenSSL.crypto.load_certificate_request(
                OpenSSL.crypto.FILETYPE_PEM,
                salt.utils.fopen('{0}/{1}/certs/{2}.csr'.format(
                    cert_base_path(),
                    ca_name,
                    CN
                    )).read()
                )
    except IOError:
        return 'There is no CSR that matches the CN "{0}"'.format(CN)

    exts = []
    try:
        # see: http://bazaar.launchpad.net/~exarkun/pyopenssl/master/revision/189
        # support is there from quite a long time, but without API
        # so we mimic the newly get_extensions method present in ultra
        # recent pyopenssl distros
        native_exts_obj = OpenSSL._util.lib.X509_REQ_get_extensions(req._req)
        for i in range(OpenSSL._util.lib.sk_X509_EXTENSION_num(native_exts_obj)):
            ext = OpenSSL.crypto.X509Extension.__new__(OpenSSL.crypto.X509Extension)
            ext._extension = OpenSSL._util.lib.sk_X509_EXTENSION_value(native_exts_obj, i)
            exts.append(ext)
    except Exception:
        log.error('Support for extensions is not available, upgrade PyOpenSSL')

    cert = OpenSSL.crypto.X509()
    cert.set_version(2)
    cert.set_subject(req.get_subject())
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(int(days) * 24 * 60 * 60)
    if exts:
        cert.add_extensions(exts)
    cert.set_serial_number(_new_serial(ca_name, CN))
    cert.set_issuer(ca_cert.get_subject())
    cert.set_pubkey(req.get_pubkey())
    cert.sign(ca_key, 'sha1')

    crt = salt.utils.fopen('{0}/{1}/certs/{2}.crt'.format(
        cert_base_path(),
        ca_name,
        CN
        ), 'w+')
    crt.write(
            OpenSSL.crypto.dump_certificate(
                OpenSSL.crypto.FILETYPE_PEM,
                cert
                )
            )
    crt.close()

    _write_cert_to_database(ca_name, cert)

    return ('Created Certificate for "{0}": '
            '"{1}/{2}/certs/{3}.crt"').format(
                    ca_name,
                    cert_base_path(),
                    ca_name,
                    CN
                    )


def create_pkcs12(ca_name, CN, passphrase='', cacert_path=None):
    '''
    Create a PKCS#12 browser certificate for a particular Certificate (CN)

    ca_name
        name of the CA
    CN
        common name matching the certificate signing request
    passphrase
        used to unlock the PKCS#12 certificate when loaded into the browser
    cacert_path
        absolute path to ca certificates root directory

    If the following values were set::

        ca.cert_base_path='/etc/pki'
        ca_name='koji'
        CN='test.egavas.org'

    the resulting signed certificate would be written in the
    following location::

        /etc/pki/koji/certs/test.egavas.org.p12

    CLI Example:

    .. code-block:: bash

        salt '*' tls.create_pkcs12 test localhost
    '''
    set_ca_path(cacert_path)
    if os.path.exists(
            '{0}/{1}/certs/{2}.p12'.format(
                cert_base_path(),
                ca_name,
                CN)
            ):
        return 'Certificate "{0}" already exists'.format(CN)

    try:
        ca_cert = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM,
                salt.utils.fopen('{0}/{1}/{2}_ca_cert.crt'.format(
                    cert_base_path(),
                    ca_name,
                    ca_name
                    )).read()
                )
    except IOError:
        return 'There is no CA named "{0}"'.format(ca_name)

    try:
        cert = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM,
                salt.utils.fopen('{0}/{1}/certs/{2}.crt'.format(
                    cert_base_path(),
                    ca_name,
                    CN
                    )).read()
                )
        key = OpenSSL.crypto.load_privatekey(
                OpenSSL.crypto.FILETYPE_PEM,
                salt.utils.fopen('{0}/{1}/certs/{2}.key'.format(
                    cert_base_path(),
                    ca_name,
                    CN
                    )).read()
                )
    except IOError:
        return 'There is no certificate that matches the CN "{0}"'.format(CN)

    pkcs12 = OpenSSL.crypto.PKCS12()

    pkcs12.set_certificate(cert)
    pkcs12.set_ca_certificates([ca_cert])
    pkcs12.set_privatekey(key)

    with salt.utils.fopen('{0}/{1}/certs/{2}.p12'.format(
        cert_base_path(),
        ca_name,
        CN
        ), 'w') as ofile:
        ofile.write(pkcs12.export(passphrase=passphrase))

    return ('Created PKCS#12 Certificate for "{0}": '
            '"{1}/{2}/certs/{3}.p12"').format(
                    CN,
                    cert_base_path(),
                    ca_name,
                    CN
                    )

if __name__ == '__main__':
    #create_ca('koji', days=365, **cert_sample_meta)
    create_csr(
            'koji',
            CN='test_system',
            C="US",
            ST="Utah",
            L="Centerville",
            O="SaltStack",
            OU=None,
            emailAddress='test_system@saltstack.org'
            )
    create_ca_signed_cert('koji', 'test_system')
    create_pkcs12('koji', 'test_system', passphrase='test')
