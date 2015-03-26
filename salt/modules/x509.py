# -*- coding: utf-8 -*-
'''
Manage X509 certificates

.. versionadded:: TBD
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
import datetime

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
    Create new X509_Extension, explicitly for authorityKeyIdentifier bugs.
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


# The next four functions are more hacks because M2Crypto doesn't support getting
# Extensions from CSRs. https://github.com/martinpaljak/M2Crypto/issues/63
def _parse_openssl_req(csr_filename):
    '''
    Parses openssl command line output, this is a workaround for M2Crypto's
    inability to get them from CSR objects.
    '''
    cmd = ('openssl req -text -noout -in {0}'.format(csr_filename))

    output = subprocess.check_output(cmd.split(),
        stderr=subprocess.STDOUT)

    output = re.sub(r': rsaEncryption', ':', output)
    output = re.sub(r'[0-9a-f]{2}:', '', output)

    return yaml.safe_load(output)


def _get_csr_extensions(csr):
    '''
    Returns a list of dicts containing the name, value and critical value of
    any extension contained in a csr object.
    '''
    ret = []

    csrtempfile = tempfile.NamedTemporaryFile()
    csrtempfile.write(csr.as_pem())
    csrtempfile.flush()
    csryaml = _parse_openssl_req(csrtempfile.name)
    csrtempfile.close()
    csrexts = csryaml['Certificate Request']['Data']['Requested Extensions']

    for short_name, long_name in EXT_NAME_MAPPINGS.iteritems():
        if long_name in csrexts:
            retext = {}
            if csrexts[long_name].startswith('critical '):
                retext['critical'] = True
                csrexts[long_name] = csrexts[long_name][9:]
            retext['name'] = short_name
            retext['value'] = csrexts[long_name]
            ret.append(retext)

    return ret


# None of python libraries read CRLs. Again have to hack it with the openssl CLI
def _parse_openssl_crl(crl_filename):
    '''
    Parses openssl command line output, this is a workaround for M2Crypto's
    inability to get them from CSR objects.
    '''
    cmd = ('openssl crl -text -noout -in {0}'.format(crl_filename))

    output = subprocess.check_output(cmd.split(),
        stderr=subprocess.STDOUT)

    crl = {}
    for line in output.split('\n'):
        line = line.strip()
        if line.startswith('Version '):
            crl['Version'] = line.replace('Version ', '')
        if line.startswith('Signature Algorithm: '):
            crl['Signature Algorithm'] = line.replace('Signature Algorithm: ', '')
        if line.startswith('Issuer: '):
            line = line.replace('Issuer: ', '')
            subject = {}
            for sub_entry in line.split('/'):
                if '=' in sub_entry:
                    sub_entry = sub_entry.split('=')
                    subject[sub_entry[0]] = sub_entry[1]
            crl['Issuer'] = subject
        if line.startswith('Last Update: '):
            crl['Last Update'] = line.replace('Last Update: ', '')
            last_update = datetime.datetime.strptime(
                    crl['Last Update'], "%b %d %H:%M:%S %Y %Z")
            crl['Last Update'] = last_update.strftime("%Y-%m-%d %H:%M:%S")
        if line.startswith('Next Update: '):
            crl['Next Update'] = line.replace('Next Update: ', '')
            next_update = datetime.datetime.strptime(
                    crl['Next Update'], "%b %d %H:%M:%S %Y %Z")
            crl['Next Update'] = next_update.strftime("%Y-%m-%d %H:%M:%S")
        if line.startswith('Revoked Certificates:'):
            break

    output = output.split('Revoked Certificates:')[1]
    output = output.split('Signature Algorithm:')[0]

    rev = []
    for revoked in output.split('Serial Number: '):
        if not revoked.strip():
            continue

        rev_sn = revoked.split('\n')[0].strip()
        revoked = rev_sn + ':\n' + '\n'.join(revoked.split('\n')[1:])
        rev_yaml = yaml.safe_load(revoked)
        for rev_item, rev_values in rev_yaml.iteritems():
            if 'Revocation Date' in rev_values:
                rev_date = datetime.datetime.strptime(
                        rev_values['Revocation Date'], "%b %d %H:%M:%S %Y %Z")
                rev_values['Revocation Date'] = rev_date.strftime("%Y-%m-%d %H:%M:%S")

        rev.append(rev_yaml)

    crl['Revoked Certificates'] = rev

    return crl


def _pretty_hex(hex_str):
    '''
    Nicely formats hex strings
    '''
    if len(hex_str) % 2 != 0:
        hex_str = '0' + hex_str
    return ':'.join([hex_str[i:i+2] for i in range(0, len(hex_str), 2)]).upper()


def _dec2hex(decval):
    '''
    Converts decimal values to nicely formatted hex strings
    '''
    return _pretty_hex('{:X}'.format(decval))


def _text_or_file(input_):
    '''
    Determines if input is a path to a file, or a string with the content to be parsed.
    '''
    if os.path.isfile(input_):
        return salt.utils.fopen(input_).read()
    else:
        return input_


def _parse_subject(subject):
    '''
    Returns a dict containing all values in an X509 Subject
    '''
    ret = {}
    for nid_name in subject.nid:
        val = getattr(subject, nid_name)
        if val:
            ret[nid_name] = val

    return ret


def _get_certificate_obj(cert):
    '''
    Returns a certificate object based on PEM text.
    '''
    text = _text_or_file(cert)
    text = get_pem_entry(text, pem_type='CERTIFICATE')
    return M2Crypto.X509.load_cert_string(text)


def _get_public_key_obj(public_key):
    '''
    Returns a public key object based on PEM text.
    '''
    public_key = _text_or_file(public_key)
    public_key = get_pem_entry(public_key)
    public_key = get_public_key(public_key)
    bio = M2Crypto.BIO.MemoryBuffer()
    bio.write(public_key)
    rsapubkey = M2Crypto.RSA.load_pub_key_bio(bio)
    evppubkey = M2Crypto.EVP.PKey()
    evppubkey.assign_rsa(rsapubkey)
    return evppubkey


def _get_private_key_obj(private_key):
    '''
    Returns a private key object based on PEM text.
    '''
    private_key = _text_or_file(private_key)
    private_key = get_pem_entry(private_key)
    rsaprivkey = M2Crypto.RSA.load_key_string(private_key)
    evpprivkey = M2Crypto.EVP.PKey()
    evpprivkey.assign_rsa(rsaprivkey)
    return evpprivkey


def _get_request_obj(csr):
    '''
    Returns a CSR object based on PEM text.
    '''
    text = _text_or_file(csr)
    text = get_pem_entry(text, pem_type='CERTIFICATE REQUEST')
    return M2Crypto.X509.load_request_string(text)


def _parse_subject_in(subject_dict):
    '''
    parses a dict of subject entries
    '''
    subject = M2Crypto.X509.X509_Name()

    for name, value in subject_dict.iteritems():
        if name not in subject.nid:
            raise salt.exceptions.SaltInvocationError('{0} is not a valid subject property'.format(name))
        setattr(subject, name, value)

    return subject


def _parse_extensions_in(ext_list):
    '''
    parses a list of dicts containing extension data and returns a list of extension objects.
    '''
    ret = []

    subject_key_identifier = None
    for ext in ext_list:
        if ext['name'] == 'subjectKeyIdentifier':
            # add the subjectkeyidentifier to a temp ext, so it can be used by
            # authorityKeyIdentifier
            subject_key_identifier = M2Crypto.X509.new_extension(ext['name'], ext['value'])
        if ext['name'] == 'authorityKeyIdentifier':
            # Use the ugly hacks in place above
            # In preprocessing, for authorityKeyIdentifier, the value is replaced
            # with the certificate object representing the issuer
            # Or with the string self in case of a self-issuer
            # We need to pass this certificate object as issuer to new_extension
            # where the subjectKeyIdentifier extension will be copied
            # authorityKeyIdentifier
            if ext['value'] == 'self':
                ext['value'] = M2Crypto.X509.X509()
                ext['value'].add_ext(subject_key_identifier)
            ext_obj = _new_extension('authorityKeyIdentifier',
                         'keyid,issuer:always', 0, issuer=ext['value'])
        else:
            ext_obj = M2Crypto.X509.new_extension(ext['name'], ext['value'])

        if 'critical' in ext:
            ext_obj.set_critical(ext['critical'])

        ret.append(ext_obj)

    return ret


def _get_pubkey_hash(cert):
    '''
    Returns the sha1 hash of the modulus of a public key in a cert
    Used for generating subject key identifiers
    '''
    sha_hash = hashlib.sha1(cert.get_pubkey().get_modulus()).hexdigest()
    return _pretty_hex(sha_hash)


def get_pem_entry(text, pem_type=None):
    '''
    Returns a properly formatted PEM string from the input text fixing
    any whitespace or line-break issues

    text:
        Text containing the X509 PEM entry to be returned

    pem_type:
        If specified, this function will only return a pem of a certain type, for example
        'CERTIFICATE' or 'CERTIFICATE REQUEST'.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.get_pem_entry "-----BEGIN CERTIFICATE REQUEST-----MIICyzCC Ar8CAQI...-----END CERTIFICATE REQUEST"
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
    Returns a dict containing details of a certificate. Input can be a PEM string or file path.

    certificate:
        The certificate to be read. Can be a path to a certificate file, or a string containing
        the PEM formatted text of the certificate.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.read_certificate /etc/pki/mycert.crt
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
    Returns a dict containing details of a all certificates matching a glob

    glob_path:
        A path to certificates to be read and returned.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.read_certificates "/etc/pki/*.crt"
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
    Returns a dict containing details of a certificate request.

    :depends    - openssl command line tool

    param: csr:
        A path or PEM encoded string containing the CSR to read.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.read_csr /etc/pki/mycert.csr
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
    '''
    Returns a dict containing details of a certificate revocation list. Input can be a PEM string or file path.

    :depends    - openssl command line tool

    param: csl:
        A path or PEM encoded string containing the CSL to read.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.read_crl /etc/pki/mycrl.crl
    '''
    text = _text_or_file(crl)
    text = get_pem_entry(text, pem_type='X509 CRL')

    crltempfile = tempfile.NamedTemporaryFile()
    crltempfile.write(text)
    crltempfile.flush()
    crlparsed = _parse_openssl_crl(crltempfile.name)
    crltempfile.close()

    return crlparsed


