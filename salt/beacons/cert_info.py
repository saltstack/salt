"""
Beacon to monitor certificate expiration dates from files on the filesystem.

.. versionadded:: 3000

:maintainer: <devops@eitr.tech>
:maturity: new
:depends: OpenSSL
"""

import logging
from datetime import datetime

import salt.utils.beacons
import salt.utils.files

try:
    from OpenSSL import crypto

    HAS_OPENSSL = True
except ImportError:
    HAS_OPENSSL = False

# pyOpenSSL >= 25 removed X509.get_extension / X509.get_extension_count
# (and X509Extension as a whole). This beacon iterates extensions via the
# removed API, so refuse to load when those attributes are gone.
HAS_X509_EXTENSION_API = HAS_OPENSSL and hasattr(crypto.X509(), "get_extension")

log = logging.getLogger(__name__)

DEFAULT_NOTIFY_DAYS = 45

__virtualname__ = "cert_info"


def _format_x509_extension_value(ext):
    """
    Re-format a ``cryptography.x509.Extension`` value into the legacy
    OpenSSL printable string ("CA:FALSE", "DNS:host", "IP Address:1.2.3.4",
    ...) that pyOpenSSL <= 25 emitted via ``str(cert.get_extension(i))``.

    Only used on pyOpenSSL >= 26, which removed the legacy X509 extension
    API; consumers of this beacon would otherwise have to special-case the
    pyOpenSSL version. Imported lazily so ``cryptography`` stays an
    optional runtime dependency.
    """
    from cryptography import x509  # pylint: disable=import-outside-toplevel

    oid = ext.oid
    value = ext.value
    if oid == x509.ExtensionOID.BASIC_CONSTRAINTS:
        out = "CA:TRUE" if value.ca else "CA:FALSE"
        if value.path_length is not None:
            out += f", pathlen:{value.path_length}"
        return out
    if oid in (
        x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME,
        x509.ExtensionOID.ISSUER_ALTERNATIVE_NAME,
    ):
        items = []
        for name in value:
            if isinstance(name, x509.DNSName):
                items.append(f"DNS:{name.value}")
            elif isinstance(name, x509.IPAddress):
                items.append(f"IP Address:{name.value}")
            elif isinstance(name, x509.RFC822Name):
                items.append(f"email:{name.value}")
            elif isinstance(name, x509.UniformResourceIdentifier):
                items.append(f"URI:{name.value}")
            else:
                items.append(str(name))
        return ", ".join(items)
    return str(value)


def __virtual__():
    if HAS_OPENSSL is False:
        err_msg = "OpenSSL library is missing."
        log.error("Unable to load %s beacon: %s", __virtualname__, err_msg)
        return False, err_msg
    if not HAS_X509_EXTENSION_API:
        err_msg = "pyOpenSSL >= 25 removed the X509Extension API used by this beacon."
        log.error("Unable to load %s beacon: %s", __virtualname__, err_msg)
        return False, err_msg

    return __virtualname__


def validate(config):
    """
    Validate the beacon configuration
    """
    # Configuration for cert_info beacon should be a list of dicts
    if not isinstance(config, list):
        return False, "Configuration for cert_info beacon must be a list."

    config = salt.utils.beacons.list_to_dict(config)

    if "files" not in config:
        return (
            False,
            "Configuration for cert_info beacon must contain files option.",
        )
    return True, "Valid beacon configuration"


