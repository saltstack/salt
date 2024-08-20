r"""
A salt module for SSL/TLS.  Can create a Certificate Authority (CA)
or use Self-Signed certificates.

:depends: PyOpenSSL Python module (0.10 or later, 0.14 or later for X509
    extension support)

:configuration: Add the following values in /etc/salt/minion for the CA module
    to function properly:

    .. code-block:: yaml

        ca.cert_base_path: '/etc/pki'


CLI Example #1:
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
    Created Private Key: "/etc/pki/my_little/certs//DBReplica_No.1.key"
    Created CSR for "DBReplica_No.1": "/etc/pki/my_little/certs/DBReplica_No.1.csr"

    # salt-call tls.create_ca_signed_cert my_little CN=DBReplica_No.1
    Created Certificate for "DBReplica_No.1": "/etc/pki/my_little/certs/DBReplica_No.1.crt"

CLI Example #3:
Creating both a server and client req + cert for the same CN

.. code-block:: bash

    # salt-call tls.create_csr my_little CN=MasterDBReplica_No.2  \
        cert_type=client
    Created Private Key: "/etc/pki/my_little/certs/MasterDBReplica_No.2.key"
    Created CSR for "DBReplica_No.1": "/etc/pki/my_little/certs/MasterDBReplica_No.2.csr"

    # salt-call tls.create_ca_signed_cert my_little CN=MasterDBReplica_No.2
    Created Certificate for "DBReplica_No.1": "/etc/pki/my_little/certs/DBReplica_No.1.crt"

    # salt-call tls.create_csr my_little CN=MasterDBReplica_No.2 \
        cert_type=server
    Certificate "MasterDBReplica_No.2" already exists

    (doh!)

    # salt-call tls.create_csr my_little CN=MasterDBReplica_No.2 \
        cert_type=server type_ext=True
    Created Private Key: "/etc/pki/my_little/certs/DBReplica_No.1_client.key"
    Created CSR for "DBReplica_No.1": "/etc/pki/my_little/certs/DBReplica_No.1_client.csr"

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
    Created Private Key: "/etc/pki/my_little/certs/www.anothersometh.ing_server.key"
    Created CSR for "DBReplica_No.1": "/etc/pki/my_little/certs/www.anothersometh.ing_server.csr"

    # salt-call tls_create_ca_signed_cert my_little CN=www.anothersometh.ing \
        cert_type=server cert_filename="something_completely_different"
    Created Certificate for "www.anothersometh.ing": /etc/pki/my_little/certs/something_completely_different.crt
"""

import binascii
import calendar
import logging
import math
import os
import re
import time
from datetime import datetime

import salt.utils.data
import salt.utils.files
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError
from salt.utils.versions import Version

# pylint: disable=C0103


HAS_SSL = False
X509_EXT_ENABLED = True
try:
    import OpenSSL

    HAS_SSL = True
    OpenSSL_version = Version(OpenSSL.__dict__.get("__version__", "0.0"))
except ImportError:
    pass


log = logging.getLogger(__name__)

two_digit_year_fmt = "%y%m%d%H%M%SZ"
four_digit_year_fmt = "%Y%m%d%H%M%SZ"


def __virtual__():
    """
    Only load this module if the ca config options are set
    """
    global X509_EXT_ENABLED
    if HAS_SSL and OpenSSL_version >= Version("0.10"):
        if OpenSSL_version < Version("0.14"):
            X509_EXT_ENABLED = False
            log.debug(
                "You should upgrade pyOpenSSL to at least 0.14.1 to "
                "enable the use of X509 extensions in the tls module"
            )
        elif OpenSSL_version <= Version("0.15"):
            log.debug(
                "You should upgrade pyOpenSSL to at least 0.15.1 to "
                "enable the full use of X509 extensions in the tls module"
            )
        # NOTE: Not having configured a cert path should not prevent this
        # module from loading as it provides methods to configure the path.
        return True
    else:
        X509_EXT_ENABLED = False
        return (
            False,
            "PyOpenSSL version 0.10 or later must be installed "
            "before this module can be used.",
        )


def _microtime():
    """
    Return a Unix timestamp as a string of digits
    :return:
    """
    val1, val2 = math.modf(time.time())
    val2 = int(val2)
    return f"{val1:f}{val2}"


def _context_or_config(key):
    """
    Return the value corresponding to the key in __context__ or if not present,
    fallback to config.option.
    """
    return __context__.get(key, __salt__["config.option"](key))


def cert_base_path(cacert_path=None):
    """
    Return the base path for certs from CLI or from options

    cacert_path
        absolute path to ca certificates root directory

    CLI Example:

    .. code-block:: bash

        salt '*' tls.cert_base_path
    """
    return (
        cacert_path
        or _context_or_config("ca.contextual_cert_base_path")
        or _context_or_config("ca.cert_base_path")
    )


def _cert_base_path(cacert_path=None):
    """
    Retrocompatible wrapper
    """
    return cert_base_path(cacert_path)


def set_ca_path(cacert_path):
    """
    If wanted, store the aforementioned cacert_path in context
    to be used as the basepath for further operations

    CLI Example:

    .. code-block:: bash

        salt '*' tls.set_ca_path /etc/certs
    """
    if cacert_path:
        __context__["ca.contextual_cert_base_path"] = cacert_path
    return cert_base_path()