def get_public_key(key):
    '''
    Returns a string containing the public key in PEM format.

    param: key:
        A path or PEM encoded string containing a CSR, Certificate or Private Key from which
        a public key can be retrieved.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.get_public_key /etc/pki/mycert.cer
    '''
    text = _text_or_file(key)

    text = get_pem_entry(text)

    if text.startswith('-----BEGIN PUBLIC KEY-----'):
        return text

    bio = M2Crypto.BIO.MemoryBuffer()
    if text.startswith('-----BEGIN CERTIFICATE-----'):
        cert = M2Crypto.X509.load_cert_string(text)
        rsa = cert.get_pubkey().get_rsa()
    if text.startswith('-----BEGIN CERTIFICATE REQUEST-----'):
        csr = M2Crypto.X509.load_request_string(text)
        rsa = csr.get_pubkey().get_rsa()
    if (text.startswith('-----BEGIN PRIVATE KEY-----') or
            text.startswith('-----BEGIN RSA PRIVATE KEY-----')):
        rsa = M2Crypto.RSA.load_key_string(text)

    rsa.save_pub_key_bio(bio)
    return bio.read_all()


def get_private_key_size(private_key):
    '''
    Returns the bit length of a private key in PEM format.

    param: private_key:
        A path or PEM encoded string containing a private key.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.get_private_key_size /etc/pki/mycert.key
    '''
    return _get_private_key_obj(private_key).size()*8


