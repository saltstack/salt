# -*- coding: utf-8 -*-
'''
Allows you to manage proxy settings on minions
=======================

Setup proxy settings on minions

.. code-block:: yaml

    192.168.1.4:
      proxy.managed:
        - port: 3128
        - bypass_domains:
            - localhost
            - 127.0.0.1
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)
__virtualname__ = 'proxy'


def __virtual__():
    '''
    Only work on Mac OS and Windows
    '''
    if salt.utils.is_darwin() or salt.utils.is_windows():
        return True
    return False


def managed(name, port, services=None, user=None, password=None, bypass_domains=None, network_service='Ethernet'):
    '''
    Manages proxy settings for this mininon

    name
        The proxy server to use

    port
        The port used by the proxy server

    services
        A list of the services that should use the given proxy settings, valid services include http, https and ftp.
        If no service is given all of the valid services will be used.

    user
        The username to use for the proxy server if required

    password
        The password to use if required by the server

    bypass_domains
        An array of the domains that should bypass the proxy

    network_service
        The network service to apply the changes to, this only necessary on OSX
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}

    valid_services = ['http', 'https', 'ftp']

    if services is None:
        services = valid_services

    # Darwin
    if __grains__['os'] in ['MacOS', 'Darwin']:
        ret['changes'] = {'new': []}

        for service in services:
            current_settings = __salt__['proxy.get_{0}_proxy'.format(service)]()

            if current_settings.get('server') == name and current_settings.get('port') == str(port):
                ret['comment'] += '{0} proxy settings already set.\n'.format(service)
            elif __salt__['proxy.set_{0}_proxy'.format(service)](name, port, user, password, network_service):
                ret['comment'] += '{0} proxy settings updated correctly\n'.format(service)
                ret['changes']['new'].append({'service': service, 'server': name, 'port': port, 'user': user})
            else:
                ret['result'] = False
                ret['comment'] += 'Failed to set {0} proxy settings.\n'

        if bypass_domains is not None:

            current_domains = __salt__['proxy.get_proxy_bypass']()

            if len(set(current_domains).intersection(bypass_domains)) == len(bypass_domains):
                ret['comment'] += 'Proxy bypass domains are already set correctly.\n'
            elif __salt__['proxy.set_proxy_bypass'](bypass_domains, network_service):
                ret['comment'] += 'Proxy bypass domains updated correctly\n'
                ret['changes']['new'].append({'bypass_domains': list(set(bypass_domains).difference(current_domains))})
            else:
                ret['result'] = False
                ret['comment'] += 'Failed to set bypass proxy domains.\n'

        if len(ret['changes']['new']) == 0:
            del ret['changes']['new']

        return ret

    # Windows - Needs its own branch as all settings need to be set at the same time
    if __grains__['os'] in ['Windows']:
        changes_needed = False
        current_settings = __salt__['proxy.get_proxy_win']()
        current_domains = __salt__['proxy.get_proxy_bypass']()

        if current_settings.get('enabled', False) is True:
            for service in services:
                # We need to update one of our proxy servers
                if service not in current_settings:
                    changes_needed = True
                    break

                if current_settings[service]['server'] != name or current_settings[service]['port'] != str(port):
                    changes_needed = True
                    break
        else:
            # Proxy settings aren't enabled
            changes_needed = True

        # We need to update our bypass domains
        if len(set(current_domains).intersection(bypass_domains)) != len(bypass_domains):
            changes_needed = True

        if changes_needed:
            if __salt__['proxy.set_proxy_win'](name, port, services, bypass_domains):
                ret['comment'] = 'Proxy settings updated correctly'
            else:
                ret['result'] = False
                ret['comment'] = 'Failed to set {0} proxy settings.'
        else:
            ret['comment'] = 'Proxy settings already correct.'

    return ret