def _new_serial(ca_name):
    """
    Return a serial number in hex using os.urandom() and a Unix timestamp
    in microseconds.

    ca_name
        name of the CA
    CN
        common name in the request
    """
    hashnum = int(
        binascii.hexlify(
            b"_".join(
                (
                    salt.utils.stringutils.to_bytes(_microtime()),
                    os.urandom(5),
                )
            )
        ),
        16,
    )
    log.debug("Hashnum: %s", hashnum)

    # record the hash somewhere
    cachedir = __opts__["cachedir"]
    log.debug("cachedir: %s", cachedir)
    serial_file = f"{cachedir}/{ca_name}.serial"
    if not os.path.exists(cachedir):
        os.makedirs(cachedir)
    if not os.path.exists(serial_file):
        mode = "w"
    else:
        mode = "a+"
    with salt.utils.files.fopen(serial_file, mode) as ofile:
        ofile.write(str(hashnum))

    return hashnum


def _four_digit_year_to_two_digit(datetimeObj):
    return datetimeObj.strftime(two_digit_year_fmt)


def _get_basic_info(ca_name, cert, ca_dir=None):
    """
    Get basic info to write out to the index.txt
    """
    if ca_dir is None:
        ca_dir = f"{_cert_base_path()}/{ca_name}"

    index_file = f"{ca_dir}/index.txt"

    cert = _read_cert(cert)
    expire_date = _four_digit_year_to_two_digit(_get_expiration_date(cert))
    serial_number = format(cert.get_serial_number(), "X")

    # gotta prepend a /
    subject = "/"

    # then we can add the rest of the subject
    subject += "/".join([f"{x}={y}" for x, y in cert.get_subject().get_components()])
    subject += "\n"

    return (index_file, expire_date, serial_number, subject)


def _write_cert_to_database(ca_name, cert, cacert_path=None, status="V"):
    """
    write out the index.txt database file in the appropriate directory to
    track certificates

    ca_name
        name of the CA
    cert
        certificate to be recorded
    """
    set_ca_path(cacert_path)
    ca_dir = f"{cert_base_path()}/{ca_name}"
    index_file, expire_date, serial_number, subject = _get_basic_info(
        ca_name, cert, ca_dir
    )

    index_data = "{}\t{}\t\t{}\tunknown\t{}".format(
        status, expire_date, serial_number, subject
    )

    with salt.utils.files.fopen(index_file, "a+") as ofile:
        ofile.write(salt.utils.stringutils.to_str(index_data))


def maybe_fix_ssl_version(ca_name, cacert_path=None, ca_filename=None):
    """
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
    """
    set_ca_path(cacert_path)
    if not ca_filename:
        ca_filename = f"{ca_name}_ca_cert"
    certp = f"{cert_base_path()}/{ca_name}/{ca_filename}.crt"
    ca_keyp = f"{cert_base_path()}/{ca_name}/{ca_filename}.key"
    with salt.utils.files.fopen(certp) as fic:
        cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, fic.read())
        if cert.get_version() == 3:
            log.info("Regenerating wrong x509 version for certificate %s", certp)
            with salt.utils.files.fopen(ca_keyp) as fic2:
                try:
                    # try to determine the key bits
                    key = OpenSSL.crypto.load_privatekey(
                        OpenSSL.crypto.FILETYPE_PEM, fic2.read()
                    )
                    bits = key.bits()
                except Exception:  # pylint: disable=broad-except
                    bits = 2048
                try:
                    days = (
                        datetime.strptime(cert.get_notAfter(), "%Y%m%d%H%M%SZ")
                        - datetime.utcnow()
                    ).days
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
                    fixmode=True,
                )


def ca_exists(ca_name, cacert_path=None, ca_filename=None):
    """
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
    """
    set_ca_path(cacert_path)
    if not ca_filename:
        ca_filename = f"{ca_name}_ca_cert"
    certp = f"{cert_base_path()}/{ca_name}/{ca_filename}.crt"
    if os.path.exists(certp):
        maybe_fix_ssl_version(ca_name, cacert_path=cacert_path, ca_filename=ca_filename)
        return True
    return False


def _ca_exists(ca_name, cacert_path=None):
    """Retrocompatible wrapper"""
    return ca_exists(ca_name, cacert_path)


def get_ca(ca_name, as_text=False, cacert_path=None):
    """
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
    """
    set_ca_path(cacert_path)
    certp = "{0}/{1}/{1}_ca_cert.crt".format(cert_base_path(), ca_name)
    if not os.path.exists(certp):
        raise ValueError(f"Certificate does not exist for {ca_name}")
    else:
        if as_text:
            with salt.utils.files.fopen(certp) as fic:
                certp = salt.utils.stringutils.to_unicode(fic.read())
    return certp


def get_ca_signed_cert(
    ca_name, CN="localhost", as_text=False, cacert_path=None, cert_filename=None
):
    """
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
    """
    set_ca_path(cacert_path)
    if not cert_filename:
        cert_filename = CN

    certp = f"{cert_base_path()}/{ca_name}/certs/{cert_filename}.crt"
    if not os.path.exists(certp):
        raise ValueError(f"Certificate does not exists for {CN}")
    else:
        if as_text:
            with salt.utils.files.fopen(certp) as fic:
                certp = salt.utils.stringutils.to_unicode(fic.read())
    return certp


def get_ca_signed_key(
    ca_name, CN="localhost", as_text=False, cacert_path=None, key_filename=None
):
    """
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
    """
    set_ca_path(cacert_path)
    if not key_filename:
        key_filename = CN

    keyp = f"{cert_base_path()}/{ca_name}/certs/{key_filename}.key"
    if not os.path.exists(keyp):
        raise ValueError(f"Certificate does not exists for {CN}")
    else:
        if as_text:
            with salt.utils.files.fopen(keyp) as fic:
                keyp = salt.utils.stringutils.to_unicode(fic.read())
    return keyp


