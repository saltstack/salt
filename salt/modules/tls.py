# -*- coding: utf-8 -*-
r'''
A salt module for SSL/TLS.
Can create a Certificate Authority (CA)
or use Self-Signed certificates.

:depends:   - PyOpenSSL Python module (0.10 or later, 0.14 or later for
              X509 extension support)
:configuration: Add the following values in /etc/salt/minion for the CA module
    to function properly:

    .. code-block:: yaml

        ca.cert_base_path: '/etc/pki'


CLI Example #1
Creating a CA, a server request and its signed certificate:

.. code-block:: bash

    # salt-call tls.create_ca my_little \
    days=5 \
    CN='My Little CA' \
    C=US \
    ST=Utah \
    L=Salt Lake City \
    O=Saltstack \
    emailAddress=pleasedontemail@example.com

    Created Private Key: "/etc/pki/my_little/my_little_ca_cert.key"
    Created CA "my_little_ca": "/etc/pki/my_little_ca/my_little_ca_cert.crt"

    # salt-call tls.create_csr my_little CN=www.example.com
    Created Private Key: "/etc/pki/my_little/certs/www.example.com.key
    Created CSR for "www.example.com": "/etc/pki/my_little/certs/www.example.com.csr"

    # salt-call tls.create_ca_signed_cert my_little CN=www.example.com
    Created Certificate for "www.example.com": /etc/pki/my_little/certs/www.example.com.crt"

CLI Example #2:
Creating a client request and its signed certificate

.. code-block:: bash

    # salt-call tls.create_csr my_little CN=DBReplica_No.1 cert_type=client
    Created Private Key: "/etc/pki/my_little/certs//DBReplica_No.1.key."
    Created CSR for "DBReplica_No.1": "/etc/pki/my_little/certs/DBReplica_No.1.csr."

    # salt-call tls.create_ca_signed_cert my_little CN=DBReplica_No.1
    Created Certificate for "DBReplica_No.1": "/etc/pki/my_little/certs/DBReplica_No.1.crt"

CLI Example #3:
Creating both a server and client req + cert for the same CN

.. code-block:: bash

    # salt-call tls.create_csr my_little CN=MasterDBReplica_No.2  \
        cert_type=client
    Created Private Key: "/etc/pki/my_little/certs/MasterDBReplica_No.2.key."
    Created CSR for "DBReplica_No.1": "/etc/pki/my_little/certs/MasterDBReplica_No.2.csr."

    # salt-call tls.create_ca_signed_cert my_little CN=MasterDBReplica_No.2
    Created Certificate for "DBReplica_No.1": "/etc/pki/my_little/certs/DBReplica_No.1.crt"

    # salt-call tls.create_csr my_little CN=MasterDBReplica_No.2 \
        cert_type=server
    Certificate "MasterDBReplica_No.2" already exists

    (doh!)

    # salt-call tls.create_csr my_little CN=MasterDBReplica_No.2 \
        cert_type=server type_ext=True
    Created Private Key: "/etc/pki/my_little/certs/DBReplica_No.1_client.key."
    Created CSR for "DBReplica_No.1": "/etc/pki/my_little/certs/DBReplica_No.1_client.csr."

    # salt-call tls.create_ca_signed_cert my_little CN=MasterDBReplica_No.2
    Certificate "MasterDBReplica_No.2" already exists

    (DOH!)

    # salt-call tls.create_ca_signed_cert my_little CN=MasterDBReplica_No.2 \
        cert_type=server type_ext=True
    Created Certificate for "MasterDBReplica_No.2": "/etc/pki/my_little/certs/MasterDBReplica_No.2_server.crt"


CLI Example #4:
Create a server req + cert with non-CN filename for the cert

.. code-block:: bash

    # salt-call tls.create_csr my_little CN=www.anothersometh.ing \
        cert_type=server type_ext=True
    Created Private Key: "/etc/pki/my_little/certs/www.anothersometh.ing_server.key."
    Created CSR for "DBReplica_No.1": "/etc/pki/my_little/certs/www.anothersometh.ing_server.csr."

    # salt-call tls_create_ca_signed_cert my_little CN=www.anothersometh.ing \
        cert_type=server cert_filename="something_completely_different"
    Created Certificate for "www.anothersometh.ing": /etc/pki/my_little/certs/something_completely_different.crt
'''
from __future__ import absolute_import
# pylint: disable=C0103

# Import python libs
import os
import time
import calendar
import logging
import math
import binascii
import salt.utils
from salt._compat import string_types
from salt.ext.six.moves import range as _range
from datetime import datetime
from distutils.version import LooseVersion  # pylint: disable=no-name-in-module

import re

HAS_SSL = False
X509_EXT_ENABLED = True
try:
    import OpenSSL
    HAS_SSL = True
    OpenSSL_version = LooseVersion(OpenSSL.__dict__.get('__version__', '0.0'))
except ImportError:
    pass

# Import salt libs


log = logging.getLogger(__name__)

two_digit_year_fmt = "%y%m%d%H%M%SZ"
four_digit_year_fmt = "%Y%m%d%H%M%SZ"


def __virtual__():
    '''
    Only load this module if the ca config options are set
    '''
    global X509_EXT_ENABLED
    if HAS_SSL and OpenSSL_version >= LooseVersion('0.10'):
        if OpenSSL_version < LooseVersion('0.14'):
            X509_EXT_ENABLED = False
            log.debug('You should upgrade pyOpenSSL to at least 0.14.1 to '
                      'enable the use of X509 extensions in the tls module')
        elif OpenSSL_version <= LooseVersion('0.15'):
            log.debug('You should upgrade pyOpenSSL to at least 0.15.1 to '
                      'enable the full use of X509 extensions in the tls module')
        # NOTE: Not having configured a cert path should not prevent this
        # module from loading as it provides methods to configure the path.
        return True
    else:
        X509_EXT_ENABLED = False
        return (False, 'PyOpenSSL version 0.10 or later must be installed '
                       'before this module can be used.')


