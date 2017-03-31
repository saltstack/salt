# -*- coding: utf-8 -*-
'''
ACME / Let's Encrypt module
===========================

.. versionadded: 2016.3

This module currently uses letsencrypt-auto, which needs to be available in the path or in /opt/letsencrypt/.

.. note::

    Installation & configuration of the Let's Encrypt client can for example be done using
    https://github.com/saltstack-formulas/letsencrypt-formula

.. warning::

    Be sure to set at least accept-tos = True in cli.ini!

Most parameters will fall back to cli.ini defaults if None is given.

'''
# Import python libs
from __future__ import absolute_import
import logging
import datetime
import os

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

LEA = salt.utils.which_bin(['certbot', 'letsencrypt',
                            'certbot-auto', 'letsencrypt-auto',
                            '/opt/letsencrypt/letsencrypt-auto'])
LE_LIVE = '/etc/letsencrypt/live/'


def __virtual__():
    '''
    Only work when letsencrypt-auto is installed
    '''
    return LEA is not None, 'The ACME execution module cannot be loaded: letsencrypt-auto not installed.'


def _cert_file(name, cert_type):
    '''
    Return expected path of a Let's Encrypt live cert
    '''
    return os.path.join(LE_LIVE, name, '{0}.pem'.format(cert_type))


def _expires(name):
    '''
    Return the expiry date of a cert

    :return datetime object of expiry date
    '''
    cert_file = _cert_file(name, 'cert')
    # Use the salt module if available
    if 'tls.cert_info' in __salt__:
        expiry = __salt__['tls.cert_info'](cert_file)['not_after']
    # Cobble it together using the openssl binary
    else:
        openssl_cmd = 'openssl x509 -in {0} -noout -enddate'.format(cert_file)
        # No %e format on my Linux'es here
        strptime_sux_cmd = 'date --date="$({0} | cut -d= -f2)" +%s'.format(openssl_cmd)
        expiry = float(__salt__['cmd.shell'](strptime_sux_cmd, output_loglevel='quiet'))
        # expiry = datetime.datetime.strptime(expiry.split('=', 1)[-1], '%b %e %H:%M:%S %Y %Z')

    return datetime.datetime.fromtimestamp(expiry)


def _renew_by(name, window=None):
    '''
    Date before a certificate should be renewed

    :param name: Common Name of the certificate (DNS name of certificate)
    :param window: days before expiry date to renew
    :return datetime object of first renewal date
    '''
    expiry = _expires(name)
    if window is not None:
        expiry = expiry - datetime.timedelta(days=window)

    return expiry