def _read_cert(cert):
    if isinstance(cert, str):
        try:
            with salt.utils.files.fopen(cert) as rfh:
                return OpenSSL.crypto.load_certificate(
                    OpenSSL.crypto.FILETYPE_PEM, rfh.read()
                )
        except Exception:  # pylint: disable=broad-except
            log.exception("Failed to read cert from path %s", cert)
            return None
    else:
        if not hasattr(cert, "get_notAfter"):
            log.error("%s is not a valid cert path/object", cert)
            return None
        else:
            return cert


def validate(cert, ca_name, crl_file):
    """
    .. versionadded:: 3000

    Validate a certificate against a given CA/CRL.

    cert
        path to the certifiate PEM file or string

    ca_name
        name of the CA

    crl_file
        full path to the CRL file
    """
    store = OpenSSL.crypto.X509Store()
    cert_obj = _read_cert(cert)
    if cert_obj is None:
        raise CommandExecutionError(
            f"Failed to read cert from {cert}, see log for details"
        )
    ca_dir = f"{cert_base_path()}/{ca_name}"
    ca_cert = _read_cert(f"{ca_dir}/{ca_name}_ca_cert.crt")
    store.add_cert(ca_cert)
    # These flags tell OpenSSL to check the leaf as well as the
    # entire cert chain.
    X509StoreFlags = OpenSSL.crypto.X509StoreFlags
    store.set_flags(X509StoreFlags.CRL_CHECK | X509StoreFlags.CRL_CHECK_ALL)
    if crl_file is None:
        crl = OpenSSL.crypto.CRL()
    else:
        with salt.utils.files.fopen(crl_file) as fhr:
            crl = OpenSSL.crypto.load_crl(OpenSSL.crypto.FILETYPE_PEM, fhr.read())
    store.add_crl(crl)
    context = OpenSSL.crypto.X509StoreContext(store, cert_obj)
    ret = {}
    try:
        context.verify_certificate()
        ret["valid"] = True
    except OpenSSL.crypto.X509StoreContextError as e:
        ret["error"] = str(e)
        ret["error_cert"] = e.certificate
        ret["valid"] = False
    return ret


def _get_expiration_date(cert):
    """
    Returns a datetime.datetime object
    """
    cert_obj = _read_cert(cert)

    if cert_obj is None:
        raise CommandExecutionError(
            f"Failed to read cert from {cert}, see log for details"
        )

    return datetime.strptime(
        salt.utils.stringutils.to_str(cert_obj.get_notAfter()), four_digit_year_fmt
    )


def get_expiration_date(cert, date_format="%Y-%m-%d"):
    """
    .. versionadded:: 2019.2.0

    Get a certificate's expiration date

    cert
        Full path to the certificate

    date_format
        By default this will return the expiration date in YYYY-MM-DD format,
        use this to specify a different strftime format string. Note that the
        expiration time will be in UTC.

    CLI Examples:

    .. code-block:: bash

        salt '*' tls.get_expiration_date /path/to/foo.crt
        salt '*' tls.get_expiration_date /path/to/foo.crt date_format='%d/%m/%Y'
    """
    return _get_expiration_date(cert).strftime(date_format)


def _check_onlyif_unless(onlyif, unless):
    ret = None
    retcode = __salt__["cmd.retcode"]
    if onlyif is not None:
        if not isinstance(onlyif, str):
            if not onlyif:
                ret = {"comment": "onlyif condition is false", "result": True}
        elif isinstance(onlyif, str):
            if retcode(onlyif) != 0:
                ret = {"comment": "onlyif condition is false", "result": True}
                log.debug("onlyif condition is false")
    if unless is not None:
        if not isinstance(unless, str):
            if unless:
                ret = {"comment": "unless condition is true", "result": True}
        elif isinstance(unless, str):
            if retcode(unless) == 0:
                ret = {"comment": "unless condition is true", "result": True}
                log.debug("unless condition is true")
    return ret