def beacon(config):
    """
    Monitor the certificate files on the minion.

    Specify a notification threshold in days and only emit a beacon if any certificates are
    expiring within that timeframe or if `notify_days` equals `-1` (always report information).
    The default notification threshold is 45 days and can be overridden at the beacon level and
    at an individual certificate level.

    .. code-block:: yaml

        beacons:
          cert_info:
            - files:
                - /etc/pki/tls/certs/mycert.pem
                - /etc/pki/tls/certs/yourcert.pem:
                    notify_days: 15
                - /etc/pki/tls/certs/ourcert.pem
            - notify_days: 45
            - interval: 86400

    """
    ret = []
    certificates = []
    CryptoError = crypto.Error  # pylint: disable=invalid-name

    config = salt.utils.beacons.list_to_dict(config)

    global_notify_days = config.get("notify_days", DEFAULT_NOTIFY_DAYS)

    for cert_path in config.get("files", []):
        notify_days = global_notify_days

        if isinstance(cert_path, dict):
            try:
                next_cert_path = next(iter(cert_path))
                notify_days = cert_path[next_cert_path].get(
                    "notify_days", global_notify_days
                )
            except StopIteration as exc:
                log.error("Unable to load certificate %s (%s)", cert_path, exc)
                continue
            else:
                cert_path = next_cert_path

        try:
            with salt.utils.files.fopen(cert_path) as fp_:
                cert = crypto.load_certificate(crypto.FILETYPE_PEM, fp_.read())
        except (OSError, CryptoError) as exc:
            log.error("Unable to load certificate %s (%s)", cert_path, exc)
            continue

        cert_date = datetime.strptime(
            cert.get_notAfter().decode(encoding="UTF-8"), "%Y%m%d%H%M%SZ"
        )
        date_diff = (cert_date - datetime.today()).days
        log.debug("Certificate %s expires in %s days.", cert_path, date_diff)

        if notify_days < 0 or date_diff <= notify_days:
            log.debug(
                "Certificate %s triggered beacon due to %s day notification threshold.",
                cert_path,
                notify_days,
            )
            extensions = []
            if hasattr(cert, "get_extension"):
                # pyOpenSSL <= 25 still exposes the legacy X509 extension API.
                for ext in range(0, cert.get_extension_count()):
                    extensions.append(
                        {
                            "ext_name": cert.get_extension(ext)
                            .get_short_name()
                            .decode(encoding="UTF-8"),
                            "ext_data": str(cert.get_extension(ext)),
                        }
                    )
            else:
                # pyOpenSSL >= 26 removed get_extension* on X509; go through
                # the cryptography conversion which exposes a stable
                # x509.Extension API on every version.
                for ext in cert.to_cryptography().extensions:
                    try:
                        short_name = ext.oid._name
                    except AttributeError:
                        short_name = ext.oid.dotted_string
                    extensions.append(
                        {
                            "ext_name": short_name,
                            "ext_data": _format_x509_extension_value(ext),
                        }
                    )

            certificates.append(
                {
                    "cert_path": cert_path,
                    "issuer": ",".join(
                        [
                            '{}="{}"'.format(
                                t[0].decode(encoding="UTF-8"),
                                t[1].decode(encoding="UTF-8"),
                            )
                            for t in cert.get_issuer().get_components()
                        ]
                    ),
                    "issuer_dict": {
                        k.decode("UTF-8"): v.decode("UTF-8")
                        for k, v in cert.get_issuer().get_components()
                    },
                    "notAfter_raw": cert.get_notAfter().decode(encoding="UTF-8"),
                    "notAfter": cert_date.strftime("%Y-%m-%d %H:%M:%SZ"),
                    "notBefore_raw": cert.get_notBefore().decode(encoding="UTF-8"),
                    "notBefore": datetime.strptime(
                        cert.get_notBefore().decode(encoding="UTF-8"), "%Y%m%d%H%M%SZ"
                    ).strftime("%Y-%m-%d %H:%M:%SZ"),
                    "serial_number": cert.get_serial_number(),
                    "signature_algorithm": cert.get_signature_algorithm().decode(
                        encoding="UTF-8"
                    ),
                    "subject": ",".join(
                        [
                            '{}="{}"'.format(
                                t[0].decode(encoding="UTF-8"),
                                t[1].decode(encoding="UTF-8"),
                            )
                            for t in cert.get_subject().get_components()
                        ]
                    ),
                    "subject_dict": {
                        k.decode("UTF-8"): v.decode("UTF-8")
                        for k, v in cert.get_subject().get_components()
                    },
                    "version": cert.get_version(),
                    "extensions": extensions,
                    "has_expired": cert.has_expired(),
                }
            )

    if certificates:
        ret.append({"certificates": certificates})

    return ret
