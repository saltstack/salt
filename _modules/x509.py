# -*- coding: utf-8 -*-
'''
A salt module for x509 certificates.
Can create keys, certificates and certificate requests.

:depends:   - M2Crypto Python module
'''

from __future__ import absolute_import

# Import python libs
import os
import logging
import hashlib
import glob
import M2Crypto
import random
import ctypes
import tempfile
import yaml
import subprocess
import re
from M2Crypto import m2, X509, RSA, BIO, EVP

# Import salt libs
import salt.utils
import salt.exceptions

log = logging.getLogger(__name__)

EXT_NAME_MAPPINGS = {'subjectKeyIdentifier': 'X509v3 Subject Key Identifier',
                     'authorityKeyIdentifier': 'X509v3 Authority Key Identifier',
                     'basicConstraints': 'X509v3 Basic Constraints',
                     'keyUsage': 'X509v3 Key Usage',
                     'nsComment': 'Netscape Comment',
                     'subjectAltName': 'X509v3 Subject Alternative Name',}


# Everything in this section is an ugly hack to fix an ancient bug in M2Crypto
# https://bugzilla.osafoundation.org/show_bug.cgi?id=7530#c13
class _Ctx(ctypes.Structure):
    _fields_ = [('flags', ctypes.c_int),
                ('issuer_cert', ctypes.c_void_p),
                ('subject_cert', ctypes.c_void_p),
                ('subject_req', ctypes.c_void_p),
                ('crl', ctypes.c_void_p),
                ('db_meth', ctypes.c_void_p),
                ('db', ctypes.c_void_p),
                ]

def _fix_ctx(m2_ctx, issuer=None):
    ctx = _Ctx.from_address(int(m2_ctx))

    ctx.flags = 0
    ctx.subject_cert = None
    ctx.subject_req = None
    ctx.crl = None
    if issuer is None:
        ctx.issuer_cert = None
    else:
        ctx.issuer_cert = int(issuer.x509)


def _new_extension(name, value, critical=0, issuer=None, _pyfree=1):
    '''
    Create new X509_Extension instance.
    '''
    if name == 'subjectKeyIdentifier' and \
        value.strip('0123456789abcdefABCDEF:') is not '':
        raise salt.exceptions.SaltInvocationError('value must be precomputed hash')


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


# The next two functions are more hacks because M2Crypto doesn't support getting
# Extensions from CSRs. https://github.com/martinpaljak/M2Crypto/issues/63
def _req_extensions(csr_filename):
    cmd = ('openssl req -text -noout -in {0}'.format(csr_filename))

    output = subprocess.check_output(cmd.split(),
        stderr=subprocess.STDOUT)

    output = re.sub(r': rsaEncryption', ':', output)
    output = re.sub(r'[0-9a-f]{2}:', '', output)

    return yaml.safe_load(output)


def _get_csr_extensions(csr):
    # Currently only supports SAN
    # Add SubjectAlternativeName from CSR
    ret = []

    csrtempfile = tempfile.NamedTemporaryFile()
    csrtempfile.write(csr.as_pem())
    csrtempfile.flush()
    csryaml = _req_extensions(csrtempfile.name)
    csrtempfile.close()
    csrexts = csryaml['Certificate Request']['Data']['Requested Extensions']

    for short_name, long_name in EXT_NAME_MAPPINGS.iteritems():
        if long_name in csrexts:
            ret.append({'name': short_name,
                'value': csrexts[long_name]})

    return ret


def _pretty_hex(hex_str):
    return ':'.join([hex_str[i:i+2] for i in range(0, len(hex_str), 2)])


def _dec2hex(decval):
    return _pretty_hex('{:X}'.format(decval))


def _text_or_file(input_):
    if os.path.isfile(input_):
        return salt.utils.fopen(input_).read()
    else:
        return input_


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


def _get_certificate_obj(cert):
    text = _text_or_file(cert)
    text = get_pem_entry(text, pem_type='CERTIFICATE')
    return X509.load_cert_string(text)


def _parse_subject_in(subject_dict):
    '''
    parses a dict of subject entries
    '''
    subject = X509.X509_Name()

    for name, value in subject_dict.iteritems():
        if name not in subject.nid:
            raise salt.exceptions.SaltInvocationError('{0} is not a valid subject property'.format(name))
        setattr(subject, name, value)

    return subject