def create_ca(
    ca_name,
    bits=2048,
    days=365,
    CN="localhost",
    C="US",
    ST="Utah",
    L="Salt Lake City",
    O="SaltStack",
    OU=None,
    emailAddress=None,
    fixmode=False,
    cacert_path=None,
    ca_filename=None,
    digest="sha256",
    onlyif=None,
    unless=None,
    replace=False,
):
    """
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
        email address for the CA owner, default is None
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
    location with appropriate permissions::

        /etc/pki/koji/koji_ca_cert.crt
        /etc/pki/koji/koji_ca_cert.key

    CLI Example:

    .. code-block:: bash

        salt '*' tls.create_ca test_ca
    """
    status = _check_onlyif_unless(onlyif, unless)
    if status is not None:
        return None

    set_ca_path(cacert_path)

    if not ca_filename:
        ca_filename = f"{ca_name}_ca_cert"

    certp = f"{cert_base_path()}/{ca_name}/{ca_filename}.crt"
    ca_keyp = f"{cert_base_path()}/{ca_name}/{ca_filename}.key"
    if not replace and not fixmode and ca_exists(ca_name, ca_filename=ca_filename):
        return f'Certificate for CA named "{ca_name}" already exists'

    if fixmode and not os.path.exists(certp):
        raise ValueError(f"{certp} does not exists, can't fix")

    if not os.path.exists(f"{cert_base_path()}/{ca_name}"):
        os.makedirs(f"{cert_base_path()}/{ca_name}")

    # try to reuse existing ssl key
    key = None
    if os.path.exists(ca_keyp):
        with salt.utils.files.fopen(ca_keyp) as fic2:
            # try to determine the key bits
            try:
                key = OpenSSL.crypto.load_privatekey(
                    OpenSSL.crypto.FILETYPE_PEM, fic2.read()
                )
            except OpenSSL.crypto.Error as err:
                log.warning(
                    "Error loading existing private key %s, generating a new key: %s",
                    ca_keyp,
                    err,
                )
                bck = "{}.unloadable.{}".format(
                    ca_keyp, datetime.utcnow().strftime("%Y%m%d%H%M%S")
                )
                log.info("Saving unloadable CA ssl key in %s", bck)
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
    if emailAddress:
        ca.get_subject().emailAddress = emailAddress

    ca.gmtime_adj_notBefore(0)
    ca.gmtime_adj_notAfter(int(days) * 24 * 60 * 60)
    ca.set_issuer(ca.get_subject())
    ca.set_pubkey(key)

    if X509_EXT_ENABLED:
        ca.add_extensions(
            [
                OpenSSL.crypto.X509Extension(
                    b"basicConstraints", True, b"CA:TRUE, pathlen:0"
                ),
                OpenSSL.crypto.X509Extension(
                    b"keyUsage", True, b"keyCertSign, cRLSign"
                ),
                OpenSSL.crypto.X509Extension(
                    b"subjectKeyIdentifier", False, b"hash", subject=ca
                ),
            ]
        )

        ca.add_extensions(
            [
                OpenSSL.crypto.X509Extension(
                    b"authorityKeyIdentifier",
                    False,
                    b"issuer:always,keyid:always",
                    issuer=ca,
                )
            ]
        )
    ca.sign(key, salt.utils.stringutils.to_str(digest))

    # always backup existing keys in case
    keycontent = OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key)
    write_key = True
    if os.path.exists(ca_keyp):
        bck = "{}.{}".format(ca_keyp, datetime.utcnow().strftime("%Y%m%d%H%M%S"))
        with salt.utils.files.fopen(ca_keyp) as fic:
            old_key = salt.utils.stringutils.to_unicode(fic.read()).strip()
            if old_key.strip() == keycontent.strip():
                write_key = False
            else:
                log.info("Saving old CA ssl key in %s", bck)
                fp = os.open(bck, os.O_CREAT | os.O_RDWR, 0o600)
                with salt.utils.files.fopen(fp, "w") as bckf:
                    bckf.write(old_key)
    if write_key:
        fp = os.open(ca_keyp, os.O_CREAT | os.O_RDWR, 0o600)
        with salt.utils.files.fopen(fp, "wb") as ca_key:
            ca_key.write(salt.utils.stringutils.to_bytes(keycontent))

    with salt.utils.files.fopen(certp, "wb") as ca_crt:
        ca_crt.write(
            salt.utils.stringutils.to_bytes(
                OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, ca)
            )
        )

    _write_cert_to_database(ca_name, ca)

    ret = 'Created Private Key: "{}/{}/{}.key" '.format(
        cert_base_path(), ca_name, ca_filename
    )
    ret += 'Created CA "{0}": "{1}/{0}/{2}.crt"'.format(
        ca_name, cert_base_path(), ca_filename
    )

    return ret


def get_extensions(cert_type):
    """
    Fetch X509 and CSR extension definitions from tls:extensions:
    (common|server|client) or set them to standard defaults.

    .. versionadded:: 2015.8.0

    cert_type:
        The type of certificate such as ``server`` or ``client``.

    CLI Example:

    .. code-block:: bash

        salt '*' tls.get_extensions client

    """

    assert X509_EXT_ENABLED, (
        "X509 extensions are not supported in "
        "pyOpenSSL prior to version 0.15.1. Your "
        "version: {}".format(OpenSSL_version)
    )

    ext = {}
    if cert_type == "":
        log.error(
            "cert_type set to empty in tls_ca.get_extensions(); "
            "defaulting to ``server``"
        )
        cert_type = "server"

    try:
        ext["common"] = __salt__["pillar.get"]("tls.extensions:common", False)
    except NameError as err:
        log.debug(err)

    if not ext["common"] or ext["common"] == "":
        ext["common"] = {
            "csr": {"basicConstraints": "CA:FALSE"},
            "cert": {
                "authorityKeyIdentifier": "keyid,issuer:always",
                "subjectKeyIdentifier": "hash",
            },
        }

    try:
        ext["server"] = __salt__["pillar.get"]("tls.extensions:server", False)
    except NameError as err:
        log.debug(err)

    if not ext["server"] or ext["server"] == "":
        ext["server"] = {
            "csr": {
                "extendedKeyUsage": "serverAuth",
                "keyUsage": "digitalSignature, keyEncipherment",
            },
            "cert": {},
        }

    try:
        ext["client"] = __salt__["pillar.get"]("tls.extensions:client", False)
    except NameError as err:
        log.debug(err)

    if not ext["client"] or ext["client"] == "":
        ext["client"] = {
            "csr": {
                "extendedKeyUsage": "clientAuth",
                "keyUsage": "nonRepudiation, digitalSignature, keyEncipherment",
            },
            "cert": {},
        }

    # possible user-defined profile or a typo
    if cert_type not in ext:
        try:
            ext[cert_type] = __salt__["pillar.get"](f"tls.extensions:{cert_type}")
        except NameError as e:
            log.debug(
                "pillar, tls:extensions:%s not available or "
                "not operating in a salt context\n%s",
                cert_type,
                e,
            )

    retval = ext["common"]

    for Use in retval:
        retval[Use].update(ext[cert_type][Use])

    return retval