def write_pem(text, path, pem_type=None):
    '''
    Writes out a PEM string fixing any formatting or whitespace issues before writing.

    text:
        PEM string input to be written out.

    path:
        Path of the file to write the pem out to.

    pem_type:
        The PEM type to be saved, for example ``CERTIFICATE`` or ``PUBLIC KEY``. Adding this
        will allow the function to take input that may contain multiple pem types.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.write_pem "-----BEGIN CERTIFICATE-----MIIGMzCCBBugA..." path=/etc/pki/mycert.crt
    '''
    text = get_pem_entry(text, pem_type=pem_type)
    salt.utils.fopen(path, 'w').write(text)
    return 'PEM written to {0}'.format(path)


def create_private_key(path=None, text=False, bits=2048):
    '''
    Creates a private key in PEM format.

    path:
        The path to write the file to, either ``path`` or ``text`` are required.

    text:
        If ``True``, return the PEM text without writing to a file. Default ``False``.

    bits:
        Lenth of the private key in bits. Default 2048

    CLI Example:

    .. code-block:: bash

        salt '*' x509.create_private_key path=/etc/pki/mykey.key
    '''
    if not path and not text:
        raise salt.exceptions.SaltInvocationError('Either path or text must be specified.')
    if path and text:
        raise salt.exceptions.SaltInvocationError('Either path or text must be specified, not both.')

    rsa = M2Crypto.RSA.gen_key(bits, M2Crypto.m2.RSA_F4)
    bio = M2Crypto.BIO.MemoryBuffer()
    rsa.save_key_bio(bio, cipher=None)

    if path:
        return write_pem(text=bio.read_all(), path=path,
                pem_type='RSA PRIVATE KEY')
    else:
        return bio.read_all()