def _parse_extensions_in(ext_list):
    '''
    imports extension data from a list of dicts
    returns as a list of extensions
    each dict must contain name, value and optionally critical
    '''
    ret = []

    subject_key_identifier = None
    for ext in ext_list:
        if ext['name'] == 'subjectKeyIdentifier':
            # add the subjectkeyidentifier to a temp ext, so it can be used by
            # authorityKeyIdentifier
            subject_key_identifier = X509.new_extension(ext['name'], ext['value'])
        if ext['name'] == 'authorityKeyIdentifier':
            # Use the ugly hacks in place above
            if subject_key_identifier:
                ext['value'].add_ext(subject_key_identifier)
            ext = _new_extension('authorityKeyIdentifier',
                    'keyid,issuer:always', 0, issuer=ext['value'])
        else:
            ext = X509.new_extension(ext['name'], ext['value'])
        try:
            ext.set_critical(ext['critical'])
        except NameError:
            pass

        ret.append(ext)

    return ret


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


def _get_request_obj(csr):
    text = _text_or_file(csr)
    text = get_pem_entry(text, pem_type='CERTIFICATE REQUEST')
    return X509.load_request_string(text)


def _get_pubkey_hash(cert):
    sha_hash = hashlib.sha1(cert.get_pubkey().get_modulus()).digest()
    return ':'.join(['{0}02X'.format(ord(byte)) for byte in sha_hash])


def get_pem_entry(text, pem_type=None):
    '''
    Takes PEM string that may be malformed and attempts to properly format it.

    Can fix situations where python converts new lines to spaces and most other
    whitespace related issues.

    If type not inclued, it will only work with an PEM that contains a single entry.
    '''

    if not pem_type:
        # Split based on headers
        if len(text.split('-----')) is not 5:
            raise salt.exceptions.SaltInvocationError('PEM text not valid:\n{0}'.format(text))
        pem_header = '-----'+text.split('-----')[1]+'-----'
        # Remove all whitespace from body
        pem_footer = '-----'+text.split('-----')[3]+'-----'
    else:
        pem_header = '-----BEGIN {0}-----'.format(pem_type)
        pem_footer = '-----END {0}-----'.format(pem_type)
        # Split based on defined headers
        if (len(text.split(pem_header)) is not 2 or
                len(text.split(pem_footer)) is not 2):
            raise salt.exceptions.SaltInvocationError(
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
        'Not Before': cert.get_not_before().get_datetime().strftime('%Y-%m-%d %H:%M:%S'),
        'Not After': cert.get_not_after().get_datetime().strftime('%Y-%m-%d %H:%M:%S'),
    }

    exts = []
    for ext_index in range(0, cert.get_ext_count()):
        ext = cert.get_ext_at(ext_index)
        name = ext.get_name()
        exts.append({
            'name': name,
            'value': ext.get_value(),
            'critical': bool(ext.get_critical()),
        })

    if exts:
        ret['X509v3 Extensions'] = exts

    return ret


def read_certificates(glob_path):
    '''
    Gets the details for all certs in a file or directory.
    '''
    ret = {}

    for path in glob.glob(glob_path):
        if os.path.isfile(path):
            try:
                ret[path] = read_certificate(certificate=path)
            except ValueError:
                pass

    return ret


def read_csr(csr):
    '''
    Reads a certificate signing request
    '''
    csr = _get_request_obj(csr)
    ret = {
           # X509 Verison 3 has a value of 2 in the field.
           # Version 2 has a value of 1.
           # https://tools.ietf.org/html/rfc5280#section-4.1.2.1
           'Version': csr.get_version()+1,
           # Get size returns in bytes. The world thinks of key sizes in bits.
           'Subject': _parse_subject(csr.get_subject()),
           'Subject Hash': _dec2hex(csr.get_subject().as_hash()),
           }

    ret['X509v3 Extensions'] = _get_csr_extensions(csr)

    return ret


def read_crl(crl):
    text = _text_or_file(crl)
    text = get_pem_entry(text, pem_type='X509 CRL')

    # M2Crypto doesn't provide the same quick function to load CRL
    bio = BIO.MemoryBuffer()
    bio.write(text)
    cptr = m2.x509_crl_read_pem(bio._ptr())
    crl = X509.CRL(cptr, 1)

    return None


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


def get_private_key_size(private_key):
    return _get_private_key_obj(private_key).size()*8


def write_pem(text, path, pem_type=None):
    '''
    Writes out a pem file, fixes format before writing.
    '''
    text = get_pem_entry(text, pem_type=pem_type)
    salt.utils.fopen(path, 'w').write(text)
    return 'PEM written to {0}'.format(path)