def create_csr(
    ca_name,
    bits=2048,
    CN="localhost",
    C="US",
    ST="Utah",
    L="Salt Lake City",
    O="SaltStack",
    OU=None,
    emailAddress=None,
    subjectAltName=None,
    cacert_path=None,
    ca_filename=None,
    csr_path=None,
    csr_filename=None,
    digest="sha256",
    type_ext=False,
    cert_type="server",
    replace=False,
):
    """
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
        email address for the request, default is None
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
    following location with appropriate permissions::

        /etc/pki/koji/certs/test.egavas.org.csr
        /etc/pki/koji/certs/test.egavas.org.key

    CLI Example:

    .. code-block:: bash

        salt '*' tls.create_csr test
    """
    set_ca_path(cacert_path)

    if not ca_filename:
        ca_filename = f"{ca_name}_ca_cert"

    if not ca_exists(ca_name, ca_filename=ca_filename):
        return 'Certificate for CA named "{}" does not exist, please create it first.'.format(
            ca_name
        )

    if not csr_path:
        csr_path = f"{cert_base_path()}/{ca_name}/certs/"

    if not os.path.exists(csr_path):
        os.makedirs(csr_path)

    CN_ext = f"_{cert_type}" if type_ext else ""

    if not csr_filename:
        csr_filename = f"{CN}{CN_ext}"

    csr_f = f"{csr_path}/{csr_filename}.csr"

    if not replace and os.path.exists(csr_f):
        return f'Certificate Request "{csr_f}" already exists'

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
    if emailAddress:
        req.get_subject().emailAddress = emailAddress

    try:
        extensions = get_extensions(cert_type)["csr"]

        extension_adds = []

        for ext, value in extensions.items():
            if isinstance(value, str):
                value = salt.utils.stringutils.to_bytes(value)
            extension_adds.append(
                OpenSSL.crypto.X509Extension(
                    salt.utils.stringutils.to_bytes(ext), False, value
                )
            )
    except AssertionError as err:
        log.error(err)
        extensions = []

    if subjectAltName:
        if X509_EXT_ENABLED:
            if isinstance(subjectAltName, str):
                subjectAltName = [subjectAltName]

            extension_adds.append(
                OpenSSL.crypto.X509Extension(
                    b"subjectAltName",
                    False,
                    b", ".join(salt.utils.data.encode(subjectAltName)),
                )
            )
        else:
            raise ValueError(
                "subjectAltName cannot be set as X509 "
                "extensions are not supported in pyOpenSSL "
                "prior to version 0.15.1. Your "
                "version: {}.".format(OpenSSL_version)
            )

    if X509_EXT_ENABLED:
        req.add_extensions(extension_adds)

    req.set_pubkey(key)
    req.sign(key, salt.utils.stringutils.to_str(digest))

    # Write private key and request
    priv_keyp = f"{csr_path}/{csr_filename}.key"
    fp = os.open(priv_keyp, os.O_CREAT | os.O_RDWR, 0o600)
    with salt.utils.files.fopen(fp, "wb+") as priv_key:
        priv_key.write(
            salt.utils.stringutils.to_bytes(
                OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key)
            )
        )

    with salt.utils.files.fopen(csr_f, "wb+") as csr:
        csr.write(
            salt.utils.stringutils.to_bytes(
                OpenSSL.crypto.dump_certificate_request(
                    OpenSSL.crypto.FILETYPE_PEM, req
                )
            )
        )

    ret = f'Created Private Key: "{csr_path}{csr_filename}.key" '
    ret += f'Created CSR for "{CN}": "{csr_path}{csr_filename}.csr"'

    return ret


def create_self_signed_cert(
    tls_dir="tls",
    bits=2048,
    days=365,
    CN="localhost",
    C="US",
    ST="Utah",
    L="Salt Lake City",
    O="SaltStack",
    OU=None,
    emailAddress=None,
    cacert_path=None,
    cert_filename=None,
    digest="sha256",
    replace=False,
):
    """
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
        email address for the request, default is None
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
    following location with appropriate permissions::

        /etc/pki/koji/certs/test.egavas.org.crt
        /etc/pki/koji/certs/test.egavas.org.key

    CLI Example:

    .. code-block:: bash

        salt '*' tls.create_self_signed_cert

    Passing options from the command line:

    .. code-block:: bash

        salt 'minion' tls.create_self_signed_cert CN='test.mysite.org'
    """
    set_ca_path(cacert_path)

    if not os.path.exists(f"{cert_base_path()}/{tls_dir}/certs/"):
        os.makedirs(f"{cert_base_path()}/{tls_dir}/certs/")

    if not cert_filename:
        cert_filename = CN

    if not replace and os.path.exists(
        f"{cert_base_path()}/{tls_dir}/certs/{cert_filename}.crt"
    ):
        return f'Certificate "{cert_filename}" already exists'

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
    if emailAddress:
        cert.get_subject().emailAddress = emailAddress

    cert.set_serial_number(_new_serial(tls_dir))
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, salt.utils.stringutils.to_str(digest))

    # Write private key and cert
    priv_key_path = "{}/{}/certs/{}.key".format(
        cert_base_path(), tls_dir, cert_filename
    )
    fp = os.open(priv_key_path, os.O_CREAT | os.O_RDWR, 0o600)
    with salt.utils.files.fopen(fp, "wb+") as priv_key:
        priv_key.write(
            salt.utils.stringutils.to_bytes(
                OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key)
            )
        )

    crt_path = f"{cert_base_path()}/{tls_dir}/certs/{cert_filename}.crt"
    with salt.utils.files.fopen(crt_path, "wb+") as crt:
        crt.write(
            salt.utils.stringutils.to_bytes(
                OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, cert)
            )
        )

    _write_cert_to_database(tls_dir, cert)

    ret = 'Created Private Key: "{}/{}/certs/{}.key" '.format(
        cert_base_path(), tls_dir, cert_filename
    )
    ret += 'Created Certificate: "{}/{}/certs/{}.crt"'.format(
        cert_base_path(), tls_dir, cert_filename
    )

    return ret