def create_crl(path=None, text=False, signing_private_key=None,
        signing_cert=None, revoked=None, include_expired=False,
        days_valid=100):
    '''
    Create a CRL

    :depends:   - PyOpenSSL Python module

    path:
        Path to write the crl to.

    text:
        If ``True``, return the PEM text without writing to a file. Default ``False``.

    signing_private_key:
        A path or string of the private key in PEM format that will be used to sign this crl.
        This is required.

    signing_cert:
        A certificate matching the private key that will be used to sign this crl. This is
        required.

    revoked:
        A list of dicts containing all the certificates to revoke. Each dict represents one
        certificate. A dict must contain either the key ``serial_number`` with the value of
        the serial number to revoke, or ``certificate`` with either the PEM encoded text of
        the certificate, or a path ot the certificate to revoke.

        The dict can optionally contain the ``revocation_date`` key. If this key is ommitted
        the revocation date will be set to now. If should be a string in the format "%Y-%m-%d %H:%M:%S".

        The dict can also optionally contain the ``not_after`` key. This is redundant if the
        ``certificate`` key is included. If the ``Certificate`` key is not included, this
        can be used for the logic behind the ``include_expired`` parameter.
        If should be a string in the format "%Y-%m-%d %H:%M:%S".

        The dict can also optionally contain the ``reason`` key. This is the reason code for the
        revocation. Available choices are ``unspecified``, ``keyCompromise``, ``CACompromise``,
        ``affiliationChanged``, ``superseded``, ``cessationOfOperation`` and ``certificateHold``.

    include_expired:
        Include expired certificates in the CRL. Default is ``False``.

    days_valid:
        The number of days that the CRL should be valid. This sets the Next Update field in the CRL.

    .. note

        At this time the pyOpenSSL library does not allow choosing a signing algorithm for CRLs
        See https://github.com/pyca/pyopenssl/issues/159
    '''
    # pyOpenSSL is required for dealing with CSLs. Importing inside these functions because
    # Client operations like creating CRLs shouldn't require pyOpenSSL
    # Note due to current limitations in pyOpenSSL it is impossible to specify a digest
    # For signing the CRL. This will hopefully be fixed soon: https://github.com/pyca/pyopenssl/pull/161
    import OpenSSL
    crl = OpenSSL.crypto.CRL()

    if revoked is None:
        revoked = []

    for rev_item in revoked:
        if 'certificate' in rev_item:
            rev_cert = read_certificate(rev_item['certificate'])
            rev_item['serial_number'] = rev_cert['Serial Number']
            rev_item['not_after'] = rev_cert['Not After']

        serial_number = rev_item['serial_number'].replace(':', '')
        serial_number = str(int(serial_number, 16))

        if 'not_after' in rev_item and not include_expired:
            not_after = datetime.datetime.strptime(rev_item['not_after'], '%Y-%m-%d %H:%M:%S')
            if datetime.datetime.now() > not_after:
                continue

        if not 'revocation_date' in rev_item:
            rev_item['revocation_date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        rev_date = datetime.datetime.strptime(rev_item['revocation_date'], '%Y-%m-%d %H:%M:%S')
        rev_date = rev_date.strftime('%Y%m%d%H%M%SZ')

        rev = OpenSSL.crypto.Revoked()
        rev.set_serial(serial_number)
        rev.set_rev_date(rev_date)

        if 'reason' in rev_item:
            rev.set_reason(rev_item['reason'])

        crl.add_revoked(rev)

    signing_cert = _text_or_file(signing_cert)
    cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM,
            get_pem_entry(signing_cert, pem_type='CERTIFICATE'))
    signing_private_key = _text_or_file(signing_private_key)
    key = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM,
            get_pem_entry(signing_private_key))

    crltext = crl.export(cert, key, OpenSSL.crypto.FILETYPE_PEM, days=days_valid)

    if text:
        return crltext

    return write_pem(text=crltext, path=path,
                pem_type='X509 CRL')


