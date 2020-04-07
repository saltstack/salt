# -*- coding: utf-8 -*-
"""
Beacon to monitor certificate expiration dates from files on the filesystem.

.. versionadded:: 3000

:maintainer: <devops@eitr.tech>
:maturity: new
:depends: OpenSSL
"""

# Import Python libs
from __future__ import absolute_import, unicode_literals

import logging
from datetime import datetime

# pylint: enable=import-error,no-name-in-module,redefined-builtin,3rd-party-module-not-gated
import salt.utils.files

# Import salt libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin,3rd-party-module-not-gated
from salt.ext.six.moves import map as _map
from salt.ext.six.moves import range as _range

# Import Third Party Libs
try:
    from OpenSSL import crypto

    HAS_OPENSSL = True
except ImportError:
    HAS_OPENSSL = False

log = logging.getLogger(__name__)

DEFAULT_NOTIFY_DAYS = 45

__virtualname__ = "cert_info"


def __virtual__():
    if HAS_OPENSSL is False:
        return False

    return __virtualname__


def validate(config):
    """
    Validate the beacon configuration
    """
    _config = {}
    list(_map(_config.update, config))

    # Configuration for cert_info beacon should be a list of dicts
    if not isinstance(config, list):
        return False, ("Configuration for cert_info beacon must be a list.")

    if "files" not in _config:
        return (
            False,
            ("Configuration for cert_info beacon must contain files option."),
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

    _config = {}
    list(_map(_config.update, config))

    global_notify_days = _config.get("notify_days", DEFAULT_NOTIFY_DAYS)

    for cert_path in _config.get("files", []):
        notify_days = global_notify_days

        if isinstance(cert_path, dict):
            try:
                notify_days = cert_path[cert_path.keys()[0]].get(
                    "notify_days", global_notify_days
                )
                cert_path = cert_path.keys()[0]
            except IndexError as exc:
                log.error("Unable to load certificate %s (%s)", cert_path, exc)
                continue

        try:
            with salt.utils.files.fopen(cert_path) as fp_:
                cert = crypto.load_certificate(crypto.FILETYPE_PEM, fp_.read())
        except (IOError, CryptoError) as exc:
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
            for ext in _range(0, cert.get_extension_count()):
                extensions.append(
                    {
                        "ext_name": cert.get_extension(ext)
                        .get_short_name()
                        .decode(encoding="UTF-8"),
                        "ext_data": str(cert.get_extension(ext)),
                    }
                )

            certificates.append(
                {
                    "cert_path": cert_path,
                    "issuer": ",".join(
                        [
                            '{0}="{1}"'.format(
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
                            '{0}="{1}"'.format(
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
