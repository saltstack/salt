# -*- coding: utf-8 -*-
'''
A salt module for x509 certificates.
Can create keys, certificates and certificate requests.

:depends:   - M2Crypto Python module
'''

from __future__ import absolute_import

# Import python libs
import os
import time
import datetime
import logging
import hashlib
import glob
from salt.ext.six.moves import range
import OpenSSL
import M2Crypto
import random
import ctypes
from M2Crypto import m2, X509, RSA, BIO, EVP

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def get_pem_entry(text, pem_type=None):
    '''
    Takes PEM string that may be malformed and attempts to properly format it.

    Can fix situations where python converts new lines to spaces and most other
    whitespace related issues.

    If type not inclued, it will only work with an PEM that contains a single entry.
    '''

    if not pem_type:
        # Split based on headers
        if len(text.split("-----")) is not 5:
            raise ValueError('PEM text not valid:\n{0}'.format(text))
        pem_header = "-----"+text.split("-----")[1]+"-----"
        # Remove all whitespace from body
        pem_footer = "-----"+text.split("-----")[3]+"-----"
    else:
        pem_header = "-----BEGIN {0}-----".format(pem_type)
        pem_footer = "-----END {0}-----".format(pem_type)
        # Split based on defined headers
        if (len(text.split(pem_header)) is not 2 or
                len(text.split(pem_footer)) is not 2):
            raise ValueError(
                    'PEM does not contain a single entry of type {0}:\n'
                    '{1}'.format(pem_type, text))

    pem_body = text.split(pem_header)[1].split(pem_footer)[0]

    # Remove all whitespace from body
    pem_body = ''.join(pem_body.split())

    # Generate correctly formatted pem
    ret = pem_header+'\n'
    for i in range(0, len(pem_body), 64):
        ret += pem_body[i:i+64]+'\n'
    ret += pem_footer+'\n'

    return ret


def _pretty_hex(hex_str):
    return ':'.join([hex_str[i:i+2] for i in range(0, len(hex_str), 2)])


def _dec2hex(decval):
    return _pretty_hex("{:X}".format(decval))


def _parse_subject(subject):
    ret = {}
    for nid_name in subject.nid:
        val = getattr(subject, nid_name)
        if val:
            ret[nid_name] = val

    return ret


def _import_private_key(pem_text):
    pem_text = get_pem_entry(pem_text, pem_type='PRIVATE KEY')

    key = EVP.load_key_string(pem_text)

    return key


def _text_or_file(input_):
    if os.path.isfile(input_):
        return salt.utils.fopen(input_).read()
    else:
        return input_


def _get_certificate_obj(cert):
    text = _text_or_file(cert)
    text = get_pem_entry(text, pem_type='CERTIFICATE')
    return X509.load_cert_string(text)


def read_certificate(certificate):
    '''
    Reads a certificate, can specified as text or a file.
    '''
    cert = _get_certificate_obj(certificate)

    ret = {
        # X509 Verison 3 has a value of 2 in the field.
        # Version 2 has a value of 1.
        # https://tools.ietf.org/html/rfc5280#section-4.1.2.1
        'Version': cert.get_version()+1,
        # Get size returns in bytes. The world thinks of key sizes in bits.
        'Key Size': cert.get_pubkey().size()*8,
        'Serial Number': _dec2hex(cert.get_serial_number()),
        'SHA-256 Finger Print': _pretty_hex(cert.get_fingerprint(md='sha256')),
        'MD5 Finger Print': _pretty_hex(cert.get_fingerprint(md='md5')),
        'SHA1 Finger Print': _pretty_hex(cert.get_fingerprint(md='sha1')),
        'Subject': _parse_subject(cert.get_subject()),
        'Subject Hash': _dec2hex(cert.get_subject().as_hash()),
        'Issuer': _parse_subject(cert.get_issuer()),
        'Issuer Hash': _dec2hex(cert.get_issuer().as_hash()),
        'Not Before': str(cert.get_not_before().get_datetime()),
        'Not After': str(cert.get_not_after().get_datetime()),
    }

    exts = {}
    for ext_index in range(0, cert.get_ext_count()):
        ext = cert.get_ext_at(ext_index)
        name = ext.get_name()
        exts[name] = {
            'index': ext_index,
            'critical': bool(ext.get_critical()),
            'value': ext.get_value(),
        }

    if exts:
        ret['X509v3 Extensions'] = exts

    return ret


def read_crl(crl):
    text = _text_or_file(crl)
    text = get_pem_entry(text, pem_type='X509 CRL')

    # M2Crypto doesn't provide the same quick function to load CRL
    bio = BIO.MemoryBuffer()
    bio.write(text)
    cptr=m2.x509_crl_read_pem(bio._ptr())
    crl = CRL(cptr, 1)

    return None


def read_certificates(glob_path):
    '''
    Gets the details for all certs in a file or directory.
    '''
    ret = {}

    for path in glob.glob(glob_path):
        if os.path.isfile(path):
            try:
                ret[path] = read_certificate(path=path)
            except ValueError:
                pass

    return ret