def create_certificate(path=None, text=False, subject=None,
        signing_private_key=None, signing_cert=None, public_key=None,
        csr=None, extensions=None, days_valid=365, version=3,
        serial_number=None, serial_bits=64,
        algorithm='sha256',):
    '''
    Create an X509 certificate.

    path:
        Path to write the certificate to.

    text:
        If ``True``, return the PEM text without writing to a file. Default ``False``.

    subject:
        A dict containing subject values. Some acceptable keys are: ``C``, ``CN``, ``Email``,
        ``GN``, ``L``, ``O``, ``OU``, ``SN``, ``SP`` and ``ST``. Any subject value accepted by
        OpenSSL should work.

    signing_private_key:
        A path or string of the private key in PEM format that will be used to sign this certificate.
        This is required.

    signing_cert:
        A certificate matching the private key that will be used to sign this certificate. This is used
        to populate the issuer values in the resulting certificate. Do not include this value for
        self-signed certificateds.

    public_key:
        The public key to be included in this certificate. This can be sourced from a public key,
        certificate, csr or private key. If neither ``public_key`` or ``csr`` are
        specified, it will be assumed that this is a self-signed certificate, and the public key
        derived from ``signing_private_key`` will be used. Specify either ``public_key`` or ``csr``,
        not both. Because you can input a CSR as a public key or as a CSR, it is important to understand
        the difference. If you import a CSR as a public key, only the public key will be added
        to the certificate, subject or extension information in the CSR will be lost.

    csr:
        A file or PEM string containing a certificate signing request. This will be used to supply the
        subject, extensions and public key of a certificate. Any subject or extensions specified
        explicitly will overwrite any in the CSR. If neither ``public_key`` or ``csr`` are specified,
        it will be assumed that this is a self-signed certificate, and the public key derived from
        ``signing_private_key`` will be used. Specify either ``public_key`` or ``csr``, not both.

    extensions:
        An ordered list of dicts containing values for X509v3 Extensions. Each dict must contain the
        keys ``name`` and ``value`` and may optionally contain the boolean ``critical``.

        Some special extensions are ``subjectKeyIdentifier`` and ``authorityKeyIdentifier``.

        ``subjectKeyIdentifier`` can be an explicit value or it can be the special string ``hash``.
        ``hash`` will set the subjectKeyIdentifier equal to the SHA1 hash of the modulus of the
        public key in this certificate. Note that this is not the exact same hashing method used by
        OpenSSL when using the hash value.

        ``authorityKeyIdentifier`` only supports the value ``keyid,issuer:always``. This value will
        automatically populate ``authorityKeyIdentifier`` with the ``subjectKeyIdentifier`` of
        ``signing_cert``. If this is a self-signed cert these values will be the same.

    days_valid:
        The number of days this certificate should be valid. This sets the ``notAfter`` property
        of the certificate. Defaults to 365.

    version:
        The version of the X509 certificate. Defaults to 3. This is automatically converted to the
        version value, so ``version=3`` sets the certificate version field to 0x2.

    serial_number:
        The serial number to assign to this certificate. If ommited a random serial number of size
        ``serial_bits`` is generated.

    serial_bits:
        The number of bits to use when randomly generating a serial number. Defaults to 64.

    algorithm:
        The hashing algorithm to be used for signing this certificate. Defaults to sha256.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.create_certificate path=/etc/pki/myca.crt signing_private_key=/etc/pki/myca.key csr=/etc/pki/myca.csr
    '''
    if not path and not text:
        raise salt.exceptions.SaltInvocationError('Either path or text must be specified.')
    if path and text:
        raise salt.exceptions.SaltInvocationError('Either path or text must be specified, not both.')

    if subject is None:
        subject = {}

    if extensions is None:
        extensions = []

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

    cert = M2Crypto.X509.X509()
    cert.set_serial_number(serial_number)
    # X509 Verison 3 has a value of 2 in the field.
    # Version 2 has a value of 1.
    # https://tools.ietf.org/html/rfc5280#section-4.1.2.1
    cert.set_version(version - 1)
    cert.set_subject(subject)
    cert.set_issuer(signing_cert_subject)
    cert.set_pubkey(public_key)

    not_before = M2Crypto.m2.x509_get_not_before(cert.x509)
    not_after = M2Crypto.m2.x509_get_not_after(cert.x509)
    M2Crypto.m2.x509_gmtime_adj(not_before, 0)
    M2Crypto.m2.x509_gmtime_adj(not_after, 60*60*24*days_valid)

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
                ext['value'] = 'self'
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


