# -*- coding: utf-8 -*-
'''
Management of Dell DRAC

The DRAC module is used to create and manage DRAC cards on Dell servers

Ensure the property is set

  .. code-block:: yaml

  test:
    dracr.property:
       - properties:
           System.ServerOS.HostName: "Pretty-server"
           System.ServerOS.OSName: "Ubuntu 16.04"
       - admin_password: calvin
       - admin_root: myuser
       - host: 10.10.10.1

'''

from __future__ import absolute_import

import salt.exceptions

def __virtual__():
    '''
    Ensure the racadm command is installed
    '''
    if salt.utils.which('racadm'):
        return True

    return False

def property(properties, admin_username='root', admin_password='calvin', host=None, **kwangs):
    ''' properties = {} '''

    ret = {'name': host,
           'context': {'Host': host},
           'result': True,
           'changes': {},
           'comment': ''}

    if host is None:
        host = __salt__['cmd.run_all']('ipmitool lan print | tr -d " " | grep "IPAddress:" | cut -f 2 -d ":"', python_shell=True)  #("/usr/bin/ipmitool {0} {1} {2}".format('lan', 'print', '|'))
        host = host['stdout']
    if not host:
        ret['result'] = False
        ret['comment'] = 'Unknown host!'
        return ret

    properties_get = {}

    for k, v in properties.items():
        response = __salt__['dracr.get_property'](host, admin_username, admin_password, k)
        if response is False or response['retcode'] != 0:
            ret['result'] = False
            ret['comment'] = 'Failed to get property from idrac'
            return ret
        properties_get[k] = response['stdout'].split('\n')[-1].split('=')[-1]

    if __opts__['test']:
        for k, v in properties.items():
             if properties_get[k] == v:
                  ret['changes'][k] = "Won't be changed"
             else:
                  ret['changes'][k] = "Will be changed to %s" % properties_get[k]
        return ret

    for k, v in properties.items():
        if properties_get[k] != v:
            response = __salt__['dracr.set_property'](host, admin_username, admin_password, k, v)
            if response is False or response['retcode'] != 0:
                ret['result'] = False
                ret['comment'] = 'Failed to set property from idrac'
                return ret

            ret['changes'][k] = 'will be changed - old value %s , new value %s' % (properties_get[k], v)

    return ret

