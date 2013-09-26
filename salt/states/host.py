# -*- coding: utf-8 -*-
'''
Management of addresses and names in hosts file.
================================================

The /etc/hosts file can be managed to contain definitions for specific hosts:

.. code-block:: yaml

    salt-master:
      host.present:
        - ip: 192.168.0.42

Or using the "names:" directive, you can put several names for the same IP.
(Do not try one name with space-separated values).

.. code-block:: yaml

    server1:
      host.present:
        - ip: 192.168.0.42
        - names:
          - server1
          - florida

NOTE: changing the name(s) in the present() function does not cause an
update to remove the old entry.
'''


def present(name, ip):  # pylint: disable=C0103
    '''
    Ensures that the named host is present with the given ip

    name
        The host to assign an ip to

    ip
        The ip addr to apply to the host
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    if __salt__['hosts.has_pair'](ip, name):
        ret['result'] = True
        ret['comment'] = 'Host {0} already present'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = 'Host {0} needs to be added/updated'.format(name)
        return ret
    current_ip = __salt__['hosts.get_ip'](name)
    if current_ip and current_ip != ip:
        __salt__['hosts.rm_host'](current_ip, name)
    if __salt__['hosts.add_host'](ip, name):
        ret['changes'] = {'host': name}
        ret['result'] = True
        ret['comment'] = 'Added host {0}'.format(name)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to set host'
        return ret


def absent(name, ip):  # pylint: disable=C0103
    '''
    Ensure that the named host is absent

    name
        The host to remove

    ip
        The ip addr of the host to remove
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    if not __salt__['hosts.has_pair'](ip, name):
        ret['result'] = True
        ret['comment'] = 'Host {0} already absent'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = 'Host {0} needs to be removed'.format(name)
        return ret
    if __salt__['hosts.rm_host'](ip, name):
        ret['changes'] = {'host': name}
        ret['result'] = True
        ret['comment'] = 'Removed host {0}'.format(name)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to remove host'
        return ret