def write_pem(text, path, pem_type=None):
    '''
    Writes out a pem file, fixes format before writing.
    '''
    text = get_pem_entry(text, pem_type=pem_type)
    salt.utils.fopen(path, 'w').write(text)
    return 'PEM written to {0}'.format(path)


def _parse_subject_in(subject_list):
    '''
    designed to parse the lists of ordereddicts that salt states provide
    '''
    subject = X509.X509_Name()

    for entry in subject_list:
        if entry['name'] not in subject.nid:
            raise ValueError('{0} is not a valid subject property'.format(entry['name']))
        setattr(subject, entry['name'], entry['value'])

    return subject


# Everything in this section is an ugly hack to fix an ancient bug in M2Crypto
# https://bugzilla.osafoundation.org/show_bug.cgi?id=7530#c13
class _Ctx(ctypes.Structure):
    _fields_ = [ ('flags', ctypes.c_int),
                 ('issuer_cert', ctypes.c_void_p),
                 ('subject_cert', ctypes.c_void_p),
                 ('subject_req', ctypes.c_void_p),
                 ('crl', ctypes.c_void_p),
                 ('db_meth', ctypes.c_void_p),
                 ('db', ctypes.c_void_p),
                ]

def _fix_ctx(m2_ctx, issuer = None):
    ctx = _Ctx.from_address(int(m2_ctx))

    ctx.flags = 0
    ctx.subject_cert = None
    ctx.subject_req = None
    ctx.crl = None
    if issuer is None:
        ctx.issuer_cert = None
    else:
        ctx.issuer_cert = int(issuer.x509)


def _new_extension(name, value, critical=0, issuer=None, _pyfree = 1):
    """
    Create new X509_Extension instance.
    """
    if name == 'subjectKeyIdentifier' and \
        value.strip('0123456789abcdefABCDEF:') is not '':
        raise ValueError('value must be precomputed hash')


    lhash = M2Crypto.m2.x509v3_lhash()
    ctx = M2Crypto.m2.x509v3_set_conf_lhash(lhash)
    #ctx not zeroed
    _fix_ctx(ctx, issuer)

    x509_ext_ptr = M2Crypto.m2.x509v3_ext_conf(lhash, ctx, name, value)
    #ctx,lhash freed

    if x509_ext_ptr is None:
        raise Exception
    x509_ext = M2Crypto.X509.X509_Extension(x509_ext_ptr, _pyfree)
    x509_ext.set_critical(critical)
    return x509_ext 
# End of ugly hacks


def _parse_extensions_in(ext_list):
    '''
    imports extension data from a list of dicts
    returns as a list of extensions
    each dict must contain name, value and optionally critical
    '''
    ret = []

    subjectKeyIdentifier = None
    for ext in ext_list:
        if ext['name'] == 'subjectKeyIdentifier':
            # add the subjectkeyidentifier to a temp ext, so it can be used by
            # authorityKeyIdentifier
            subjectKeyIdentifier = X509.new_extension(ext['name'], ext['value'])
        if ext['name'] == 'authorityKeyIdentifier':
            # Use the ugly hacks in place above
            if subjectKeyIdentifier:
                ext['value'].add_ext(subjectKeyIdentifier)
            ext = _new_extension('authorityKeyIdentifier',
                    'keyid,issuer:always', 0, issuer=ext['value'])
        else:
            ext = X509.new_extension(ext['name'], ext['value'])
        try:
            ext.set_critical(properties['critical'])
        except NameError:
            pass

        ret.append(ext)

    return ret


def create_private_key(path=None, text=False, bits=2048):
    '''
    Creates a private key.
    choose to write the key to 'path' or return as text.
    '''
    if ( not path and not text):
        raise ValueError('Either path or text must be specified.')
    if (path and text):
        raise ValueError('Either path or text must be specified, not both.')

    rsa = RSA.gen_key(bits, m2.RSA_F4)
    bio = BIO.MemoryBuffer()
    rsa.save_key_bio(bio, cipher=None)

    if path:
        return write_pem(text=bio.read_all(), path=path, 
                pem_type="RSA PRIVATE KEY")
    else:
        return bio.read_all()


def get_public_key(key):
    '''
    Returns a public key, either from a private key or a certificate.
    '''
    text = _text_or_file(key)

    text = get_pem_entry(text)

    if text.startswith('-----BEGIN PUBLIC KEY-----'):
        return text

    bio = BIO.MemoryBuffer()
    if text.startswith('-----BEGIN CERTIFICATE-----'):
        cert = X509.load_cert_string(text)
        rsa = cert.get_pubkey().get_rsa()
    if text.startswith('-----BEGIN CERTIFICATE REQUEST-----'):
        csr = X509.load_request_string(text)
        rsa = csr.get_pubkey().get_rsa()
    if (text.startswith('-----BEGIN PRIVATE KEY-----') or
            text.startswith('-----BEGIN RSA PRIVATE KEY-----')):
        rsa = RSA.load_key_string(text)

    rsa.save_pub_key_bio(bio)
    return bio.read_all()