def _microtime():
    '''
    Return a Unix timestamp as a string of digits
    :return:
    '''
    val1, val2 = math.modf(time.time())
    val2 = int(val2)
    return '{0:f}{1}'.format(val1, val2)


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
        cacert_path = __context__.get(
            'ca.contextual_cert_base_path',
            __salt__['config.option']('ca.contextual_cert_base_path'))
    if not cacert_path:
        cacert_path = __context__.get(
            'ca.cert_base_path',
            __salt__['config.option']('ca.cert_base_path'))
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
        __context__['ca.contextual_cert_base_path'] = cacert_path
    return cert_base_path()


def _new_serial(ca_name):
    '''
    Return a serial number in hex using os.urandom() and a Unix timestamp
    in microseconds.

    ca_name
        name of the CA
    CN
        common name in the request
    '''
    hashnum = int(
        binascii.hexlify(
            '{0}_{1}'.format(
                _microtime(),
                os.urandom(5))),
        16
    )
    log.debug('Hashnum: {0}'.format(hashnum))

    # record the hash somewhere
    cachedir = __opts__['cachedir']
    log.debug('cachedir: {0}'.format(cachedir))
    serial_file = '{0}/{1}.serial'.format(cachedir, ca_name)
    if not os.path.exists(cachedir):
        os.makedirs(cachedir)
    if not os.path.exists(serial_file):
        fd = salt.utils.fopen(serial_file, 'w')
    else:
        fd = salt.utils.fopen(serial_file, 'a+')
    with fd as ofile:
        ofile.write(str(hashnum))

    return hashnum


def _four_digit_year_to_two_digit(datetimeObj):
    return datetimeObj.strftime(two_digit_year_fmt)


def _get_basic_info(ca_name, cert, ca_dir=None):
    '''
    Get basic info to write out to the index.txt
    '''
    if ca_dir is None:
        ca_dir = '{0}/{1}'.format(_cert_base_path(), ca_name)

    index_file = "{0}/index.txt".format(ca_dir)

    expire_date = _four_digit_year_to_two_digit(
        datetime.strptime(
            cert.get_notAfter(),
            four_digit_year_fmt)
    )
    serial_number = format(cert.get_serial_number(), 'X')

    # gotta prepend a /
    subject = '/'

    # then we can add the rest of the subject
    subject += '/'.join(
        ['{0}={1}'.format(
            x, y
        ) for x, y in cert.get_subject().get_components()]
    )
    subject += '\n'

    return (index_file, expire_date, serial_number, subject)


def _write_cert_to_database(ca_name, cert, cacert_path=None, status='V'):
    '''
    write out the index.txt database file in the appropriate directory to
    track certificates

    ca_name
        name of the CA
    cert
        certificate to be recorded
    '''
    set_ca_path(cacert_path)
    ca_dir = '{0}/{1}'.format(cert_base_path(), ca_name)
    index_file, expire_date, serial_number, subject = _get_basic_info(
        ca_name,
        cert,
        ca_dir)

    index_data = '{0}\t{1}\t\t{2}\tunknown\t{3}'.format(
        status,
        expire_date,
        serial_number,
        subject
    )

    with salt.utils.fopen(index_file, 'a+') as ofile:
        ofile.write(index_data)


def maybe_fix_ssl_version(ca_name, cacert_path=None, ca_filename=None):
    '''
    Check that the X509 version is correct
    (was incorrectly set in previous salt versions).
    This will fix the version if needed.

    ca_name
        ca authority name
    cacert_path
        absolute path to ca certificates root directory
    ca_filename
        alternative filename for the CA

        .. versionadded:: 2015.5.3


    CLI Example:

    .. code-block:: bash

        salt '*' tls.maybe_fix_ssl_version test_ca /etc/certs
    '''
    set_ca_path(cacert_path)
    if not ca_filename:
        ca_filename = '{0}_ca_cert'.format(ca_name)
    certp = '{0}/{1}/{2}.crt'.format(
            cert_base_path(),
            ca_name,
            ca_filename)
    ca_keyp = '{0}/{1}/{2}.key'.format(
        cert_base_path(),
        ca_name,
        ca_filename)
    with salt.utils.fopen(certp) as fic:
        cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM,
                                               fic.read())
        if cert.get_version() == 3:
            log.info(
                'Regenerating wrong x509 version '
                'for certificate {0}'.format(certp))
            with salt.utils.fopen(ca_keyp) as fic2:
                try:
                    # try to determine the key bits
                    key = OpenSSL.crypto.load_privatekey(
                        OpenSSL.crypto.FILETYPE_PEM, fic2.read())
                    bits = key.bits()
                except Exception:
                    bits = 2048
                try:
                    days = (datetime.strptime(
                        cert.get_notAfter(),
                        '%Y%m%d%H%M%SZ') - datetime.utcnow()).days
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


