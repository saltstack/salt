'''
A salt interface for running a Certificate Authority (CA)
which provides signed/unsigned SSL certificates

REQUIREMENT 1?:

Required python modules: PyOpenSSL

REQUIREMENT 2:

Add the following values in /etc/salt/minion for the
CA module to function properly::

ca.cert_base_path: '/etc/pki/koji'


'''

import os
import sys
import time
import logging
import hashlib
import OpenSSL

import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

def __virtual__():
    '''
    Only load this module if the ca config options are set
    '''

    return 'ca'

def _cert_base_path():
    if 'ca.cert_base_path' in __opts__:
        return __opts__['ca.cert_base_path']
    raise CommandExecutionError("Please set the 'ca.cert_base_path' in the minion configuration")


def _new_serial(ca_name, CN):

    '''
    Return a serial number in hex using md5sum, based upon the the ca_name and CN values

    ca_name
        name of the CA
    CN
        common name in the request
    '''

    hashnum = int(hashlib.md5('{0}_{1}_{2}'.format(ca_name, CN, int(time.time()))).hexdigest(), 16)
    log.debug("Hashnum: {0}".format(hashnum))

    # record the hash somewhere
    cachedir = __opts__['cachedir']
    log.debug("cachedir: {0}".format(cachedir))
    serial_file = '{0}/{1}.serial'.format(cachedir, ca_name)
    if os.path.exists(serial_file):
        fr = open(serial_file, 'r')
        lines = fr.readlines()
        fr.close()

    with open(serial_file, 'a+') as f:
        f.write(str(hashnum))

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
    subject += '/'.join(['{0}={1}'.format(x,y) for x,y in cert.get_subject().get_components()])
    subject += '\n'

    index_data = "V\t{0}\t\t{1}\tunknown\t{2}".format(expire_date, serial_number, subject)

    with open(index_file, 'a+') as f:
        f.write(index_data)


def _ca_exists(ca_name):

    '''
    Verify whether a Certificate Authority (CA) already exists

    ca_name
        name of the CA
    '''

    if os.path.exists("{0}/{1}/{2}_ca_cert.crt".format(_cert_base_path(), ca_name, ca_name)):
        return True
    return False

def create_ca(ca_name, bits=2048, days=365, CN='localhost', C="US", ST="Utah", L="Centerville", O="Salt Stack", OU=None, emailAddress='xyz@pdq.net'):

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
    email
        email address for the CA owner, default is 'xyz@pdq.net'

    Writes out a CA certificate based upon defined config values. If the file
    already exists, the function just returns assuming the CA certificate
    already exists.

    If the following values were set:

    ca.cert_base_path='/etc/pki/koji'
    ca_name='koji'

    the resulting CA would be written in the following location::

    /etc/pki/koji/koji_ca_cert.crt
    '''

    if _ca_exists(ca_name):
        return "Certificate for CA named '{0}' already exists".format(ca_name)

    if not os.path.exists("{0}/{1}".format(_cert_base_path(), ca_name)):
        os.makedirs("{0}/{1}".format(_cert_base_path(), ca_name))

    key = OpenSSL.crypto.PKey()
    key.generate_key(OpenSSL.crypto.TYPE_RSA, 2048)

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
    ca.gmtime_adj_notAfter(days * 24 * 60 * 60)
    ca.set_issuer(ca.get_subject())
    ca.set_pubkey(key)

    ca.add_extensions([
      OpenSSL.crypto.X509Extension("basicConstraints", True,
                                   "CA:TRUE, pathlen:0"),
      OpenSSL.crypto.X509Extension("keyUsage", True,
                                   "keyCertSign, cRLSign"),
      OpenSSL.crypto.X509Extension("subjectKeyIdentifier", False, "hash",
                                   subject=ca)
      ])

    ca.add_extensions([
      OpenSSL.crypto.X509Extension('authorityKeyIdentifier', False, 'issuer:always,keyid:always',
                                   issuer=ca)
      ])
    ca.sign(key, "sha1")


    ca_key = open("{0}/{1}/{2}_ca_cert.key".format(_cert_base_path(), ca_name, ca_name), 'w')
    ca_key.write(OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key))
    ca_key.close()

    ca_crt = open("{0}/{1}/{2}_ca_cert.crt" % (_cert_base_path(), ca_name, ca_name), 'w')
    ca_crt.write(OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, ca))
    ca_crt.close()

    _write_cert_to_database(ca_name, ca)

    return "Created CA '{0}', certificate is located at '{1}/{2}/{3}_ca_cert.crt'".format(ca_name, _cert_base_path(), ca_name, ca_name)


def create_csr(ca_name, bits=2048, CN='localhost', C="US", ST="Utah", L="Centerville", O="Salt Stack", OU=None, emailAddress='xyz@pdq.net'):

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

    the resulting CSR, and corresponding key, would be written in the following location:

    /etc/pki/koji/certs/test.egavas.org.csr
    /etc/pki/koji/certs/test.egavas.org.key
    '''

    if not _ca_exists(ca_name):
        return "Certificate for CA named '{0}' does not exist, please create it first.".format(ca_name)

    if not os.path.exists("{0}/{1}/certs/".format(_cert_base_path(), ca_name)):
        os.makedirs("{0}/{1}/certs/".format(_cert_base_path(), ca_name))

    if os.path.exists("{0}/{1}/certs/{2}.csr".format(_cert_base_path(), ca_name, CN)):
        return "Certificate Request '{0}' already exists".format(ca_name)

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
    req.sign(key, "sha1")

    # Write private key and request
    priv_key = open("{0}/{1}/certs/{2}.key".format(_cert_base_path(), ca_name, CN), 'w')
    priv_key.write(OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key))
    priv_key.close()

    csr = open("{0}/{1}/certs/{2}.csr".format(_cert_base_path(), ca_name, CN), 'w')
    csr.write(OpenSSL.crypto.dump_certificate_request(OpenSSL.crypto.FILETYPE_PEM, req))
    csr.close()

    return "Created CSR for '{0}', request is located at '{1}/{2}/certs/{3}.csr".format(ca_name, _cert_base_path(), ca_name, CN)


