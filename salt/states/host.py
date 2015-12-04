# -*- coding: utf-8 -*-
'''
Management of addresses and names in hosts file
===============================================

The ``/etc/hosts`` file can be managed to contain definitions for specific hosts:

.. code-block:: yaml

    salt-master:
      host.present:
        - ip: 192.168.0.42

Or using the ``names`` directive, you can put several names for the same IP.
(Do not try one name with space-separated values).

.. code-block:: yaml

    server1:
      host.present:
        - ip: 192.168.0.42
        - names:
          - server1
          - florida

.. note::

    Changing the ``names`` in ``host.present`` does not cause an
    update to remove the old entry.

.. code-block:: yaml

    server1:
      host.present:
        - ip:
          - 192.168.0.42
          - 192.168.0.43
          - 192.168.0.44
        - names:
          - server1

'''
from __future__ import absolute_import

import salt.utils.validate.net


def present(name, ip):  # pylint: disable=C0103
    '''
    Ensures that the named host is present with the given ip

    name
        The host to assign an ip to

    ip
        The ip addr(s) to apply to the host
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if not isinstance(ip, list):
        ip = [ip]

    comments = []
    for _ip in ip:
        if __salt__['hosts.has_pair'](_ip, name):
            ret['result'] = True
            comments.append('Host {0} ({1}) already present'.format(name, _ip))
        else:
            if __opts__['test']:
                comments.append('Host {0} ({1}) needs to be added/updated'.format(name, _ip))
            else:
                if salt.utils.validate.net.ipv4_addr(_ip) or salt.utils.validate.net.ipv6_addr(_ip):
                    if __salt__['hosts.add_host'](_ip, name):
                        ret['changes'] = {'host': name}
                        ret['result'] = True
                        comments.append('Added host {0} ({1})'.format(name, _ip))
                    else:
                        ret['result'] = False
                        comments.append('Failed to set host')
                else:
                    ret['result'] = False
                    comments.append('Invalid IP Address for {0} ({1})'.format(name, _ip))
    ret['comment'] = '\n'.join(comments)
    return ret


def absent(name, ip):  # pylint: disable=C0103
    '''
    Ensure that the named host is absent

    name
        The host to remove

    ip
        The ip addr(s) of the host to remove
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if not isinstance(ip, list):
        ip = [ip]

    comments = []
    for _ip in ip:
        if not __salt__['hosts.has_pair'](_ip, name):
            ret['result'] = True
            comments.append('Host {0} ({1}) already absent'.format(name, _ip))
        else:
            if __opts__['test']:
                comments.append('Host {0} ({1} needs to be removed'.format(name, _ip))
            else:
                if __salt__['hosts.rm_host'](_ip, name):
                    ret['changes'] = {'host': name}
                    ret['result'] = True
                    comments.append('Removed host {0} ({1})'.format(name, _ip))
                else:
                    ret['result'] = False
                    comments.append('Failed to remove host')
    ret['comment'] = '\n'.join(comments)
    return ret
