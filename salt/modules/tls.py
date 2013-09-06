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
        return 'tls'
    return False


def _cert_base_path():
    '''
    Return the base path for certs
    '''
    return __salt__['config.option']('ca.cert_base_path')


def _new_serial(ca_name, CN):
    '''
    Return a serial number in hex using md5sum, based upon the ca_name and
    CN values

    ca_name
        name of the CA
    CN
        common name in the request
    '''
    hashnum = int(
            hashlib.md5(
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


def _write_cert_to_database(ca_name, cert):
    '''
    write out the index.txt database file in the appropriate directory to
    track certificates

    ca_name
        name of the CA
    cert
        certificate to be recorded
    '''
    index_file = "{0}/{1}/index.txt".format(_cert_base_path(), ca_name)

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


def _ca_exists(ca_name):
    '''
    Verify whether a Certificate Authority (CA) already exists

    ca_name
        name of the CA
    '''

    if os.path.exists('{0}/{1}/{2}_ca_cert.crt'.format(
            _cert_base_path(),
            ca_name,
            ca_name
            )):
        return True
    return False


def create_ca(
        ca_name,
        bits=2048,
        days=365,
        CN='localhost',
        C='US',
        ST='Utah',
        L='Salt Lake City',
        O='Salt Stack',
        OU=None,
        emailAddress='xyz@pdq.net'):
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
        organization, default is "Salt Stack"
    OU
        organizational unit, default is None
    emailAddress
        email address for the CA owner, default is 'xyz@pdq.net'

    Writes out a CA certificate based upon defined config values. If the file
    already exists, the function just returns assuming the CA certificate
    already exists.

    If the following values were set:

    ca.cert_base_path='/etc/pki/koji'
    ca_name='koji'

    the resulting CA would be written in the following location::

    /etc/pki/koji/koji_ca_cert.crt

    CLI Example::

        salt '*' tls.create_ca test_ca
    '''
    if _ca_exists(ca_name):
        return 'Certificate for CA named "{0}" already exists'.format(ca_name)

    if not os.path.exists('{0}/{1}'.format(_cert_base_path(), ca_name)):
        os.makedirs('{0}/{1}'.format(_cert_base_path(), ca_name))

    key = OpenSSL.crypto.PKey()
    key.generate_key(OpenSSL.crypto.TYPE_RSA, bits)

    ca = OpenSSL.crypto.X509()
    ca.set_version(3)
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
                                   subject=ca)
      ])

    ca.add_extensions([
      OpenSSL.crypto.X509Extension(
          'authorityKeyIdentifier',
          False,
          'issuer:always,keyid:always',
          issuer=ca
          )
      ])
    ca.sign(key, 'sha1')

    ca_key = salt.utils.fopen(
            '{0}/{1}/{2}_ca_cert.key'.format(
                _cert_base_path(),
                ca_name,
                ca_name
                ),
            'w'
            )
    ca_key.write(
            OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key)
            )
    ca_key.close()

    ca_crt = salt.utils.fopen(
            '{0}/{1}/{2}_ca_cert.crt'.format(
                _cert_base_path(),
                ca_name,
                ca_name
                ),
            'w'
            )
    ca_crt.write(
            OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, ca)
            )
    ca_crt.close()

    _write_cert_to_database(ca_name, ca)

    return ('Created CA "{0}", certificate is located at '
            '"{1}/{2}/{3}_ca_cert.crt"').format(
                    ca_name,
                    _cert_base_path(),
                    ca_name,
                    ca_name
                    )


def create_csr(
        ca_name,
        bits=2048,
        CN='localhost',
        C='US',
        ST='Utah',
        L='Salt Lake City',
        O='Salt Stack',
        OU=None,
        emailAddress='xyz@pdq.net'):
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
        organization, default is "Salt Stack"
        NOTE: Must the same as CA certificate or an error will be raised
    OU
        organizational unit, default is None
    emailAddress
        email address for the request, default is 'xyz@pdq.net'

    Writes out a Certificate Signing Request (CSR) If the file already
    exists, the function just returns assuming the CSR already exists.

    If the following values were set:

    ca.cert_base_path='/etc/pki/koji'
    ca_name='koji'
    CN='test.egavas.org'

    the resulting CSR, and corresponding key, would be written in the
    following location:

    /etc/pki/koji/certs/test.egavas.org.csr
    /etc/pki/koji/certs/test.egavas.org.key

    CLI Example::

        salt '*' tls.create_csr test
    '''

    if not _ca_exists(ca_name):
        return ('Certificate for CA named "{0}" does not exist, please create '
                'it first.').format(ca_name)

    if not os.path.exists('{0}/{1}/certs/'.format(_cert_base_path(), ca_name)):
        os.makedirs("{0}/{1}/certs/".format(_cert_base_path(), ca_name))

    if os.path.exists('{0}/{1}/certs/{2}.csr'.format(
            _cert_base_path(),
            ca_name,
            CN)
            ):
        return 'Certificate Request "{0}" already exists'.format(ca_name)

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
    req.set_pubkey(key)
    req.sign(key, 'sha1')

    # Write private key and request
    priv_key = salt.utils.fopen(
            '{0}/{1}/certs/{2}.key'.format(_cert_base_path(), ca_name, CN),
            'w+'
            )
    priv_key.write(
            OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key)
            )
    priv_key.close()

    csr = salt.utils.fopen(
            '{0}/{1}/certs/{2}.csr'.format(_cert_base_path(), ca_name, CN),
            'w+'
            )
    csr.write(
            OpenSSL.crypto.dump_certificate_request(
                OpenSSL.crypto.FILETYPE_PEM,
                req
                )
            )
    csr.close()

    return ('Created CSR for "{0}", request is located at '
            '"{1}/{2}/certs/{3}.csr"').format(
                    ca_name,
                    _cert_base_path(),
                    ca_name,
                    CN
                    )


def create_self_signed_cert(
        tls_dir='tls',
        bits=2048,
        days=365,
        CN='localhost',
        C='US',
        ST='Utah',
        L='Salt Lake City',
        O='Salt Stack',
        OU=None,
        emailAddress='xyz@pdq.net'):

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
        organization, default is "Salt Stack"
        NOTE: Must the same as CA certificate or an error will be raised
    OU
        organizational unit, default is None
    emailAddress
        email address for the request, default is 'xyz@pdq.net'

    Writes out a Self-Signed Certificate (CERT). If the file already
    exists, the function just returns.

    If the following values were set:

    ca.cert_base_path='/etc/pki/koji'
    tls_dir='koji'
    CN='test.egavas.org'

    the resulting CERT, and corresponding key, would be written in the
    following location:

    /etc/pki/tls/certs/test.egavas.org.crt
    /etc/pki/tls/certs/test.egavas.org.key

    CLI Example::

        salt '*' tls.create_self_signed_cert
    '''

    if not os.path.exists('{0}/{1}/certs/'.format(_cert_base_path(), tls_dir)):
        os.makedirs("{0}/{1}/certs/".format(_cert_base_path(), tls_dir))

    if os.path.exists(
            '{0}/{1}/certs/{2}.crt'.format(_cert_base_path(), tls_dir, CN)
            ):
        return 'Certificate "{0}" already exists'.format(CN)

    key = OpenSSL.crypto.PKey()
    key.generate_key(OpenSSL.crypto.TYPE_RSA, bits)

    # create certificate
    cert = OpenSSL.crypto.X509()
    cert.set_version(3)

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
            '{0}/{1}/certs/{2}.key'.format(_cert_base_path(), tls_dir, CN),
            'w+'
            )
    priv_key.write(
            OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key)
            )
    priv_key.close()

    crt = salt.utils.fopen('{0}/{1}/certs/{2}.crt'.format(
        _cert_base_path(),
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

    ret = 'Created Private Key: {0}/{1}/certs/{2}.key. '.format(
        _cert_base_path(),
        tls_dir,
        CN)
    ret += 'Created Certificate: {0}/{1}/certs/{2}.crt.'.format(
        _cert_base_path(),
        tls_dir,
        CN)

    return ret


def create_ca_signed_cert(ca_name, CN, days=365):
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

    CLI Example::

        salt '*' tls.create_ca_signed_cert test localhost
    '''
    if os.path.exists(
            '{0}/{1}/{2}.crt'.format(_cert_base_path(), ca_name, CN)
            ):
        return 'Certificate "{0}" already exists'.format(ca_name)

    try:
        ca_cert = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM,
                salt.utils.fopen('{0}/{1}/{2}_ca_cert.crt'.format(
                    _cert_base_path(),
                    ca_name, ca_name
                    )).read()
                )
        ca_key = OpenSSL.crypto.load_privatekey(
                OpenSSL.crypto.FILETYPE_PEM,
                salt.utils.fopen('{0}/{1}/{2}_ca_cert.key'.format(
                    _cert_base_path(),
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
                    _cert_base_path(),
                    ca_name,
                    CN
                    )).read()
                )
    except IOError:
        return 'There is no CSR that matches the CN "{0}"'.format(CN)

    cert = OpenSSL.crypto.X509()
    cert.set_subject(req.get_subject())
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(int(days) * 24 * 60 * 60)
    cert.set_serial_number(_new_serial(ca_name, CN))
    cert.set_issuer(ca_cert.get_subject())
    cert.set_pubkey(req.get_pubkey())
    cert.sign(ca_key, 'sha1')

    crt = salt.utils.fopen('{0}/{1}/certs/{2}.crt'.format(
        _cert_base_path(),
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

    return ('Created Certificate for "{0}", located at '
            '"{1}/{2}/certs/{3}.crt"').format(
                    ca_name,
                    _cert_base_path(),
                    ca_name,
                    CN
                    )


def create_pkcs12(ca_name, CN, passphrase=''):
    '''
    Create a PKCS#12 browser certificate for a particular Certificate (CN)

    ca_name
        name of the CA
    CN
        common name matching the certificate signing request
    passphrase
        used to unlock the PKCS#12 certificate when loaded into the browser

    CLI Example::

        salt '*' tls.create_pkcs12 test localhost
    '''
    if os.path.exists(
            '{0}/{1}/certs/{2}.p12'.format(
                _cert_base_path(),
                ca_name,
                CN)
            ):
        return 'Certificate "{0}" already exists'.format(CN)

    try:
        ca_cert = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM,
                salt.utils.fopen('{0}/{1}/{2}_ca_cert.crt'.format(
                    _cert_base_path(),
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
                    _cert_base_path(),
                    ca_name,
                    CN
                    )).read()
                )
        key = OpenSSL.crypto.load_privatekey(
                OpenSSL.crypto.FILETYPE_PEM,
                salt.utils.fopen('{0}/{1}/certs/{2}.key'.format(
                    _cert_base_path(),
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
        _cert_base_path(),
        ca_name,
        CN
        ), 'w') as ofile:
        ofile.write(pkcs12.export(passphrase=passphrase))

    return ('Created PKCS#12 Certificate for "{0}", located at '
            '"{1}/{2}/certs/{3}.p12"').format(
                    CN,
                    _cert_base_path(),
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
            O="Salt Stack",
            OU=None,
            emailAddress='test_system@saltstack.org'
            )
    create_ca_signed_cert('koji', 'test_system')
    create_pkcs12('koji', 'test_system', passphrase='test')
