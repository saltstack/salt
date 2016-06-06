# -*- coding: utf-8 -*-
'''
Return salt data to Zabbix
The following Type: "Zabbix trapper" with "Type of information" Text items are required

Key: salt.trap.info
Key: salt.trap.average
Key: salt.trap.warning
Key: salt.trap.high
Key: salt.trap.disaster

  To use the Zabbix returner, append '--return zabbix' to the salt command. ex:
  .. code-block:: bash
    salt '*' test.ping --return zabbix
'''
from __future__ import absolute_import
import logging
log = logging.getLogger(__name__)


# Define the module's virtual name
__virtualname__ = 'zabbix'


def __virtual__():
    return __virtualname__


def zabbix_sender(key, host, output):
    zabbix_sender = "/usr/local/zabbix/bin/zabbix_sender"
    zabbix_config = "/usr/local/zabbix/etc/zabbix_agentd.conf"
    cmd = zabbix_sender + " -c " + zabbix_config + " -s " + host + " -k " + key + " -o \"" + output +"\""
    __salt__['cmd.shell'](cmd)


def returner(ret):
    changes = False
    errors = False
    job_minion_id = ret['id']
    host = job_minion_id.split('.')[0]

    if type(ret['return']) is dict:
        for state, item in ret['return'].iteritems():
            if not item['result']:
                errors = True
                zabbix_sender("salt.trap.high", host, 'SALT:\nname: {0}\ncomment: {1}'.format(item['name'], item['comment']))
            if item['changes']:
                changes = True
                zabbix_sender("salt.trap.warning", host, 'SALT:\nname: {0}\ncomment: {1}'.format(item['name'], item['comment']))

    if not changes and not errors:
        zabbix_sender("salt.trap.info", host, 'SALT {0} OK'.format(job_minion_id))
