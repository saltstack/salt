# -*- coding: utf-8 -*-
'''
ACME / Let's Encrypt certificate management state
=================================================

.. versionadded: 2016.3

See also the module documentation

.. code-block:: yaml

    reload-gitlab:
      cmd.run:
        - name: gitlab-ctl hup

    dev.example.com:
      acme.cert:
        - aliases:
          - gitlab.example.com
        - email: acmemaster@example.com
        - webroot: /opt/gitlab/embedded/service/gitlab-rails/public
        - renew: 14
        - fire_event: acme/dev.example.com
        - onchanges_in:
          - cmd: reload-gitlab

'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import salt libs
import salt.utils.dictdiffer
import salt.ext.six as six

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work when the ACME module agrees
    '''
    return 'acme.cert' in __salt__


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
         mode='0640',
         certname=None):
    '''
    Obtain/renew a certificate from an ACME CA, probably Let's Encrypt.

    :param name: Common Name of the certificate (DNS name of certificate)
    :param aliases: subjectAltNames (Additional DNS names on certificate)
    :param email: e-mail address for interaction with ACME provider
    :param webroot: True or a full path to webroot. Otherwise use standalone mode
    :param test_cert: Request a certificate from the Happy Hacker Fake CA (mutually exclusive with 'server')
    :param renew: True/'force' to force a renewal, or a window of renewal before expiry in days
    :param keysize: RSA key bits
    :param server: API endpoint to talk to
    :param owner: owner of the private key file
    :param group: group of the private key file
    :param mode: mode of the private key file
    :param certname: Name of the certificate to save
    '''
    ret = {'name': name, 'result': 'changeme', 'comment': [], 'changes': {}}
    action = None

    current_certificate = {}
    new_certificate = {}
    if not __salt__['acme.has'](name):
        action = 'obtain'
    elif __salt__['acme.needs_renewal'](name, renew):
        action = 'renew'
        current_certificate = __salt__['acme.info'](name)
    else:
        ret['result'] = True
        ret['comment'].append('Certificate {} exists and does not need renewal.'
                              ''.format(name))

    if action:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'].append('Certificate {} would have been {}ed.'
                                  ''.format(name, action))
            ret['changes'] = {'old': 'current certificate', 'new': 'new certificate'}
        else:
            res = __salt__['acme.cert'](
                name,
                aliases=aliases,
                email=email,
                webroot=webroot,
                certname=certname,
                test_cert=test_cert,
                renew=renew,
                keysize=keysize,
                server=server,
                owner=owner,
                group=group,
                mode=mode,
                preferred_challenges=preferred_challenges,
                tls_sni_01_port=tls_sni_01_port,
                tls_sni_01_address=tls_sni_01_address,
                http_01_port=http_01_port,
                http_01_address=http_01_address,
                dns_plugin=dns_plugin,
                dns_plugin_credentials=dns_plugin_credentials,
            )
            ret['result'] = res['result']
            ret['comment'].append(res['comment'])
            if ret['result']:
                new_certificate = __salt__['acme.info'](name)
            ret['changes'] = salt.utils.dictdiffer.deep_diff(current_certificate, new_certificate)
    return ret