def cert(name,
         aliases=None,
         email=None,
         webroot=None,
         test_cert=False,
         renew=None,
         keysize=None,
         server=None,
         owner='root',
         group='root',
         certname=None):
    '''
    Obtain/renew a certificate from an ACME CA, probably Let's Encrypt.

    :param name: Common Name of the certificate (DNS name of certificate)
    :param aliases: subjectAltNames (Additional DNS names on certificate)
    :param email: e-mail address for interaction with ACME provider
    :param webroot: True or a full path to use to use webroot. Otherwise use standalone mode
    :param test_cert: Request a certificate from the Happy Hacker Fake CA (mutually exclusive with 'server')
    :param renew: True/'force' to force a renewal, or a window of renewal before expiry in days
    :param keysize: RSA key bits
    :param server: API endpoint to talk to
    :param owner: owner of private key
    :param group: group of private key
    :param certname: Name of the certificate to save
    :return: dict with 'result' True/False/None, 'comment' and certificate's expiry date ('not_after')

    CLI example:

    .. code-block:: bash

        salt 'gitlab.example.com' acme.cert dev.example.com "[gitlab.example.com]" test_cert=True renew=14 webroot=/opt/gitlab/embedded/service/gitlab-rails/public
    '''

    cmd = [LEA, 'certonly', '--quiet']

    cert_file = _cert_file(name, 'cert')
    if not __salt__['file.file_exists'](cert_file):
        log.debug('Certificate {0} does not exist (yet)'.format(cert_file))
        renew = False
    elif needs_renewal(name, renew):
        log.debug('Certificate {0} will be renewed'.format(cert_file))
        cmd.append('--renew-by-default')
        renew = True
    else:
        return {
            'result': None,
            'comment': 'Certificate {0} does not need renewal'.format(cert_file),
            'not_after': expires(name)
        }

    if server:
        cmd.append('--server {0}'.format(server))

    if certname:
        cmd.append('--cert-name {0}'.format(certname))

    if test_cert:
        if server:
            return {'result': False, 'comment': 'Use either server or test_cert, not both'}
        cmd.append('--test-cert')

    if webroot:
        cmd.append('--authenticator webroot')
        if webroot is not True:
            cmd.append('--webroot-path {0}'.format(webroot))
    else:
        cmd.append('--authenticator standalone')

    if email:
        cmd.append('--email {0}'.format(email))

    if keysize:
        cmd.append('--rsa-key-size {0}'.format(keysize))

    cmd.append('--domains {0}'.format(name))
    if aliases is not None:
        for dns in aliases:
            cmd.append('--domains {0}'.format(dns))

    res = __salt__['cmd.run_all'](' '.join(cmd))

    if res['retcode'] != 0:
        return {'result': False, 'comment': 'Certificate {0} renewal failed with:\n{1}'.format(name, res['stderr'])}

    if renew:
        comment = 'Certificate {0} renewed'.format(name)
    else:
        comment = 'Certificate {0} obtained'.format(name)
    ret = {'comment': comment, 'not_after': expires(name)}

    res = __salt__['file.check_perms'](_cert_file(name, 'privkey'), {}, owner, group, '0600', follow_symlinks=True)

    if res is None:
        ret['result'] = False
        ret['comment'] += ', but setting permissions failed.'
    elif not res[0].get('result', False):
        ret['result'] = False
        ret['comment'] += ', but setting permissions failed with \n{0}'.format(res[0]['comment'])
    else:
        ret['result'] = True
        ret['comment'] += '.'

    return ret


def certs():
    '''
    Return a list of active certificates

    CLI example:

    .. code-block:: bash

        salt 'vhost.example.com' acme.certs
    '''
    return __salt__['file.readdir'](LE_LIVE)[2:]


def info(name):
    '''
    Return information about a certificate

    .. note::
        Will output tls.cert_info if that's available, or OpenSSL text if not

    :param name: CommonName of cert

    CLI example:

    .. code-block:: bash

        salt 'gitlab.example.com' acme.info dev.example.com
    '''
    cert_file = _cert_file(name, 'cert')
    # Use the salt module if available
    if 'tls.cert_info' in __salt__:
        info = __salt__['tls.cert_info'](cert_file)
        # Strip out the extensions object contents;
        # these trip over our poor state output
        # and they serve no real purpose here anyway
        info['extensions'] = info['extensions'].keys()
        return info
    # Cobble it together using the openssl binary
    else:
        openssl_cmd = 'openssl x509 -in {0} -noout -text'.format(cert_file)
        return __salt__['cmd.run'](openssl_cmd, output_loglevel='quiet')


def expires(name):
    '''
    The expiry date of a certificate in ISO format

    :param name: CommonName of cert

    CLI example:

    .. code-block:: bash

        salt 'gitlab.example.com' acme.expires dev.example.com
    '''
    return _expires(name).isoformat()


def has(name):
    '''
    Test if a certificate is in the Let's Encrypt Live directory

    :param name: CommonName of cert

    Code example:

    .. code-block:: python

        if __salt__['acme.has']('dev.example.com'):
            log.info('That is one nice certificate you have there!')
    '''
    return __salt__['file.file_exists'](_cert_file(name, 'cert'))


def renew_by(name, window=None):
    '''
    Date in ISO format when a certificate should first be renewed

    :param name: CommonName of cert
    :param window: number of days before expiry when renewal should take place
    '''
    return _renew_by(name, window).isoformat()


def needs_renewal(name, window=None):
    '''
    Check if a certicate needs renewal

    :param name: CommonName of cert
    :param window: Window in days to renew earlier or True/force to just return True

    Code example:

    .. code-block:: python

        if __salt__['acme.needs_renewal']('dev.example.com'):
            __salt__['acme.cert']('dev.example.com', **kwargs)
        else:
            log.info('Your certificate is still good')
    '''
    if window is not None and window in ('force', 'Force', True):
        return True

    return _renew_by(name, window) <= datetime.datetime.today()
