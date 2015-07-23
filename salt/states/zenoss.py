# -*- coding: utf-8 -*-
'''
State to manage monitoring in Zenoss.

.. versionadded:: Boron

This state module depends on the 'zenoss' Salt execution module.

Allows for setting a state of minions in Zenoss using the Zenoss API. Currently Zenoss 4.x is supported.

.. code-block:: yaml

    enable_monitoring:
      zenoss.monitored:
        - name: web01.example.com
        - device_class: /Servers/Linux
        - collector: localhost
'''

from __future__ import absolute_import
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if the Zenoss execution module is available.
    '''
    if 'zenoss.add_device' in __salt__:
        return 'zenoss'


def monitored(name, device_class=None, collector='localhost'):
    '''
    Ensure a device is monitored. The 'name' given will be used for Zenoss device name and should be resolvable.

    .. code-block:: yaml

        enable_monitoring:
          zenoss.monitored:
            - name: web01.example.com
            - device_class: /Servers/Linux
            - collector: localhost
    '''

    ret = {}
    ret['name'] = name

    # If device is already monitored, return early
    if __salt__['zenoss.device_exists'](name):
        ret['result'] = True
        ret['changes'] = None
        ret['comment'] = '{0} is already monitored'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'The state of "{0}" will be changed.'.format(name)
        ret['changes'] = {'old': 'monitored == False', 'new': 'monitored == True'}
        ret['result'] = None
        return ret

    # Device not yet in Zenoss. Add and check result
    if __salt__['zenoss.add_device'](name, device_class, collector):
        ret['result'] = True
        ret['changes'] = {'old': 'monitored == False', 'new': 'monitored == True'}
        ret['comment'] = '{0} has been added to Zenoss'.format(name)
    else:
        ret['result'] = False
        ret['changes'] = None
        ret['comment'] = 'Unable to add {0} to Zenoss'.format(name)
    return ret