def _get_public_key_obj(public_key):
    public_key = _text_or_file(public_key)
    public_key = get_pem_entry(public_key)
    public_key = get_public_key(public_key)
    bio = BIO.MemoryBuffer()
    bio.write(public_key)
    rsapubkey = RSA.load_pub_key_bio(bio)
    evppubkey = EVP.PKey()
    evppubkey.assign_rsa(rsapubkey)
    return evppubkey


def _get_private_key_obj(private_key):
    private_key = _text_or_file(private_key)
    private_key = get_pem_entry(private_key)
    rsaprivkey = RSA.load_key_string(private_key)
    evpprivkey = EVP.PKey()
    evpprivkey.assign_rsa(rsaprivkey)
    return evpprivkey


def get_private_key_size(private_key):
    return _get_private_key_obj(private_key).size()*8


def _get_pubkey_hash(cert):
    sha_hash = hashlib.sha1(cert.get_pubkey().get_modulus()).digest()
    return ":".join(["%02X"%ord(byte) for byte in sha_hash])


def create_certificate(path=None, text=None, subject=None,
        signing_private_key=None, signing_cert=None, public_key=None,
        extensions=None, days_valid=365, version=3,
        serial_number=None, serial_bits=64,
        algorithm='sha256',):
    '''
    Create a certificate. Requires passing a private and public key.
    Docs should indicate that if the private key matches the public key
    this is by definition a self-signed certificate.
    Also takes all the subject and extension properties.

    The subjectKeyIdentifier extension can be specified with a value of 'hash'
    This will create a subjectKeyIdentifier equal to the sha1 hash of the
    public key in DER format. Note this is not the same as openssl's
    subjectKeyIdentifier hash.
    '''
    if (not path and not text):
        raise ValueError('Either path or text must be specified.')
    if (path and text):
        raise ValueError('Either path or text must be specified, not both.')

    if not signing_private_key:
        raise ValueError('signing_private_key must be specified')

    if not public_key:
        public_key = get_public_key(signing_private_key)

    if (get_public_key(signing_private_key) == get_public_key(public_key) and
            signing_cert):
        raise ValueError('signing_private_key equals public_key,'
                'this is a self-signed certificate.'
                'Do not include signing_cert')

    if (get_public_key(signing_private_key) != get_public_key(public_key) and
            not signing_cert):
        raise ValueError('this is not a self-signed certificate.'
                'signing_cert is required.')

    subject = _parse_subject_in(subject)
    signing_private_key = _get_private_key_obj(signing_private_key)
    public_key = _get_public_key_obj(public_key)

    if signing_cert:
        signing_cert = _get_certificate_obj(signing_cert)
        signing_cert_subject = signing_cert.get_subject()
    else:
        signing_cert_subject = subject

    if not serial_number:
        serial_number = _dec2hex(random.getrandbits(serial_bits))

    serial_number = int(serial_number.replace(":",""), 16)

    cert = X509.X509()
    cert.set_serial_number(serial_number)
    # X509 Verison 3 has a value of 2 in the field.
    # Version 2 has a value of 1.
    # https://tools.ietf.org/html/rfc5280#section-4.1.2.1
    cert.set_version(version - 1)
    cert.set_subject(subject)
    cert.set_issuer(signing_cert_subject)
    cert.set_pubkey(public_key)

    notBefore = m2.x509_get_not_before(cert.x509)
    notAfter  = m2.x509_get_not_after(cert.x509)
    m2.x509_gmtime_adj(notBefore, 0)
    m2.x509_gmtime_adj(notAfter, 60*60*24*days_valid)

    # Preprocess key identifier extensions
    tmpext = []
    for ext in extensions:
        if (ext['name'] == 'subjectKeyIdentifier' and
                'hash' in ext['value']):
            hash_ = _get_pubkey_hash(cert)
            ext['value'] = ext['value'].replace('hash', hash_)

        if ext['name'] == 'authorityKeyIdentifier':
            # Part of the ugly hack for the authorityKeyIdentifier bug in M2Crypto
            if ext['value'] != 'keyid,issuer:always':
                raise ValueError('authorityKeyIdentifier must be keyid,issuer:always')
            if signing_cert:
                ext['value'] = signing_cert
            else:
                ext['value'] = cert
        tmpext.append(ext)

    extensions = tmpext

    # Process extensions list into ext objects
    extensions = _parse_extensions_in(extensions)
    for ext in extensions:
        cert.add_ext(ext)

    cert.sign(signing_private_key, algorithm)

    if path:
        return write_pem(text=cert.as_pem(), path=path, 
                pem_type="CERTIFICATE")
    else:
        return cert.as_pem()


def verify_private_key(private_key, public_key):
    '''
    Verify that 'private_key' matches the public key in 'public_key'
    public_key can be a certificate, csr or another private key
    '''

    return bool(get_public_key(private_key) == get_public_key(public_key))


def verify_signature(certificate, signing_pub_key=None):
    '''
    Verify the signature of a certificate.
    If signing_pub_key is not specified, assumes certificate is self-signed
    and checks it against itself.
    '''
    cert = _get_certificate_obj(certificate)

    if signing_pub_key:
        signing_pub_key = _get_public_key_obj(signing_pub_key)

    return bool(cert.verify(pkey=signing_pub_key) == 1)