def create_private_key(path=None, text=False, bits=2048):
    '''
    Creates a private key.
    choose to write the key to 'path' or return as text.
    '''
    if not path and not text:
        raise salt.exceptions.SaltInvocationError('Either path or text must be specified.')
    if path and text:
        raise salt.exceptions.SaltInvocationError('Either path or text must be specified, not both.')

    rsa = RSA.gen_key(bits, m2.RSA_F4)
    bio = BIO.MemoryBuffer()
    rsa.save_key_bio(bio, cipher=None)

    if path:
        return write_pem(text=bio.read_all(), path=path,
                pem_type='RSA PRIVATE KEY')
    else:
        return bio.read_all()


def create_certificate(path=None, text=False, subject={},
        signing_private_key=None, signing_cert=None, public_key=None,
        csr=None, extensions=[], days_valid=365, version=3,
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
    if not path and not text:
        raise salt.exceptions.SaltInvocationError('Either path or text must be specified.')
    if path and text:
        raise salt.exceptions.SaltInvocationError('Either path or text must be specified, not both.')

    if not signing_private_key:
        raise salt.exceptions.SaltInvocationError('signing_private_key must be specified')

    if public_key and csr:
        raise salt.exceptions.SaltInvocationError('Include either public_key or csr, not both.')

    if not (public_key or csr):
        public_key = get_public_key(signing_private_key)
    elif csr:
        public_key = get_public_key(csr)

    if (get_public_key(signing_private_key) == get_public_key(public_key) and
            signing_cert):
        raise salt.exceptions.SaltInvocationError('signing_private_key equals public_key,'
                'this is a self-signed certificate.'
                'Do not include signing_cert')

    if (get_public_key(signing_private_key) != get_public_key(public_key) and
            not signing_cert):
        raise salt.exceptions.SaltInvocationError('this is not a self-signed certificate.'
                'signing_cert is required.')

    if csr:
        # Reading csr
        csrsubject = read_csr(csr)['Subject']
        # Update will add entries from subject, overwriting any in the csr
        csrsubject.update(subject)
        subject = csrsubject

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

    serial_number = int(serial_number.replace(':', ''), 16)

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
                raise salt.exceptions.SaltInvocationError('authorityKeyIdentifier must be keyid,issuer:always')
            if signing_cert:
                ext['value'] = signing_cert
            else:
                ext['value'] = cert
        tmpext.append(ext)

    # Add CSR extensions that don't already exist
    if csr:
        for csrext in _get_csr_extensions(_get_request_obj(csr)):
            superseded = False
            for ext in extensions:
                if ext['name'] == csrext['name']:
                    superseded = True
                    break
            if superseded:
                continue
            tmpext.append(csrext)

    extensions = tmpext

    # Process extensions list into ext objects
    extensions = _parse_extensions_in(extensions)
    for ext in extensions:
        cert.add_ext(ext)

    cert.sign(signing_private_key, algorithm)

    if path:
        return write_pem(text=cert.as_pem(), path=path,
                pem_type='CERTIFICATE')
    else:
        return cert.as_pem()


def create_csr(path=None, text=False, subject={}, public_key=None,
        extensions=[], version=3,):
    '''
    Create a certificate signing request
    '''
    if not path and not text:
        raise salt.exceptions.SaltInvocationError('Either path or text must be specified.')
    if path and text:
        raise salt.exceptions.SaltInvocationError('Either path or text must be specified, not both.')

    subject = _parse_subject_in(subject)
    public_key = _get_public_key_obj(public_key)

    csr = X509.Request()
    csr.set_version(version - 1)
    csr.set_subject(subject)
    csr.set_pubkey(public_key)

    # subjectkeyidentifier and authoritykeyidentifier should not be in CSRs
    for ext in extensions:
        if ext['name'] == 'subjectKeyIdentifier':
            raise salt.exceptions.SaltInvocationError('subjectKeyIdentifier should be added by the CA,'
                'not include in the CSR')
        if ext['name'] == 'authorityKeyIdentifier':
            raise salt.exceptions.SaltInvocationError('authorityKeyIdentifier should be added by the CA,'
                'not include in the CSR')
        if ext['name'] not in EXT_NAME_MAPPINGS:
            raise salt.exceptions.SaltInvocationError('Unknown Extension {0}'.format(ext['name']))

    extensions = _parse_extensions_in(extensions)
    extstack = X509.X509_Extension_Stack()
    for ext in extensions:
        extstack.push(ext)
    csr.add_extensions(extstack)

    if path:
        return write_pem(text=csr.as_pem(), path=path,
                pem_type='CERTIFICATE REQUEST')
    else:
        return csr.as_pem()


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
