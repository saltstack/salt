# -*- coding: utf-8 -*-
r'''
Return salt data to Zabbix with keys of the form `salt.return.<fun>`

Missing items will be ignored.
The value will be either OK or FAILED, followed by the formatted return data:

.. code-block

    salt.return.test.ping: OK True

To use the Zabbix returner, append '--return zabbix' to the salt command:

.. code-block:: bash

    salt '*' test.ping --return zabbix

An example Zabbix template:

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8"?>
    <zabbix_export>
      <version>4.0</version>
      <date>2019-01-21T19:16:50Z</date>
      <groups><group><name>Templates/Applications</name></group></groups>
      <templates>
        <template>
          <template>Template App Saltstack</template>
          <name>Template App Saltstack</name>
          <description/>
          <groups><group><name>Templates/Applications</name></group></groups>
          <applications><application><name>Saltstack</name></application></applications>
          <items>
            <item>
              <name>Salt state.apply</name>
              <type>2</type>
              <snmp_community/>
              <snmp_oid/>
              <key>salt.return.state.apply</key>
              <delay>0</delay>
              <history>90d</history>
              <trends>0</trends>
              <status>0</status>
              <value_type>4</value_type>
              <allowed_hosts/>
              <units/>
              <snmpv3_contextname/>
              <snmpv3_securityname/>
              <snmpv3_securitylevel>0</snmpv3_securitylevel>
              <snmpv3_authprotocol>0</snmpv3_authprotocol>
              <snmpv3_authpassphrase/>
              <snmpv3_privprotocol>0</snmpv3_privprotocol>
              <snmpv3_privpassphrase/>
              <params/>
              <ipmi_sensor/>
              <authtype>0</authtype>
              <username/>
              <password/>
              <publickey/>
              <privatekey/>
              <port/>
              <description/>
              <inventory_link>0</inventory_link>
              <applications><application><name>Saltstack</name></application></applications>
              <valuemap/>
              <logtimefmt/>
              <preprocessing/>
              <jmx_endpoint/>
              <timeout>3s</timeout>
              <url/>
              <query_fields/>
              <posts/>
              <status_codes>200</status_codes>
              <follow_redirects>1</follow_redirects>
              <post_type>0</post_type>
              <http_proxy/>
              <headers/>
              <retrieve_mode>0</retrieve_mode>
              <request_method>0</request_method>
              <output_format>0</output_format>
              <allow_traps>0</allow_traps>
              <ssl_cert_file/>
              <ssl_key_file/>
              <ssl_key_password/>
              <verify_peer>0</verify_peer>
              <verify_host>0</verify_host>
              <master_item/>
            </item>
            <item>
              <name>Salt test.ping</name>
              <type>2</type>
              <snmp_community/>
              <snmp_oid/>
              <key>salt.return.test.ping</key>
              <delay>0</delay>
              <history>90d</history>
              <trends>0</trends>
              <status>0</status>
              <value_type>4</value_type>
              <allowed_hosts/>
              <units/>
              <snmpv3_contextname/>
              <snmpv3_securityname/>
              <snmpv3_securitylevel>0</snmpv3_securitylevel>
              <snmpv3_authprotocol>0</snmpv3_authprotocol>
              <snmpv3_authpassphrase/>
              <snmpv3_privprotocol>0</snmpv3_privprotocol>
              <snmpv3_privpassphrase/>
              <params/>
              <ipmi_sensor/>
              <authtype>0</authtype>
              <username/>
              <password/>
              <publickey/>
              <privatekey/>
              <port/>
              <description/>
              <inventory_link>0</inventory_link>
              <applications><application><name>Saltstack</name></application></applications>
              <valuemap/>
              <logtimefmt/>
              <preprocessing/>
              <jmx_endpoint/>
              <timeout>3s</timeout>
              <url/>
              <query_fields/>
              <posts/>
              <status_codes>200</status_codes>
              <follow_redirects>1</follow_redirects>
              <post_type>0</post_type>
              <http_proxy/>
              <headers/>
              <retrieve_mode>0</retrieve_mode>
              <request_method>0</request_method>
              <output_format>0</output_format>
              <allow_traps>0</allow_traps>
              <ssl_cert_file/>
              <ssl_key_file/>
              <ssl_key_password/>
              <verify_peer>0</verify_peer>
              <verify_host>0</verify_host>
              <master_item/>
            </item>
          </items>
          <discovery_rules/>
          <httptests/>
          <macros/>
          <templates/>
          <screens/>
        </template>
      </templates>
      <triggers>
        <trigger>
          <expression>{Template App Saltstack:salt.return.test.ping.str(True)}=0</expression>
          <recovery_mode>0</recovery_mode>
          <recovery_expression/>
          <name>Salt ping failed</name>
          <correlation_mode>0</correlation_mode>
          <correlation_tag/>
          <url/>
          <status>0</status>
          <priority>2</priority>
          <description/>
          <type>0</type>
          <manual_close>0</manual_close>
          <dependencies/>
          <tags/>
        </trigger>
        <trigger>
          <expression>{Template App Saltstack:salt.return.state.apply.regexp(Failed:\s*0)}=0</expression>
          <recovery_mode>0</recovery_mode>
          <recovery_expression/>
          <name>Salt state failed</name>
          <correlation_mode>0</correlation_mode>
          <correlation_tag/>
          <url/>
          <status>0</status>
          <priority>4</priority>
          <description/>
          <type>1</type>
          <manual_close>1</manual_close>
          <dependencies/>
          <tags/>
        </trigger>
      </triggers>
    </zabbix_export>

'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import shlex

# Import Salt libs
import salt.output
from salt.exceptions import CommandExecutionError

# Define the module's virtual name
__virtualname__ = 'zabbix'


def __virtual__():
    if zbx():
        return True
    return False, 'Zabbix returner: No zabbix_sender and zabbix_agend.conf found.'


def zbx():
    if os.path.exists('/usr/local/zabbix/bin/zabbix_sender') and os.path.exists('/usr/local/zabbix/etc/zabbix_agentd.conf'):
        zabbix_sender = '/usr/local/zabbix/bin/zabbix_sender'
        zabbix_config = '/usr/local/zabbix/etc/zabbix_agentd.conf'
        return {"sender": zabbix_sender, "config": zabbix_config}
    elif os.path.exists('/usr/bin/zabbix_sender') and os.path.exists('/etc/zabbix/zabbix_agentd.conf'):
        zabbix_sender = "/usr/bin/zabbix_sender"
        zabbix_config = "/etc/zabbix/zabbix_agentd.conf"
        return {"sender": zabbix_sender, "config": zabbix_config}
    else:
        return False


def zabbix_send(key, value):
    cmd = '{} -c {} -k {} -o {}'.format(
        zbx()['sender'], zbx()['config'],
        shlex.quote(key), shlex.quote(value))

    retcode = __salt__['cmd.retcode'](cmd, ignore_retcode=True)
    if retcode == 1:
        msg = 'Command \'{}\' failed with return code: {}'.format(cmd, retcode)
        raise CommandExecutionError(msg)


def returner(ret):
    if ret['fun'].split('.')[0] == 'state':
        out = 'highstate'
        data = {ret['id']: ret['return']}
    else:
        out = 'nested'
        data = ret['return']

    opts = __opts__.copy()
    opts['color'] = False

    key = 'salt.return.{}'.format(ret['fun'])
    value = salt.output.try_printout(data, ret.get('out', out), opts)
    zabbix_send(key, value)
