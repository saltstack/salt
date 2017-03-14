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
from __future__ import absolute_import
import logging

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
    '''

    if __opts__['test']:
        ret = {
            'name': name,
            'changes': {},
            'result': None
        }
        window = None
        try:
            window = int(renew)
        except:  # pylint: disable=bare-except
            pass

        comment = 'Certificate {0} '.format(name)
        if not __salt__['acme.has'](name):
            comment += 'would have been obtained'
        elif __salt__['acme.needs_renewal'](name, window):
            comment += 'would have been renewed'
        else:
            comment += 'would not have been touched'
        ret['comment'] = comment
        return ret

    if not __salt__['acme.has'](name):
        old = None
    else:
        old = __salt__['acme.info'](name)

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
        group=group
    )

    ret = {
        'name': name,
        'result': res['result'] is not False,
        'comment': res['comment']
    }

    if res['result'] is None:
        ret['changes'] = {}
    else:
        ret['changes'] = {
            'old': old,
            'new': __salt__['acme.info'](name)
        }

    return ret
