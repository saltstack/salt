# -*- coding: utf-8 -*-
'''
.. versionadded:: Fluorine

Management of Dell DRAC

The DRAC module is used to create and manage DRAC cards on Dell servers

Ensure the property is set

  .. code-block:: yaml

  test:
    dracr.property_present:
       - properties:
           System.ServerOS.HostName: "Pretty-server"
           System.ServerOS.OSName: "Ubuntu 16.04"
       - admin_password: calvin
       - admin_root: myuser
       - host: 10.10.10.1

'''

from __future__ import absolute_import, print_function, unicode_literals

import re
import salt.exceptions
import salt.utils.path


def __virtual__():
    '''
    Ensure the racadm command is installed
    '''
    if salt.utils.path.which('racadm'):
        return True

    return False


def property_present(properties, admin_username='root', admin_password='calvin', host=None, **kwargs):
    '''
    properties = {}
    '''

    ret = {'name': host,
           'context': {'Host': host},
           'result': True,
           'changes': {},
           'comment': ''}

    if host is None:
        output = __salt__['cmd.run_all']('ipmitool lan print')
        stdout = output['stdout']
        reg = re.compile(r'\s*IP Address\s*:\s*(\d+.\d+.\d+.\d+)\s*')
        for line in stdout:
            result = reg.match(line)
            if result is not None:
                # we want group(1) as this is match in parentheses
                host = result.group(1)
                break

    if not host:
        ret['result'] = False
        ret['comment'] = 'Unknown host!'
        return ret

    properties_get = {}

    for key, value in properties.items():
        response = __salt__['dracr.get_property'](host, admin_username, admin_password, key)
        if response is False or response['retcode'] != 0:
            ret['result'] = False
            ret['comment'] = 'Failed to get property from idrac'
            return ret
        properties_get[key] = response['stdout'].split('\n')[-1].split('=')[-1]

    if __opts__['test']:
        for key, value in properties.items():
            if properties_get[key] == value:
                ret['changes'][key] = 'Won\'t be changed'
            else:
                ret['changes'][key] = 'Will be changed to {0}'.format(properties_get[key])
        return ret

    for key, value in properties.items():
        if properties_get[key] != value:
            response = __salt__['dracr.set_property'](host, admin_username, admin_password, key, value)
            if response is False or response['retcode'] != 0:
                ret['result'] = False
                ret['comment'] = 'Failed to set property from idrac'
                return ret

            ret['changes'][key] = 'will be changed - old value {0} , new value {1}'.format(properties_get[key], value)

    return ret
