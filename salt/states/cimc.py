# -*- coding: utf-8 -*-
'''
A state module to manage Cisco UCS chassis devices.

:codeauthor: :email:`Spencer Ervin <spencer_ervin@hotmail.com>`
:maturity:   new
:depends:    none
:platform:   unix


About
=====
This state module was designed to handle connections to a Cisco Unified Computing System (UCS) chassis. This module
relies on the CIMC proxy module to interface with the device.

.. seealso::
    :prox:`CIMC Proxy Module <salt.proxy.cimc>`

'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

log = logging.getLogger(__name__)


def __virtual__():
    return 'cimc.get_system_info' in __salt__


def _default_ret(name):
    '''
    Set the default response values.

    '''
    ret = {
        'name': name,
        'changes': {},
        'result': False,
        'comment': ''
    }
    return ret


def ntp(name, servers):
    '''
    Ensures that the NTP servers are configured. Servers are provided as an individual string or list format. Only four
    NTP servers will be reviewed. Any entries past four will be ignored.

    name: The name of the module function to execute.

    servers(str, list): The IP address or FQDN of the NTP servers.

    SLS Example:

    .. code-block:: yaml

        ntp_configuration_list:
          cimc.ntp:
            - servers:
              - foo.bar.com
              - 10.10.10.10

        ntp_configuration_str:
          cimc.ntp:
            - servers: foo.bar.com

    '''
    ret = _default_ret(name)

    ntp_servers = ['', '', '', '']

    # Parse our server arguments
    if isinstance(servers, list):
        i = 0
        for x in servers:
            ntp_servers[i] = x
            i += 1
    else:
        ntp_servers[0] = servers

    conf = __salt__['cimc.get_ntp']()

    # Check if our NTP configuration is already set
    req_change = False
    try:
        if conf['outConfigs']['commNtpProvider'][0]['ntpEnable'] != 'yes' \
                or ntp_servers[0] != conf['outConfigs']['commNtpProvider'][0]['ntpServer1'] \
                or ntp_servers[1] != conf['outConfigs']['commNtpProvider'][0]['ntpServer2'] \
                or ntp_servers[2] != conf['outConfigs']['commNtpProvider'][0]['ntpServer3'] \
                or ntp_servers[3] != conf['outConfigs']['commNtpProvider'][0]['ntpServer4']:
            req_change = True
    except KeyError as err:
        ret['result'] = False
        ret['comment'] = "Unable to confirm current NTP settings."
        log.error(err)
        return ret

    if req_change:

        try:
            update = __salt__['cimc.set_ntp_server'](ntp_servers[0],
                                                     ntp_servers[1],
                                                     ntp_servers[2],
                                                     ntp_servers[3])
            if update['outConfig']['commNtpProvider'][0]['status'] != 'modified':
                ret['result'] = False
                ret['comment'] = "Error setting NTP configuration."
                return ret
        except Exception as err:
            ret['result'] = False
            ret['comment'] = "Error setting NTP configuration."
            log.error(err)
            return ret

        ret['changes']['before'] = conf
        ret['changes']['after'] = __salt__['cimc.get_ntp']()
        ret['comment'] = "NTP settings modified."
    else:
        ret['comment'] = "NTP already configured. No changes required."

    ret['result'] = True

    return ret


def syslog(name, primary=None, secondary=None):
    '''
    Ensures that the syslog servers are set to the specified values. A value of None will be ignored.

    name: The name of the module function to execute.

    primary(str): The IP address or FQDN of the primary syslog server.

    secondary(str): The IP address or FQDN of the secondary syslog server.

    SLS Example:

    .. code-block:: yaml

        syslog_configuration:
          cimc.syslog:
            - primary: 10.10.10.10
            - secondary: foo.bar.com

    '''
    ret = _default_ret(name)

    conf = __salt__['cimc.get_syslog']()

    req_change = False

    if primary:
        prim_change = True
        if 'outConfigs' in conf and 'commSyslogClient' in conf['outConfigs']:
            for entry in conf['outConfigs']['commSyslogClient']:
                if entry['name'] != 'primary':
                    continue
                if entry['adminState'] == 'enabled' and entry['hostname'] == primary:
                    prim_change = False

        if prim_change:
            try:
                update = __salt__['cimc.set_syslog_server'](primary, "primary")
                if update['outConfig']['commSyslogClient'][0]['status'] == 'modified':
                    req_change = True
                else:
                    ret['result'] = False
                    ret['comment'] = "Error setting primary SYSLOG server."
                    return ret
            except Exception as err:
                ret['result'] = False
                ret['comment'] = "Error setting primary SYSLOG server."
                log.error(err)
                return ret

    if secondary:
        sec_change = True
        if 'outConfig' in conf and 'commSyslogClient' in conf['outConfig']:
            for entry in conf['outConfig']['commSyslogClient']:
                if entry['name'] != 'secondary':
                    continue
                if entry['adminState'] == 'enabled' and entry['hostname'] == secondary:
                    sec_change = False

        if sec_change:
            try:
                update = __salt__['cimc.set_syslog_server'](secondary, "secondary")
                if update['outConfig']['commSyslogClient'][0]['status'] == 'modified':
                    req_change = True
                else:
                    ret['result'] = False
                    ret['comment'] = "Error setting secondary SYSLOG server."
                    return ret
            except Exception as err:
                ret['result'] = False
                ret['comment'] = "Error setting secondary SYSLOG server."
                log.error(err)
                return ret

    if req_change:
        ret['changes']['before'] = conf
        ret['changes']['after'] = __salt__['cimc.get_syslog']()
        ret['comment'] = "SYSLOG settings modified."
    else:
        ret['comment'] = "SYSLOG already configured. No changes required."

    ret['result'] = True

    return ret