def create_csr(path=None, text=False, subject=None, public_key=None,
        extensions=None, version=3,):
    '''
    Create a certificate signing request.

    path:
        Path to write the certificate to.

    text:
        If ``True``, return the PEM text without writing to a file. Default ``False``.

    subject:
        A dict containing subject values. Some acceptable keys are: ``C``, ``CN``, ``Email``,
        ``GN``, ``L``, ``O``, ``OU``, ``SN``, ``SP`` and ``ST``. Any subject value accepted by
        OpenSSL should work.

    public_key:
        The public key to be included in this certificate. This can be sourced from a csr,
        certificate or private key.

    extensions:
        An ordered list of dicts containing values for X509v3 Extensions. Each dict must contain the
        keys ``name`` and ``value`` and may optionally contain the boolean ``critical``.

        ``subjectKeyIdentifier`` and ``authorityKeyIdentifier`` are not valid extensions to add
        to a CSR, because they are designed to be assigned by the signing authority.

    version:
        The version of the X509 certificate. Defaults to 3. This is automatically converted to the
        version value, so ``version=3`` sets the certificate version field to 0x2.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.create_csr path=/etc/pki/myca.csr public_key=/etc/pki/myca.key subject={'CN': 'My Cert'}
    '''
    if not path and not text:
        raise salt.exceptions.SaltInvocationError('Either path or text must be specified.')
    if path and text:
        raise salt.exceptions.SaltInvocationError('Either path or text must be specified, not both.')

    if subject is None:
        subject = {}

    if extensions is None:
        extensions = []

    subject = _parse_subject_in(subject)
    public_key = _get_public_key_obj(public_key)

    csr = M2Crypto.X509.Request()
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
    extstack = M2Crypto.X509.X509_Extension_Stack()
    for ext in extensions:
        extstack.push(ext)
    csr.add_extensions(extstack)

    if path:
        return write_pem(text=csr.as_pem(), path=path,
                pem_type='CERTIFICATE REQUEST')
    else:
        return csr.as_pem()


def request_certificate(path, ca_server, signing_policy, public_key=None, csr=None,
        with_grains=False, with_pillar=False):
    '''
    Request a signed certificate from a remote CA server.
    Requires the reactor /salt/x509/request_certificate to be configured.

    path: The path to save the signed certificate.

    ca_server: The minion ID of the remote server that needs to sign the request.

    signing_policy: The signing policy on the remote server to be used for
        signing this request.

    public_key: The public key to be included in the signed certificate. If a CSR
        is used, this is not required. If ``public_key`` is used only the public
        key will be submitted to the CA, the subject and extensions in the certificate will
        be entirely determined by the CA. This can also be the path to the private key.
        This argument will always be converted into a public key PEM before being transmitted
        to the event, so your private key will never leave the minion.

    csr: The CSR to be submitted. Using a csr rather than ``public_key`` allows
        submitting subject and extension values that the CA may honor. If the CA
        signing policy is not configured to allow csr's, only the public key included
        in the CSR will be used, all other values will be discarded.

    with_grains: Include grains from the current minion. The signing policy
        on the CA may use grains to populate subject fields. If so, this parameter
        must include the grains that are required by the CA.
    :type with_grains: Specify ``True`` to include all grains, or specify a
        list of strings of grain names to include.

    with_pillar: Include Pillar values from the current minion.
        The signing policy on the CA may use pillars to populate subject fields.
        If so, this parameter must include the pillars that are required by
        the CA.
    :type with_pillar: Specify ``True`` to include all Pillar values, or
        specify a list of strings of Pillar keys to include. It is a
        best-practice to only specify a relevant subset of Pillar data.
    '''
    if not public_key and not csr:
        raise salt.exceptions.SaltInvocationError('public_key or csr must be included')

    data = {'ca_server': ca_server,
            'signing_policy': signing_policy,
            'path': path}

    # Intentionally stripping new lines from returned PEM data, because they will be
    # inserted into user-created YAML reactors, and dealing with multi-line strings
    # in yaml is a pain. And they'll get nicely formatted on the way back into the x509
    # module anyway.
    if public_key:
        data['public_key'] = get_public_key(public_key).replace('\n', '')

    if csr:
        data['csr'] = get_pem_entry(csr, pem_type='CERTIFICATE REQUEST').replace('\n', '')

    return __salt__['event.send'](tag='/salt/x509/request_certificate', data=data,
            with_grains=with_grains, with_pillar=with_pillar)