def ca_exists(ca_name, cacert_path=None, ca_filename=None):
    '''
    Verify whether a Certificate Authority (CA) already exists

    ca_name
        name of the CA
    cacert_path
        absolute path to ca certificates root directory
    ca_filename
        alternative filename for the CA

        .. versionadded:: 2015.5.3


    CLI Example:

    .. code-block:: bash

        salt '*' tls.ca_exists test_ca /etc/certs
    '''
    set_ca_path(cacert_path)
    if not ca_filename:
        ca_filename = '{0}_ca_cert'.format(ca_name)
    certp = '{0}/{1}/{2}.crt'.format(
            cert_base_path(),
            ca_name,
            ca_filename)
    if os.path.exists(certp):
        maybe_fix_ssl_version(ca_name,
                              cacert_path=cacert_path,
                              ca_filename=ca_filename)
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
        raise ValueError('Certificate does not exist for {0}'.format(ca_name))
    else:
        if as_text:
            with salt.utils.fopen(certp) as fic:
                certp = fic.read()
    return certp


def get_ca_signed_cert(ca_name,
                       CN='localhost',
                       as_text=False,
                       cacert_path=None,
                       cert_filename=None):
    '''
    Get the certificate path or content

    ca_name
        name of the CA
    CN
        common name of the certificate
    as_text
        if true, return the certificate content instead of the path
    cacert_path
        absolute path to certificates root directory
    cert_filename
        alternative filename for the certificate, useful when using special characters in the CN

        .. versionadded:: 2015.5.3


    CLI Example:

    .. code-block:: bash

        salt '*' tls.get_ca_signed_cert test_ca CN=localhost as_text=False cacert_path=/etc/certs
    '''
    set_ca_path(cacert_path)
    if not cert_filename:
        cert_filename = CN

    certp = '{0}/{1}/certs/{2}.crt'.format(
            cert_base_path(),
            ca_name,
            cert_filename)
    if not os.path.exists(certp):
        raise ValueError('Certificate does not exists for {0}'.format(CN))
    else:
        if as_text:
            with salt.utils.fopen(certp) as fic:
                certp = fic.read()
    return certp


def get_ca_signed_key(ca_name,
                      CN='localhost',
                      as_text=False,
                      cacert_path=None,
                      key_filename=None):
    '''
    Get the certificate path or content

    ca_name
        name of the CA
    CN
        common name of the certificate
    as_text
        if true, return the certificate content instead of the path
    cacert_path
        absolute path to certificates root directory
    key_filename
        alternative filename for the key, useful when using special characters

        .. versionadded:: 2015.5.3

        in the CN

    CLI Example:

    .. code-block:: bash

        salt '*' tls.get_ca_signed_key \
                test_ca CN=localhost \
                as_text=False \
                cacert_path=/etc/certs
    '''
    set_ca_path(cacert_path)
    if not key_filename:
        key_filename = CN

    keyp = '{0}/{1}/certs/{2}.key'.format(
        cert_base_path(),
        ca_name,
        key_filename)
    if not os.path.exists(keyp):
        raise ValueError('Certificate does not exists for {0}'.format(CN))
    else:
        if as_text:
            with salt.utils.fopen(keyp) as fic:
                keyp = fic.read()
    return keyp