def create_ca_signed_cert(
    ca_name,
    CN,
    days=365,
    cacert_path=None,
    ca_filename=None,
    cert_path=None,
    cert_filename=None,
    digest="sha256",
    cert_type=None,
    type_ext=False,
    replace=False,
):
    """
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
    """
    ret = {}

    set_ca_path(cacert_path)

    if not ca_filename:
        ca_filename = f"{ca_name}_ca_cert"

    if not cert_path:
        cert_path = f"{cert_base_path()}/{ca_name}/certs"

    if type_ext:
        if not cert_type:
            log.error(
                "type_ext = True but cert_type is unset. Certificate not written."
            )
            return ret
        elif cert_type:
            CN_ext = f"_{cert_type}"
    else:
        CN_ext = ""

    csr_filename = f"{CN}{CN_ext}"

    if not cert_filename:
        cert_filename = f"{CN}{CN_ext}"

    if not replace and os.path.exists(
        os.path.join(
            os.path.sep.join(
                "{}/{}/certs/{}.crt".format(
                    cert_base_path(), ca_name, cert_filename
                ).split("/")
            )
        )
    ):
        return f'Certificate "{cert_filename}" already exists'

    try:
        maybe_fix_ssl_version(ca_name, cacert_path=cacert_path, ca_filename=ca_filename)
        with salt.utils.files.fopen(
            f"{cert_base_path()}/{ca_name}/{ca_filename}.crt"
        ) as fhr:
            ca_cert = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM, fhr.read()
            )
        with salt.utils.files.fopen(
            f"{cert_base_path()}/{ca_name}/{ca_filename}.key"
        ) as fhr:
            ca_key = OpenSSL.crypto.load_privatekey(
                OpenSSL.crypto.FILETYPE_PEM, fhr.read()
            )
    except OSError:
        ret["retcode"] = 1
        ret["comment"] = f'There is no CA named "{ca_name}"'
        return ret

    try:
        csr_path = f"{cert_path}/{csr_filename}.csr"
        with salt.utils.files.fopen(csr_path) as fhr:
            req = OpenSSL.crypto.load_certificate_request(
                OpenSSL.crypto.FILETYPE_PEM, fhr.read()
            )
    except OSError:
        ret["retcode"] = 1
        ret["comment"] = 'There is no CSR that matches the CN "{}"'.format(
            cert_filename
        )
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
            log.info(
                "req.get_extensions() not supported in pyOpenSSL versions "
                "prior to 0.15. Processing extensions internally. "
                "Your version: %s",
                OpenSSL_version,
            )

            native_exts_obj = OpenSSL._util.lib.X509_REQ_get_extensions(req._req)
            for i in range(OpenSSL._util.lib.sk_X509_EXTENSION_num(native_exts_obj)):
                ext = OpenSSL.crypto.X509Extension.__new__(OpenSSL.crypto.X509Extension)
                ext._extension = OpenSSL._util.lib.sk_X509_EXTENSION_value(
                    native_exts_obj, i
                )
                exts.append(ext)
        except Exception:  # pylint: disable=broad-except
            log.error(
                "X509 extensions are unsupported in pyOpenSSL "
                "versions prior to 0.14. Upgrade required to "
                "use extensions. Current version: %s",
                OpenSSL_version,
            )

    cert = OpenSSL.crypto.X509()
    cert.set_version(2)
    cert.set_subject(req.get_subject())
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(int(days) * 24 * 60 * 60)
    cert.set_serial_number(_new_serial(ca_name))
    cert.set_issuer(ca_cert.get_subject())
    cert.set_pubkey(req.get_pubkey())

    cert.add_extensions(exts)

    cert.sign(ca_key, salt.utils.stringutils.to_str(digest))

    cert_full_path = f"{cert_path}/{cert_filename}.crt"

    with salt.utils.files.fopen(cert_full_path, "wb+") as crt:
        crt.write(
            salt.utils.stringutils.to_bytes(
                OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, cert)
            )
        )

    _write_cert_to_database(ca_name, cert)

    return 'Created Certificate for "{}": "{}/{}.crt"'.format(
        CN, cert_path, cert_filename
    )