def sign_request(path=None, text=False, requestor=None, signing_policy=None,
        signing_policy_def=None, public_key=None, csr=None, grains=None, pillar=None):
    '''
    Sign and return a remotely requested certificate based on the a signing policy in signing_policy_def


    path:
        Path to write the certificate to.

    text:
        If ``True``, return the PEM text without writing to a file. Default ``False``.

    requestor:
        The minion id of the client making this request.

    signing_policy:
        The name of the signing policy to be used to sign this request, must be defined in
        signing_policy_def

    signing_policy_def: The signing policies for this CA. Top level key will be
        used to match the minion. A match value can be included to determine how the minion is matched
        according to the :doc:`match module </ref/modules/salt.modules.match>`. This can parameter can
        be either a dict, a string containing a yaml definiton of the signing policy, a string
        referencing a yaml file containing the signing policy, or a string beginning with ``pillar:``
        followed by the name of the pillar which holds the signing policy.
        For example ``pillar:x509_signing_policy``.

    Example signing policy:

    .. code-block:: yaml

        x509_signing_policy:
          'pki':
            myca:
              signing_private_key: /etc/pki/ca.key
              signing_cert: /etc/pki/ca.crt
              csr: False
              subject:
                CN:
                  grain: 'fqdn'
                C: US
                ST: Utah
                L: Salt Lake City
                emailAddress:
                  pillar: 'x509:Email'
                  default: 'ca@example.com'
              extensions:
                - basicConstraints:
                    value: "CA:false"
                    critical: True
                - keyUsage:
                    value: "cRLSign, keyCertSign"
                    critical: True
                - subjectKeyIdentifier:
                    value: hash
                - authorityKeyIdentifier:
                    value: keyid,issuer:always
              days_valid: 90
              version: 3

    public_key:
        The public key to be signed by the CA. Either ``public_key`` or ``csr`` must be spcified.
        ``public_key`` can be the path to a file, or a string containing a CSR. If so, the other
        properties in the CSR, like subject and extensions are not included in the signed
        certificate.

    csr:
        A certificate signing request to use to generate the certificate. Any values specified in
        the CSR for subject or extensions will be overwritten by values explicitly configured in the
        signing policy.

    grains:
        Grains from the minion that may be used in the signing policy.

    pillar:
        Pillar values from the minion that may be used in the signing policy.
    '''
    if not path and not text:
        raise salt.exceptions.SaltInvocationError('Either path or text must be specified.')
    if path and text:
        raise salt.exceptions.SaltInvocationError('Either path or text must be specified, not both.')

    if grains is None:
        grains = {}

    if pillar is None:
        pillar = {}

    if public_key and csr:
        raise salt.exceptions.SaltInvocationError('Include either public_key or csr, not both.')

    if not signing_policy_def:
        raise salt.exceptions.SaltInvocationError('signing_policy_def is required.')

    if not signing_policy:
        raise salt.exceptions.SaltInvocationError('signing_policy is required.')

    if not isinstance(signing_policy_def, dict):
        if signing_policy_def.startswith('pillar:'):
            signing_policy_def = signing_policy_def.replace('pillar:', '')
            signing_policy_def = __salt__['pillar.get'](signing_policy_def)
        else:
            signing_policy_def = _text_or_file(signing_policy_def)

    for target, policy in signing_policy_def.iteritems():
        if 'match' not in policy:
            policy['match'] = 'glob'

        if not __salt__['match.' + policy['match']](target, requestor):
            continue

        if not signing_policy in policy:
            continue

        signing_policy = policy[signing_policy]

        if csr and 'csr' in signing_policy and signing_policy['csr'] == True:
            continue
        elif csr:
            public_key = csr
            csr = None

        if not public_key:
            raise salt.exceptions.SaltInvocationError('public_key is required')

        # default values from signing_policy:
        defaults = {'subject': {}, 'extensions': [],
                'days_valid': 365, 'version': 3, 'serial_number': None,
                'serial_bits': 64, 'algorithm': 'sha256'}

        # Set initial simple values form signing_policy where they exist
        for prop, val in defaults.iteritems():
            if prop not in signing_policy:
                signing_policy[prop] = val

        # Subject is a dict, because order is irrelevant
        if 'subject' in signing_policy:
            for entry, val in signing_policy['subject'].iteritems():
                if not isinstance(val, dict):
                    continue

                if 'grain' in val:
                    try:
                        val = grains[val['grain']]
                    except KeyError:
                        try:
                            val = val['default']
                        except KeyError:
                            raise salt.exceptions.SaltInvocationError('grain {0} not found '
                            'and no default included for {1}.'.format(val['grain'], entry))

                if 'pillar' in val:
                    try:
                        val = pillar[val['pillar']]
                    except KeyError:
                        try:
                            val = val['default']
                        except KeyError:
                            raise salt.exceptions.SaltInvocationError('pillar {0} not found '
                            'and no default included for {1}.'.format(val['pillar'], entry))

                signing_policy['subject'][entry] = val

        # Extensions are a list of dicts, because order matters.
        if 'extensions' in signing_policy:
            for idx, extension in enumerate(signing_policy['extensions']):
                for ext_name, ext_props in extension.iteritems():
                    ext_props['name'] = ext_name

                    val = ext_props['value']

                    if 'grain' in val:
                        try:
                            val = grains[val['grain']]
                        except KeyError:
                            try:
                                val = val['default']
                            except KeyError:
                                raise salt.exceptions.SaltInvocationError('grain {0} not found '
                                'and no default included for {1}.'.format(val['grain'], ext_name))

                    if 'pillar' in val:
                        try:
                            val = pillar[val['pillar']]
                        except KeyError:
                            try:
                                val = val['default']
                            except KeyError:
                                raise salt.exceptions.SaltInvocationError('pillar {0} not found '
                                'and no default included for {1}.'.format(val['pillar'], ext_name))

                    ext_props['value'] = val
                    signing_policy['extensions'][idx] = ext_props

    if 'signing_private_key' not in signing_policy or 'signing_cert' not in signing_policy:
        return "Invalid signing policy"

    return create_certificate(path=path, text=text, public_key=public_key, csr=csr,
            subject=signing_policy['subject'],
            signing_private_key=signing_policy['signing_private_key'],
            signing_cert=signing_policy['signing_cert'],
            extensions=signing_policy['extensions'],
            days_valid=signing_policy['days_valid'],
            version=signing_policy['version'],
            serial_number=signing_policy['serial_number'],
            serial_bits=signing_policy['serial_bits'],
            algorithm=signing_policy['algorithm'],)


def verify_private_key(private_key, public_key):
    '''
    Verify that 'private_key' matches 'public_key'

    private_key:
        The private key to verify, can be a string or path to a private key in PEM format.

    public_key:
        The public key to verify, can be a string or path to a PEM formatted certificate, csr,
        or another private key.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.verify_private_key private_key=/etc/pki/myca.key public_key=/etc/pki/myca.crt
    '''
    return bool(get_public_key(private_key) == get_public_key(public_key))


def verify_signature(certificate, signing_pub_key=None):
    '''
    Verify that ``certificate`` has been signed by ``signing_pub_key``

    certificate:
        The certificate to verify. Can be a path or string containing a PEM formatted certificate.

    signing_pub_key:
        The public key to verify, can be a string or path to a PEM formatted certificate, csr,
        or private key.

    CLI Example:

    .. code-block:: bash

        salt '*' x509.verify_private_key private_key=/etc/pki/myca.key public_key=/etc/pki/myca.crt
    '''
    cert = _get_certificate_obj(certificate)

    if signing_pub_key:
        signing_pub_key = _get_public_key_obj(signing_pub_key)

    return bool(cert.verify(pkey=signing_pub_key) == 1)