def _check_onlyif_unless(onlyif, unless):
    ret = None
    retcode = __salt__['cmd.retcode']
    if onlyif is not None:
        if not isinstance(onlyif, string_types):
            if not onlyif:
                ret = {'comment': 'onlyif execution failed', 'result': True}
        elif isinstance(onlyif, string_types):
            if retcode(onlyif) != 0:
                ret = {'comment': 'onlyif execution failed', 'result': True}
                log.debug('onlyif execution failed')
    if unless is not None:
        if not isinstance(unless, string_types):
            if unless:
                ret = {'comment': 'unless execution succeeded', 'result': True}
        elif isinstance(unless, string_types):
            if retcode(unless) == 0:
                ret = {'comment': 'unless execution succeeded', 'result': True}
                log.debug('unless execution succeeded')
    return ret


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
              cacert_path=None,
              ca_filename=None,
              digest='sha256',
              onlyif=None,
              unless=None,
              replace=False):
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
    ca_filename
        alternative filename for the CA

        .. versionadded:: 2015.5.3

    digest
        The message digest algorithm. Must be a string describing a digest
        algorithm supported by OpenSSL (by EVP_get_digestbyname, specifically).
        For example, "md5" or "sha1". Default: 'sha256'
    replace
        Replace this certificate even if it exists

        .. versionadded:: 2015.5.1

    Writes out a CA certificate based upon defined config values. If the file
    already exists, the function just returns assuming the CA certificate
    already exists.

    If the following values were set::

        ca.cert_base_path='/etc/pki'
        ca_name='koji'

    the resulting CA, and corresponding key, would be written in the following
    location::

        /etc/pki/koji/koji_ca_cert.crt
        /etc/pki/koji/koji_ca_cert.key

    CLI Example:

    .. code-block:: bash

        salt '*' tls.create_ca test_ca
    '''
    status = _check_onlyif_unless(onlyif, unless)
    if status is not None:
        return None

    set_ca_path(cacert_path)

    if not ca_filename:
        ca_filename = '{0}_ca_cert'.format(ca_name)

    certp = '{0}/{1}/{2}.crt'.format(
        cert_base_path(), ca_name, ca_filename)
    ca_keyp = '{0}/{1}/{2}.key'.format(
        cert_base_path(), ca_name, ca_filename)
    if not replace and not fixmode and ca_exists(ca_name, ca_filename=ca_filename):
        return 'Certificate for CA named "{0}" already exists'.format(ca_name)

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
        with salt.utils.fopen(ca_keyp) as fic2:
            # try to determine the key bits
            try:
                key = OpenSSL.crypto.load_privatekey(
                    OpenSSL.crypto.FILETYPE_PEM, fic2.read())
            except OpenSSL.crypto.Error as err:
                log.warning('Error loading existing private key'
                    ' %s, generating a new key: %s', ca_keyp, str(err))
                bck = "{0}.unloadable.{1}".format(ca_keyp,
                    datetime.utcnow().strftime("%Y%m%d%H%M%S"))
                log.info('Saving unloadable CA ssl key in {0}'.format(bck))
                os.rename(ca_keyp, bck)

    if not key:
        key = OpenSSL.crypto.PKey()
        key.generate_key(OpenSSL.crypto.TYPE_RSA, bits)

    ca = OpenSSL.crypto.X509()
    ca.set_version(2)
    ca.set_serial_number(_new_serial(ca_name))
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

    if X509_EXT_ENABLED:
        ca.add_extensions([
            OpenSSL.crypto.X509Extension('basicConstraints', True,
                                         'CA:TRUE, pathlen:0'),
            OpenSSL.crypto.X509Extension('keyUsage', True,
                                         'keyCertSign, cRLSign'),
            OpenSSL.crypto.X509Extension('subjectKeyIdentifier', False,
                                         'hash', subject=ca)])

        ca.add_extensions([
            OpenSSL.crypto.X509Extension(
                'authorityKeyIdentifier',
                False,
                'issuer:always,keyid:always',
                issuer=ca)])
    ca.sign(key, digest)

    # always backup existing keys in case
    keycontent = OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM,
                                                key)
    write_key = True
    if os.path.exists(ca_keyp):
        bck = "{0}.{1}".format(ca_keyp, datetime.utcnow().strftime(
            "%Y%m%d%H%M%S"))
        with salt.utils.fopen(ca_keyp) as fic:
            old_key = fic.read().strip()
            if old_key.strip() == keycontent.strip():
                write_key = False
            else:
                log.info('Saving old CA ssl key in {0}'.format(bck))
                with salt.utils.fopen(bck, 'w') as bckf:
                    bckf.write(old_key)
                    os.chmod(bck, 0o600)
    if write_key:
        with salt.utils.fopen(ca_keyp, 'w') as ca_key:
            ca_key.write(keycontent)

    with salt.utils.fopen(certp, 'w') as ca_crt:
        ca_crt.write(
            OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, ca))

    _write_cert_to_database(ca_name, ca)

    ret = ('Created Private Key: "{0}/{1}/{2}.key." ').format(
        cert_base_path(), ca_name, ca_filename)
    ret += ('Created CA "{0}": "{1}/{2}/{3}.crt."').format(
        ca_name, cert_base_path(), ca_name, ca_filename)

    return ret


def get_extensions(cert_type):
    '''
    Fetch X509 and CSR extension definitions from tls:extensions:
    (common|server|client) or set them to standard defaults.

    .. versionadded:: 2015.8.0

    cert_type:
        The type of certificate such as ``server`` or ``client``.

    CLI Example:

    .. code-block:: bash

        salt '*' tls.get_extensions client

    '''

    assert X509_EXT_ENABLED, ('X509 extensions are not supported in '
                              'pyOpenSSL prior to version 0.15.1. Your '
                              'version: {0}'.format(OpenSSL_version))

    ext = {}
    if cert_type == '':
        log.error('cert_type set to empty in tls_ca.get_extensions(); '
                  'defaulting to ``server``')
        cert_type = 'server'

    try:
        ext['common'] = __salt__['pillar.get']('tls.extensions:common', False)
    except NameError as err:
        log.debug(err)

    if not ext['common'] or ext['common'] == '':
        ext['common'] = {
            'csr': {
                'basicConstraints': 'CA:FALSE',
            },
            'cert': {
                'authorityKeyIdentifier': 'keyid,issuer:always',
                'subjectKeyIdentifier': 'hash',
            },
        }

    try:
        ext['server'] = __salt__['pillar.get']('tls.extensions:server', False)
    except NameError as err:
        log.debug(err)

    if not ext['server'] or ext['server'] == '':
        ext['server'] = {
            'csr': {
                'extendedKeyUsage': 'serverAuth',
                'keyUsage': 'digitalSignature, keyEncipherment',
            },
            'cert': {},
        }

    try:
        ext['client'] = __salt__['pillar.get']('tls.extensions:client', False)
    except NameError as err:
        log.debug(err)

    if not ext['client'] or ext['client'] == '':
        ext['client'] = {
            'csr': {
                'extendedKeyUsage': 'clientAuth',
                'keyUsage': 'nonRepudiation, digitalSignature, keyEncipherment',
            },
            'cert': {},
        }

    # possible user-defined profile or a typo
    if cert_type not in ext:
        try:
            ext[cert_type] = __salt__['pillar.get'](
                'tls.extensions:{0}'.format(cert_type))
        except NameError as e:
            log.debug(
                'pillar, tls:extensions:{0} not available or '
                'not operating in a salt context\n{1}'.format(cert_type, e))

    retval = ext['common']

    for Use in retval:
        retval[Use].update(ext[cert_type][Use])

    return retval


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
               cacert_path=None,
               ca_filename=None,
               csr_path=None,
               csr_filename=None,
               digest='sha256',
               type_ext=False,
               cert_type='server',
               replace=False):
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
        this function with this value:

        examples: ['DNS:somednsname.com',
                'DNS:1.2.3.4',
                'IP:1.2.3.4',
                'IP:2001:4801:7821:77:be76:4eff:fe11:e51',
                'email:me@i.like.pie.com']

    .. note::
        some libraries do not properly query IP: prefixes, instead looking
        for the given req. source with a DNS: prefix. To be thorough, you
        may want to include both DNS: and IP: entries if you are using
        subjectAltNames for destinations for your TLS connections.
        e.g.:
        requests to https://1.2.3.4 will fail from python's
        requests library w/out the second entry in the above list

    .. versionadded:: 2015.8.0

    cert_type
        Specify the general certificate type. Can be either `server` or
        `client`. Indicates the set of common extensions added to the CSR.

        .. code-block:: cfg

            server: {
               'basicConstraints': 'CA:FALSE',
               'extendedKeyUsage': 'serverAuth',
               'keyUsage': 'digitalSignature, keyEncipherment'
            }

            client: {
               'basicConstraints': 'CA:FALSE',
               'extendedKeyUsage': 'clientAuth',
               'keyUsage': 'nonRepudiation, digitalSignature, keyEncipherment'
            }

    type_ext
        boolean.  Whether or not to extend the filename with CN_[cert_type]
        This can be useful if a server and client certificate are needed for
        the same CN. Defaults to False to avoid introducing an unexpected file
        naming pattern

        The files normally named some_subject_CN.csr and some_subject_CN.key
        will then be saved

    replace
        Replace this signing request even if it exists

        .. versionadded:: 2015.5.1

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

    if not ca_filename:
        ca_filename = '{0}_ca_cert'.format(ca_name)

    if not ca_exists(ca_name, ca_filename=ca_filename):
        return ('Certificate for CA named "{0}" does not exist, please create '
                'it first.').format(ca_name)

    if not csr_path:
        csr_path = '{0}/{1}/certs/'.format(cert_base_path(), ca_name)

    if not os.path.exists(csr_path):
        os.makedirs(csr_path)

    CN_ext = '_{0}'.format(cert_type) if type_ext else ''

    if not csr_filename:
        csr_filename = '{0}{1}'.format(CN, CN_ext)

    csr_f = '{0}/{1}.csr'.format(csr_path, csr_filename)

    if not replace and os.path.exists(csr_f):
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

    try:
        extensions = get_extensions(cert_type)['csr']

        extension_adds = []

        for ext, value in extensions.items():
            extension_adds.append(OpenSSL.crypto.X509Extension(ext, False,
                                                               value))

    except AssertionError as err:
        log.error(err)
        extensions = []

    if subjectAltName:
        if X509_EXT_ENABLED:
            if isinstance(subjectAltName, str):
                subjectAltName = [subjectAltName]

            extension_adds.append(
                OpenSSL.crypto.X509Extension(
                    'subjectAltName', False, ", ".join(subjectAltName)))
        else:
            raise ValueError('subjectAltName cannot be set as X509 '
                             'extensions are not supported in pyOpenSSL '
                             'prior to version 0.15.1. Your '
                             'version: {0}.'.format(OpenSSL_version))

    if X509_EXT_ENABLED:
        req.add_extensions(extension_adds)

    req.set_pubkey(key)
    req.sign(key, digest)

    # Write private key and request
    with salt.utils.fopen('{0}/{1}.key'.format(csr_path,
                                               csr_filename), 'w+') as priv_key:
        priv_key.write(
            OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key)
        )

    with salt.utils.fopen(csr_f, 'w+') as csr:
        csr.write(
            OpenSSL.crypto.dump_certificate_request(
                OpenSSL.crypto.FILETYPE_PEM,
                req
            )
        )

    ret = 'Created Private Key: "{0}{1}.key." '.format(
        csr_path,
        csr_filename
    )
    ret += 'Created CSR for "{0}": "{1}{2}.csr."'.format(
        CN,
        csr_path,
        csr_filename
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
                            cacert_path=None,
                            cert_filename=None,
                            digest='sha256',
                            replace=False):
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
    digest
        The message digest algorithm. Must be a string describing a digest
        algorithm supported by OpenSSL (by EVP_get_digestbyname, specifically).
        For example, "md5" or "sha1". Default: 'sha256'
    replace
        Replace this certificate even if it exists

        .. versionadded:: 2015.5.1

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

    if not cert_filename:
        cert_filename = CN

    if not replace and os.path.exists(
            '{0}/{1}/certs/{2}.crt'.format(cert_base_path(),
                                           tls_dir, cert_filename)
    ):
        return 'Certificate "{0}" already exists'.format(cert_filename)

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

    cert.set_serial_number(_new_serial(tls_dir))
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, digest)

    # Write private key and cert
    with salt.utils.fopen(
        '{0}/{1}/certs/{2}.key'.format(cert_base_path(),
                                       tls_dir, cert_filename),
        'w+'
    ) as priv_key:
        priv_key.write(
            OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key)
        )

    with salt.utils.fopen('{0}/{1}/certs/{2}.crt'.format(cert_base_path(),
                                                         tls_dir,
                                                         cert_filename
                                                         ), 'w+') as crt:
        crt.write(
            OpenSSL.crypto.dump_certificate(
                OpenSSL.crypto.FILETYPE_PEM,
                cert
            )
        )

    _write_cert_to_database(tls_dir, cert)

    ret = 'Created Private Key: "{0}/{1}/certs/{2}.key." '.format(
        cert_base_path(),
        tls_dir,
        cert_filename
    )
    ret += 'Created Certificate: "{0}/{1}/certs/{2}.crt."'.format(
        cert_base_path(),
        tls_dir,
        cert_filename
    )

    return ret


def create_ca_signed_cert(ca_name,
                          CN,
                          days=365,
                          cacert_path=None,
                          ca_filename=None,
                          cert_path=None,
                          cert_filename=None,
                          digest='sha256',
                          cert_type=None,
                          type_ext=False,
                          replace=False):
    '''
    Create a Certificate (CERT) signed by a named Certificate Authority (CA)

    If the certificate file already exists, the function just returns assuming
    the CERT already exists.

    The CN *must* match an existing CSR generated by create_csr. If it
    does not, this method does nothing.

    ca_name
        name of the CA
    CN
        common name matching the certificate signing request
    days
        number of days certificate is valid, default is 365 (1 year)

    cacert_path
        absolute path to ca certificates root directory

    ca_filename
        alternative filename for the CA

        .. versionadded:: 2015.5.3


    cert_path
        full path to the certificates directory

    cert_filename
        alternative filename for the certificate, useful when using special
        characters in the CN. If this option is set it will override
        the certificate filename output effects of ``cert_type``.
        ``type_ext`` will be completely overridden.

        .. versionadded:: 2015.5.3


    digest
        The message digest algorithm. Must be a string describing a digest
        algorithm supported by OpenSSL (by EVP_get_digestbyname, specifically).
        For example, "md5" or "sha1". Default: 'sha256'
    replace
        Replace this certificate even if it exists

        .. versionadded:: 2015.5.1

    cert_type
        string. Either 'server' or 'client' (see create_csr() for details).

        If create_csr(type_ext=True) this function **must** be called with the
        same cert_type so it can find the CSR file.

    .. note::
        create_csr() defaults to cert_type='server'; therefore, if it was also
        called with type_ext, cert_type becomes a required argument for
        create_ca_signed_cert()

    type_ext
        bool. If set True, use ``cert_type`` as an extension to the CN when
        formatting the filename.

        e.g.: some_subject_CN_server.crt or some_subject_CN_client.crt

        This facilitates the context where both types are required for the same
        subject

        If ``cert_filename`` is `not None`, setting ``type_ext`` has no
        effect

    If the following values were set:

    .. code-block:: text

        ca.cert_base_path='/etc/pki'
        ca_name='koji'
        CN='test.egavas.org'

    the resulting signed certificate would be written in the following
    location:

    .. code-block:: text

        /etc/pki/koji/certs/test.egavas.org.crt

    CLI Example:

    .. code-block:: bash

        salt '*' tls.create_ca_signed_cert test localhost
    '''
    ret = {}

    set_ca_path(cacert_path)

    if not ca_filename:
        ca_filename = '{0}_ca_cert'.format(ca_name)

    if not cert_path:
        cert_path = '{0}/{1}/certs'.format(cert_base_path(), ca_name)

    if type_ext:
        if not cert_type:
            log.error('type_ext = True but cert_type is unset. '
                      'Certificate not written.')
            return ret
        elif cert_type:
            CN_ext = '_{0}'.format(cert_type)
    else:
        CN_ext = ''

    csr_filename = '{0}{1}'.format(CN, CN_ext)

    if not cert_filename:
        cert_filename = '{0}{1}'.format(CN, CN_ext)

    if not replace and os.path.exists(
            os.path.join(
                os.path.sep.join('{0}/{1}/certs/{2}.crt'.format(
                    cert_base_path(),
                    ca_name,
                    cert_filename).split('/')
                )
            )
    ):
        return 'Certificate "{0}" already exists'.format(cert_filename)

    try:
        maybe_fix_ssl_version(ca_name,
                              cacert_path=cacert_path,
                              ca_filename=ca_filename)
        with salt.utils.fopen('{0}/{1}/{2}.crt'.format(cert_base_path(),
                                                       ca_name,
                                                       ca_filename)) as fhr:
            ca_cert = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM, fhr.read()
            )
        with salt.utils.fopen('{0}/{1}/{2}.key'.format(cert_base_path(),
                                                       ca_name,
                                                       ca_filename)) as fhr:
            ca_key = OpenSSL.crypto.load_privatekey(
                OpenSSL.crypto.FILETYPE_PEM,
                fhr.read()
            )
    except IOError:
        ret['retcode'] = 1
        ret['comment'] = 'There is no CA named "{0}"'.format(ca_name)
        return ret

    try:
        csr_path = '{0}/{1}.csr'.format(cert_path, csr_filename)
        with salt.utils.fopen(csr_path) as fhr:
            req = OpenSSL.crypto.load_certificate_request(
                OpenSSL.crypto.FILETYPE_PEM,
                fhr.read())
    except IOError:
        ret['retcode'] = 1
        ret['comment'] = 'There is no CSR that matches the CN "{0}"'.format(
            cert_filename)
        return ret

    exts = []
    try:
        exts.extend(req.get_extensions())
    except AttributeError:
        try:
            # see: http://bazaar.launchpad.net/~exarkun/pyopenssl/master/revision/189
            # support is there from quite a long time, but without API
            # so we mimic the newly get_extensions method present in ultra
            # recent pyopenssl distros
            log.info('req.get_extensions() not supported in pyOpenSSL versions '
                     'prior to 0.15. Processing extensions internally. '
                     ' Your version: {0}'.format(
                         OpenSSL_version))

            native_exts_obj = OpenSSL._util.lib.X509_REQ_get_extensions(
                req._req)
            for i in _range(OpenSSL._util.lib.sk_X509_EXTENSION_num(
                    native_exts_obj)):
                ext = OpenSSL.crypto.X509Extension.__new__(
                    OpenSSL.crypto.X509Extension)
                ext._extension = OpenSSL._util.lib.sk_X509_EXTENSION_value(
                    native_exts_obj,
                    i)
                exts.append(ext)
        except Exception:
            log.error('X509 extensions are unsupported in pyOpenSSL '
                      'versions prior to 0.14. Upgrade required to '
                      'use extensions. Current version: {0}'.format(
                          OpenSSL_version))

    cert = OpenSSL.crypto.X509()
    cert.set_version(2)
    cert.set_subject(req.get_subject())
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(int(days) * 24 * 60 * 60)
    cert.set_serial_number(_new_serial(ca_name))
    cert.set_issuer(ca_cert.get_subject())
    cert.set_pubkey(req.get_pubkey())

    cert.add_extensions(exts)

    cert.sign(ca_key, digest)

    cert_full_path = '{0}/{1}.crt'.format(cert_path, cert_filename)

    with salt.utils.fopen(cert_full_path, 'w+') as crt:
        crt.write(
            OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, cert))

    _write_cert_to_database(ca_name, cert)

    return ('Created Certificate for "{0}": '
            '"{1}/{2}.crt"').format(
        CN,
        cert_path,
        cert_filename
    )


def create_pkcs12(ca_name, CN, passphrase='', cacert_path=None, replace=False):
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
    replace
        Replace this certificate even if it exists

        .. versionadded:: 2015.5.1

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
    if not replace and os.path.exists(
            '{0}/{1}/certs/{2}.p12'.format(
                cert_base_path(),
                ca_name,
                CN)
    ):
        return 'Certificate "{0}" already exists'.format(CN)

    try:
        with salt.utils.fopen('{0}/{1}/{2}_ca_cert.crt'.format(cert_base_path(),
                                                               ca_name,
                                                               ca_name)) as fhr:
            ca_cert = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM,
                fhr.read()
            )
    except IOError:
        return 'There is no CA named "{0}"'.format(ca_name)

    try:
        with salt.utils.fopen('{0}/{1}/certs/{2}.crt'.format(cert_base_path(),
                                                             ca_name,
                                                             CN)) as fhr:
            cert = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM,
                fhr.read()
            )
        with salt.utils.fopen('{0}/{1}/certs/{2}.key'.format(cert_base_path(),
                                                             ca_name,
                                                             CN)) as fhr:
            key = OpenSSL.crypto.load_privatekey(
                OpenSSL.crypto.FILETYPE_PEM,
                fhr.read()
            )
    except IOError:
        return 'There is no certificate that matches the CN "{0}"'.format(CN)

    pkcs12 = OpenSSL.crypto.PKCS12()

    pkcs12.set_certificate(cert)
    pkcs12.set_ca_certificates([ca_cert])
    pkcs12.set_privatekey(key)

    with salt.utils.fopen('{0}/{1}/certs/{2}.p12'.format(cert_base_path(),
                                                         ca_name,
                                                         CN), 'w') as ofile:
        ofile.write(pkcs12.export(passphrase=passphrase))

    return ('Created PKCS#12 Certificate for "{0}": '
            '"{1}/{2}/certs/{3}.p12"').format(
        CN,
        cert_base_path(),
        ca_name,
        CN
    )


def cert_info(cert_path, digest='sha256'):
    '''
    Return information for a particular certificate

    cert_path
        path to the cert file
    digest
        what digest to use for fingerprinting

    CLI Example:

    .. code-block:: bash

        salt '*' tls.cert_info /dir/for/certs/cert.pem
    '''
    # format that OpenSSL returns dates in
    date_fmt = '%Y%m%d%H%M%SZ'

    with salt.utils.fopen(cert_path) as cert_file:
        cert = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            cert_file.read()
        )
    ret = {
        'fingerprint': cert.digest(digest),
        'subject': dict(cert.get_subject().get_components()),
        'issuer': dict(cert.get_issuer().get_components()),
        'serial_number': cert.get_serial_number(),
        'not_before': calendar.timegm(time.strptime(
            cert.get_notBefore(),
            date_fmt)),
        'not_after': calendar.timegm(time.strptime(
            cert.get_notAfter(),
            date_fmt)),
    }

    # add additional info if your version of pyOpenSSL supports it
    if hasattr(cert, 'get_extension_count'):
        ret['extensions'] = {}
        for i in _range(cert.get_extension_count()):
            ext = cert.get_extension(i)
            ret['extensions'][ext.get_short_name()] = ext

    if 'subjectAltName' in ret.get('extensions', {}):
        valid_names = set()
        for name in str(ret['extensions']['subjectAltName']).split(", "):
            if not name.startswith('DNS:'):
                log.error('Cert {0} has an entry ({1}) which does not start '
                          'with DNS:'.format(cert_path, name))
            else:
                valid_names.add(name[4:])
        ret['subject_alt_names'] = ' '.join(valid_names)

    if hasattr(cert, 'get_signature_algorithm'):
        ret['signature_algorithm'] = cert.get_signature_algorithm()

    return ret


def create_empty_crl(
        ca_name,
        cacert_path=None,
        ca_filename=None,
        crl_file=None):
    '''
    Create an empty Certificate Revocation List.

    .. versionadded:: 2015.8.0

    ca_name
        name of the CA
    cacert_path
        absolute path to ca certificates root directory
    ca_filename
        alternative filename for the CA

        .. versionadded:: 2015.5.3

    crl_file
        full path to the CRL file

    CLI Example:

    .. code-block:: bash

        salt '*' tls.create_empty_crl ca_name='koji' \
                ca_filename='ca' \
                crl_file='/etc/openvpn/team1/crl.pem'
    '''

    set_ca_path(cacert_path)

    if not ca_filename:
        ca_filename = '{0}_ca_cert'.format(ca_name)

    if not crl_file:
        crl_file = '{0}/{1}/crl.pem'.format(
            _cert_base_path(),
            ca_name
        )

    if os.path.exists('{0}'.format(crl_file)):
        return 'CRL "{0}" already exists'.format(crl_file)

    try:
        ca_cert = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            salt.utils.fopen('{0}/{1}/{2}.crt'.format(
                cert_base_path(),
                ca_name,
                ca_filename
            )).read()
        )
        ca_key = OpenSSL.crypto.load_privatekey(
            OpenSSL.crypto.FILETYPE_PEM,
            salt.utils.fopen('{0}/{1}/{2}.key'.format(
                cert_base_path(),
                ca_name,
                ca_filename)).read()
        )
    except IOError:
        return 'There is no CA named "{0}"'.format(ca_name)

    crl = OpenSSL.crypto.CRL()
    crl_text = crl.export(ca_cert, ca_key)

    with salt.utils.fopen(crl_file, 'w') as f:
        f.write(crl_text)

    return 'Created an empty CRL: "{0}"'.format(crl_file)


def revoke_cert(
        ca_name,
        CN,
        cacert_path=None,
        ca_filename=None,
        cert_path=None,
        cert_filename=None,
        crl_file=None):
    '''
    Revoke a certificate.

    .. versionadded:: 2015.8.0

    ca_name
        Name of the CA.

    CN
        Common name matching the certificate signing request.

    cacert_path
        Absolute path to ca certificates root directory.

    ca_filename
        Alternative filename for the CA.

    cert_path
        Path to the cert file.

    cert_filename
        Alternative filename for the certificate, useful when using special
        characters in the CN.

    crl_file
        Full path to the CRL file.

    CLI Example:

    .. code-block:: bash

        salt '*' tls.revoke_cert ca_name='koji' \
                ca_filename='ca' \
                crl_file='/etc/openvpn/team1/crl.pem'

    '''

    set_ca_path(cacert_path)
    ca_dir = '{0}/{1}'.format(cert_base_path(), ca_name)

    if ca_filename is None:
        ca_filename = '{0}_ca_cert'.format(ca_name)

    if cert_path is None:
        cert_path = '{0}/{1}/certs'.format(_cert_base_path(), ca_name)

    if cert_filename is None:
        cert_filename = '{0}'.format(CN)

    try:
        ca_cert = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            salt.utils.fopen('{0}/{1}/{2}.crt'.format(
                cert_base_path(),
                ca_name,
                ca_filename
            )).read()
        )
        ca_key = OpenSSL.crypto.load_privatekey(
            OpenSSL.crypto.FILETYPE_PEM,
            salt.utils.fopen('{0}/{1}/{2}.key'.format(
                cert_base_path(),
                ca_name,
                ca_filename)).read()
        )
    except IOError:
        return 'There is no CA named "{0}"'.format(ca_name)

    try:
        client_cert = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM,
            salt.utils.fopen('{0}/{1}.crt'.format(
                cert_path,
                cert_filename)).read()
        )
    except IOError:
        return 'There is no client certificate named "{0}"'.format(CN)

    index_file, expire_date, serial_number, subject = _get_basic_info(
        ca_name,
        client_cert,
        ca_dir)

    index_serial_subject = '{0}\tunknown\t{1}'.format(
        serial_number,
        subject)
    index_v_data = 'V\t{0}\t\t{1}'.format(
        expire_date,
        index_serial_subject)
    index_r_data_pattern = re.compile(
        r"R\t" +
        expire_date +
        r"\t\d{12}Z\t" +
        re.escape(index_serial_subject))
    index_r_data = 'R\t{0}\t{1}\t{2}'.format(
        expire_date,
        _four_digit_year_to_two_digit(datetime.utcnow()),
        index_serial_subject)

    ret = {}
    with salt.utils.fopen(index_file) as f:
        for line in f:
            if index_r_data_pattern.match(line):
                revoke_date = line.split('\t')[2]
                try:
                    datetime.strptime(revoke_date, two_digit_year_fmt)
                    return ('"{0}/{1}.crt" was already revoked, '
                            'serial number: {2}').format(
                        cert_path,
                        cert_filename,
                        serial_number
                    )
                except ValueError:
                    ret['retcode'] = 1
                    ret['comment'] = ("Revocation date '{0}' does not match"
                                      "format '{1}'".format(
                                          revoke_date,
                                          two_digit_year_fmt))
                    return ret
            elif index_serial_subject in line:
                __salt__['file.replace'](
                    index_file,
                    index_v_data,
                    index_r_data,
                    backup=False)
                break

    crl = OpenSSL.crypto.CRL()

    with salt.utils.fopen(index_file) as f:
        for line in f:
            if line.startswith('R'):
                fields = line.split('\t')
                revoked = OpenSSL.crypto.Revoked()
                revoked.set_serial(fields[3])
                revoke_date_2_digit = datetime.strptime(fields[2],
                                                        two_digit_year_fmt)
                revoked.set_rev_date(revoke_date_2_digit.strftime(
                    four_digit_year_fmt))
                crl.add_revoked(revoked)

    crl_text = crl.export(ca_cert, ca_key)

    if crl_file is None:
        crl_file = '{0}/{1}/crl.pem'.format(
            _cert_base_path(),
            ca_name
        )

    if os.path.isdir(crl_file):
        ret['retcode'] = 1
        ret['comment'] = 'crl_file "{0}" is an existing directory'.format(
            crl_file)
        return ret

    with salt.utils.fopen(crl_file, 'w') as f:
        f.write(crl_text)

    return ('Revoked Certificate: "{0}/{1}.crt", '
            'serial number: {2}').format(
        cert_path,
        cert_filename,
        serial_number
    )


if __name__ == '__main__':
    # create_ca('koji', days=365, **cert_sample_meta)
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