def create_pkcs12(ca_name, CN, passphrase="", cacert_path=None, replace=False):
    """
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
    """
    set_ca_path(cacert_path)
    if not replace and os.path.exists(f"{cert_base_path()}/{ca_name}/certs/{CN}.p12"):
        return f'Certificate "{CN}" already exists'

    try:
        with salt.utils.files.fopen(
            "{0}/{1}/{1}_ca_cert.crt".format(cert_base_path(), ca_name)
        ) as fhr:
            ca_cert = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM, fhr.read()
            )
    except OSError:
        return f'There is no CA named "{ca_name}"'

    try:
        with salt.utils.files.fopen(
            f"{cert_base_path()}/{ca_name}/certs/{CN}.crt"
        ) as fhr:
            cert = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM, fhr.read()
            )
        with salt.utils.files.fopen(
            f"{cert_base_path()}/{ca_name}/certs/{CN}.key"
        ) as fhr:
            key = OpenSSL.crypto.load_privatekey(
                OpenSSL.crypto.FILETYPE_PEM, fhr.read()
            )
    except OSError:
        return f'There is no certificate that matches the CN "{CN}"'

    pkcs12 = OpenSSL.crypto.PKCS12()

    pkcs12.set_certificate(cert)
    pkcs12.set_ca_certificates([ca_cert])
    pkcs12.set_privatekey(key)

    with salt.utils.files.fopen(
        f"{cert_base_path()}/{ca_name}/certs/{CN}.p12", "wb"
    ) as ofile:
        ofile.write(
            pkcs12.export(passphrase=salt.utils.stringutils.to_bytes(passphrase))
        )

    return 'Created PKCS#12 Certificate for "{0}": "{1}/{2}/certs/{0}.p12"'.format(
        CN,
        cert_base_path(),
        ca_name,
    )


def cert_info(cert, digest="sha256"):
    """
    Return information for a particular certificate

    cert
        path to the certifiate PEM file or string

        .. versionchanged:: 2018.3.4

    digest
        what digest to use for fingerprinting

    CLI Example:

    .. code-block:: bash

        salt '*' tls.cert_info /dir/for/certs/cert.pem

    """
    # format that OpenSSL returns dates in
    date_fmt = "%Y%m%d%H%M%SZ"
    if "-----BEGIN" not in cert:
        with salt.utils.files.fopen(cert) as cert_file:
            cert = cert_file.read()
    cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert)

    issuer = {}
    for key, value in cert.get_issuer().get_components():
        if isinstance(key, bytes):
            key = salt.utils.stringutils.to_unicode(key)
        if isinstance(value, bytes):
            value = salt.utils.stringutils.to_unicode(value)
        issuer[key] = value

    subject = {}
    for key, value in cert.get_subject().get_components():
        if isinstance(key, bytes):
            key = salt.utils.stringutils.to_unicode(key)
        if isinstance(value, bytes):
            value = salt.utils.stringutils.to_unicode(value)
        subject[key] = value

    ret = {
        "fingerprint": salt.utils.stringutils.to_unicode(
            cert.digest(salt.utils.stringutils.to_str(digest))
        ),
        "subject": subject,
        "issuer": issuer,
        "serial_number": cert.get_serial_number(),
        "not_before": calendar.timegm(
            time.strptime(
                str(cert.get_notBefore().decode(__salt_system_encoding__)), date_fmt
            )
        ),
        "not_after": calendar.timegm(
            time.strptime(
                cert.get_notAfter().decode(__salt_system_encoding__), date_fmt
            )
        ),
    }

    # add additional info if your version of pyOpenSSL supports it
    if hasattr(cert, "get_extension_count"):
        ret["extensions"] = {}
        for i in range(cert.get_extension_count()):
            try:
                ext = cert.get_extension(i)
                key = salt.utils.stringutils.to_unicode(ext.get_short_name())
                ret["extensions"][key] = str(ext).strip()
            except AttributeError:
                continue

    if "subjectAltName" in ret.get("extensions", {}):
        valid_entries = ("DNS", "IP Address")
        valid_names = set()
        for name in str(ret["extensions"]["subjectAltName"]).split(", "):
            entry, name = name.split(":", 1)
            if entry not in valid_entries:
                log.error(
                    "Cert %s has an entry (%s) which does not start with %s",
                    ret["subject"],
                    name,
                    "/".join(valid_entries),
                )
            else:
                valid_names.add(name)
        ret["subject_alt_names"] = list(valid_names)

    if hasattr(cert, "get_signature_algorithm"):
        try:
            value = cert.get_signature_algorithm()
            if isinstance(value, bytes):
                value = salt.utils.stringutils.to_unicode(value)
            ret["signature_algorithm"] = value
        except AttributeError:
            # On py3 at least
            # AttributeError: cdata 'X509 *' points to an opaque type: cannot read fields
            pass

    return ret


def create_empty_crl(
    ca_name, cacert_path=None, ca_filename=None, crl_file=None, digest="sha256"
):
    """
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

    digest
        The message digest algorithm. Must be a string describing a digest
        algorithm supported by OpenSSL (by EVP_get_digestbyname, specifically).
        For example, "md5" or "sha1". Default: 'sha256'

    CLI Example:

    .. code-block:: bash

        salt '*' tls.create_empty_crl ca_name='koji' \
                ca_filename='ca' \
                crl_file='/etc/openvpn/team1/crl.pem'
    """

    set_ca_path(cacert_path)

    if not ca_filename:
        ca_filename = f"{ca_name}_ca_cert"

    if not crl_file:
        crl_file = f"{_cert_base_path()}/{ca_name}/crl.pem"

    if os.path.exists(f"{crl_file}"):
        return f'CRL "{crl_file}" already exists'

    try:
        with salt.utils.files.fopen(
            f"{cert_base_path()}/{ca_name}/{ca_filename}.crt"
        ) as fp_:
            ca_cert = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM, fp_.read()
            )
        with salt.utils.files.fopen(
            f"{cert_base_path()}/{ca_name}/{ca_filename}.key"
        ) as fp_:
            ca_key = OpenSSL.crypto.load_privatekey(
                OpenSSL.crypto.FILETYPE_PEM, fp_.read()
            )
    except OSError:
        return f'There is no CA named "{ca_name}"'

    crl = OpenSSL.crypto.CRL()
    crl_text = crl.export(
        ca_cert,
        ca_key,
        digest=salt.utils.stringutils.to_bytes(digest),
    )

    with salt.utils.files.fopen(crl_file, "w") as f:
        f.write(salt.utils.stringutils.to_str(crl_text))

    return f'Created an empty CRL: "{crl_file}"'


