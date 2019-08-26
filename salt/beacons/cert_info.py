# -*- coding: utf-8 -*-
'''
Beacon to monitor certificate expiration dates from files on the filesystem.

.. versionadded:: Sodium

:maintainer: <devops@eitr.tech>
:maturity: new
:depends: OpenSSL
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals
from datetime import datetime
import logging

# Import salt libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin,3rd-party-module-not-gated
from salt.six.moves import map as _map
from salt.six.moves import range as _range
# pylint: enable=import-error,no-name-in-module,redefined-builtin,3rd-party-module-not-gated
import salt.utils.files


# Import Third Party Libs
try:
    from OpenSSL import crypto
    HAS_OPENSSL = True
except ImportError:
    HAS_OPENSSL = False

log = logging.getLogger(__name__)

DEFAULT_NOTIFY_DAYS = 45

__virtualname__ = 'cert_info'


def __virtual__():
    if HAS_OPENSSL is False:
        return False

    return __virtualname__


def validate(config):
    '''
    Validate the beacon configuration
    '''
    _config = {}
    list(_map(_config.update, config))

    # Configuration for cert_info beacon should be a list of dicts
    if not isinstance(config, list):
        return False, ('Configuration for cert_info beacon must be a list.')

    if 'files' not in _config:
        return False, ('Configuration for cert_info beacon '
                       'must contain files option.')
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    Monitor the certificate files on the minion.

    Specify a notification threshold in days and only emit a beacon if any certificates are
    expiring within that timeframe or if `notify_days` equals `-1` (always report information).

    .. code-block:: yaml

        beacons:
          cert_info:
            - files:
                - /etc/pki/tls/certs/mycert.pem
            - notify_days: 45
            - interval: 86400

    '''
    ret = []
    certificates = []
    CryptoError = crypto.Error  # pylint: disable=invalid-name

    _config = {}
    list(_map(_config.update, config))

    notify_days = _config.get('notify_days', DEFAULT_NOTIFY_DAYS)

    for cert_path in _config.get('files', []):
        try:
            with salt.utils.files.fopen(cert_path) as fp_:
                cert = crypto.load_certificate(crypto.FILETYPE_PEM, fp_.read())
        except (IOError, CryptoError) as exc:
            log.error('Unable to load certificate %s (%s)', cert_path, exc)
            continue

        cert_date = datetime.strptime(cert.get_notAfter(), "%Y%m%d%H%M%SZ")
        date_diff = (cert_date - datetime.today()).days
        log.debug('Certificate %s expires in %s days.', cert_path, date_diff)

        if notify_days < 0 or date_diff <= notify_days:
            log.debug('Certificate %s triggered beacon due to %s day notification threshold.', cert_path, notify_days)
            extensions = []
            for ext in _range(0, cert.get_extension_count()):
                extensions.append(
                    {
                        'ext_name': cert.get_extension(ext).get_short_name(),
                        'ext_data': str(cert.get_extension(ext))
                    }
                )

            certificates.append(
                {
                    'cert_path': cert_path,
                    'issuer': ','.join(['{0}="{1}"'.format(t[0], t[1]) for t in cert.get_issuer().get_components()]),
                    'issuer_raw': cert.get_issuer().get_components(),
                    'issuer_dict': dict(cert.get_issuer().get_components()),
                    'notAfter_raw': cert.get_notAfter(),
                    'notAfter': cert_date.strftime("%Y-%m-%d %H:%M:%SZ"),
                    'notBefore_raw': cert.get_notBefore(),
                    'notBefore': datetime.strptime(
                                     cert.get_notBefore(), "%Y%m%d%H%M%SZ").strftime("%Y-%m-%d %H:%M:%SZ"),
                    'serial_number': cert.get_serial_number(),
                    'signature_algorithm': cert.get_signature_algorithm(),
                    'subject': ','.join(['{0}="{1}"'.format(t[0], t[1]) for t in cert.get_subject().get_components()]),
                    'subject_raw': cert.get_subject().get_components(),
                    'subject_dict': dict(cert.get_subject().get_components()),
                    'version': cert.get_version(),
                    'extensions': extensions,
                    'has_expired': cert.has_expired()
                }
            )

    if certificates:
        ret.append({'certificates': certificates})

    return ret