def revoke_cert(
    ca_name,
    CN,
    cacert_path=None,
    ca_filename=None,
    cert_path=None,
    cert_filename=None,
    crl_file=None,
    digest="sha256",
):
    """
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

    digest
        The message digest algorithm. Must be a string describing a digest
        algorithm supported by OpenSSL (by EVP_get_digestbyname, specifically).
        For example, "md5" or "sha1". Default: 'sha256'

    CLI Example:

    .. code-block:: bash

        salt '*' tls.revoke_cert ca_name='koji' \
                ca_filename='ca' \
                crl_file='/etc/openvpn/team1/crl.pem'

    """

    set_ca_path(cacert_path)
    ca_dir = f"{cert_base_path()}/{ca_name}"

    if ca_filename is None:
        ca_filename = f"{ca_name}_ca_cert"

    if cert_path is None:
        cert_path = f"{_cert_base_path()}/{ca_name}/certs"

    if cert_filename is None:
        cert_filename = f"{CN}"

    try:
        with salt.utils.files.fopen(
            f"{cert_base_path()}/{ca_name}/{ca_filename}.crt"
        ) as fp_:
            ca_cert = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM, fp_.read()
            )
        with salt.utils.files.fopen(
            f"{cert_base_path()}/{ca_name}/{ca_filename}.key"
        ) as fp_:
            ca_key = OpenSSL.crypto.load_privatekey(
                OpenSSL.crypto.FILETYPE_PEM, fp_.read()
            )
    except OSError:
        return f'There is no CA named "{ca_name}"'

    client_cert = _read_cert(f"{cert_path}/{cert_filename}.crt")
    if client_cert is None:
        return f'There is no client certificate named "{CN}"'

    index_file, expire_date, serial_number, subject = _get_basic_info(
        ca_name, client_cert, ca_dir
    )

    index_serial_subject = f"{serial_number}\tunknown\t{subject}"
    index_v_data = f"V\t{expire_date}\t\t{index_serial_subject}"
    index_r_data_pattern = re.compile(
        r"R\t" + expire_date + r"\t\d{12}Z\t" + re.escape(index_serial_subject)
    )
    index_r_data = "R\t{}\t{}\t{}".format(
        expire_date,
        _four_digit_year_to_two_digit(datetime.utcnow()),
        index_serial_subject,
    )

    ret = {}
    with salt.utils.files.fopen(index_file) as fp_:
        for line in fp_:
            line = salt.utils.stringutils.to_unicode(line)
            if index_r_data_pattern.match(line):
                revoke_date = line.split("\t")[2]
                try:
                    datetime.strptime(revoke_date, two_digit_year_fmt)
                    return '"{}/{}.crt" was already revoked, serial number: {}'.format(
                        cert_path, cert_filename, serial_number
                    )
                except ValueError:
                    ret["retcode"] = 1
                    ret["comment"] = (
                        "Revocation date '{}' does not matchformat '{}'".format(
                            revoke_date, two_digit_year_fmt
                        )
                    )
                    return ret
            elif index_serial_subject in line:
                __salt__["file.replace"](
                    index_file, index_v_data, index_r_data, backup=False
                )
                break

    crl = OpenSSL.crypto.CRL()

    with salt.utils.files.fopen(index_file) as fp_:
        for line in fp_:
            line = salt.utils.stringutils.to_unicode(line)
            if line.startswith("R"):
                fields = line.split("\t")
                revoked = OpenSSL.crypto.Revoked()
                revoked.set_serial(salt.utils.stringutils.to_bytes(fields[3]))
                revoke_date_2_digit = datetime.strptime(fields[2], two_digit_year_fmt)
                revoked.set_rev_date(
                    salt.utils.stringutils.to_bytes(
                        revoke_date_2_digit.strftime(four_digit_year_fmt)
                    )
                )
                crl.add_revoked(revoked)

    crl_text = crl.export(
        ca_cert, ca_key, digest=salt.utils.stringutils.to_bytes(digest)
    )

    if crl_file is None:
        crl_file = f"{_cert_base_path()}/{ca_name}/crl.pem"

    if os.path.isdir(crl_file):
        ret["retcode"] = 1
        ret["comment"] = f'crl_file "{crl_file}" is an existing directory'
        return ret

    with salt.utils.files.fopen(crl_file, "w") as fp_:
        fp_.write(salt.utils.stringutils.to_str(crl_text))

    return 'Revoked Certificate: "{}/{}.crt", serial number: {}'.format(
        cert_path, cert_filename, serial_number
    )


if __name__ == "__main__":
    # create_ca('koji', days=365, **cert_sample_meta)
    create_csr(
        "koji",
        CN="test_system",
        C="US",
        ST="Utah",
        L="Centerville",
        O="SaltStack",
        OU=None,
        emailAddress="test_system@saltstack.org",
    )
    create_ca_signed_cert("koji", "test_system")
    create_pkcs12("koji", "test_system", passphrase="test")
