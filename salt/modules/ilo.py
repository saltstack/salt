# -*- coding: utf-8 -*-
'''
Manage HP ILO

:depends: hponcfg (SmartStart Scripting Toolkit Linux Edition)
'''
from __future__ import absolute_import

from salt._compat import ElementTree as ET
import salt.utils
import os
import tempfile

import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Make sure hponcfg tool is accessible
    '''
    if salt.utils.which('hponcfg'):
        return True

    return False


def __execute_cmd(name, xml):
    '''
    Execute ilom commands
    '''
    ret = {name.replace('_', ' '): {}}
    id_num = 0

    tmp_dir = os.path.join(__opts__['cachedir'], 'tmp')
    if not os.path.isdir(tmp_dir):
        os.mkdir(tmp_dir)
    with tempfile.NamedTemporaryFile(dir=tmp_dir,
                                     prefix=name+str(os.getpid()),
                                     suffix='.xml',
                                     delete=False) as fh:
        tmpfilename = fh.name
        fh.write(xml)

    cmd = __salt__['cmd.run_all']('hponcfg -f {0}'.format(tmpfilename))

    # Clean up the temp file
    __salt__['file.remove'](tmpfilename)

    if cmd['retcode'] != 0:
        for i in cmd['stderr'].splitlines():
            if i.startswith('     MESSAGE='):
                return {'Failed': i.split('=')[-1]}
        return False

    try:
        for i in ET.fromstring(''.join(cmd['stdout'].splitlines()[3:-1])):
            # Make sure dict keys don't collide
            if ret[name.replace('_', ' ')].get(i.tag, False):
                ret[name.replace('_', ' ')].update(
                    {i.tag + '_' + str(id_num): i.attrib}
                )
                id_num += 1
            else:
                ret[name.replace('_', ' ')].update(
                    {i.tag: i.attrib}
                )
    except SyntaxError:
        return True

    return ret


def global_settings():
    '''
    Show global settings

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.global_settings
    '''
    _xml = """<!-- Sample file for Get Global command -->
              <RIBCL VERSION="2.0">
                 <LOGIN USER_LOGIN="x" PASSWORD="x">
                   <RIB_INFO MODE="read">
                     <GET_GLOBAL_SETTINGS />
                   </RIB_INFO>
                 </LOGIN>
               </RIBCL>"""

    return __execute_cmd('Global_Settings', _xml)


def set_http_port(port=80):
    '''
    Configure the port HTTP should listen on

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.set_http_port 8080
    '''
    _current = global_settings()

    if _current['Global Settings']['HTTP_PORT']['VALUE'] == port:
        return True

    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="adminname" PASSWORD="password">
                  <RIB_INFO MODE="write">
                    <MOD_GLOBAL_SETTINGS>
                      <HTTP_PORT value="{0}"/>
                    </MOD_GLOBAL_SETTINGS>
                  </RIB_INFO>
                </LOGIN>
              </RIBCL>""".format(port)

    return __execute_cmd('Set_HTTP_Port', _xml)


def set_https_port(port=443):
    '''
    Configure the port HTTPS should listen on

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.set_https_port 4334
    '''
    _current = global_settings()

    if _current['Global Settings']['HTTP_PORT']['VALUE'] == port:
        return True

    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="adminname" PASSWORD="password">
                  <RIB_INFO MODE="write">
                    <MOD_GLOBAL_SETTINGS>
                      <HTTPS_PORT value="{0}"/>
                    </MOD_GLOBAL_SETTINGS>
                  </RIB_INFO>
                </LOGIN>
              </RIBCL>""".format(port)

    return __execute_cmd('Set_HTTPS_Port', _xml)


def enable_ssh():
    '''
    Enable the SSH daemon

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.enable_ssh
    '''
    _current = global_settings()

    if _current['Global Settings']['SSH_STATUS']['VALUE'] == 'Y':
        return True

    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="adminname" PASSWORD="password">
                  <RIB_INFO MODE="write">
                    <MOD_GLOBAL_SETTINGS>
                      <SSH_STATUS value="Yes"/>
                    </MOD_GLOBAL_SETTINGS>
                  </RIB_INFO>
                </LOGIN>
              </RIBCL>"""

    return __execute_cmd('Enable_SSH', _xml)


def disable_ssh():
    '''
    Disable the SSH daemon

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.disable_ssh
    '''
    _current = global_settings()

    if _current['Global Settings']['SSH_STATUS']['VALUE'] == 'N':
        return True

    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="adminname" PASSWORD="password">
                  <RIB_INFO MODE="write">
                    <MOD_GLOBAL_SETTINGS>
                      <SSH_STATUS value="No"/>
                    </MOD_GLOBAL_SETTINGS>
                  </RIB_INFO>
                </LOGIN>
              </RIBCL>"""

    return __execute_cmd('Disable_SSH', _xml)


def set_ssh_port(port=22):
    '''
    Enable SSH on a user defined port

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.set_ssh_port 2222
    '''
    _current = global_settings()

    if _current['Global Settings']['SSH_PORT']['VALUE'] == port:
        return True

    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="adminname" PASSWORD="password">
                  <RIB_INFO MODE="write">
                    <MOD_GLOBAL_SETTINGS>
                       <SSH_PORT value="{0}"/>
                    </MOD_GLOBAL_SETTINGS>
                  </RIB_INFO>
                </LOGIN>
              </RIBCL>""".format(port)

    return __execute_cmd('Configure_SSH_Port', _xml)


def set_ssh_key(public_key):
    '''
    Configure SSH public keys for specific users

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.set_ssh_key "ssh-dss AAAAB3NzaC1kc3MAAACBA... damian"

    The SSH public key needs to be DSA and the last argument in the key needs
    to be the username (case-senstive) of the ILO username.
    '''
    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="adminname" PASSWORD="password">
                  <RIB_INFO MODE="write">
                    <IMPORT_SSH_KEY>
                      -----BEGIN SSH KEY-----
                      {0}
                      -----END SSH KEY-----
                    </IMPORT_SSH_KEY>
                  </RIB_INFO>
                </LOGIN>
              </RIBCL>""".format(public_key)

    return __execute_cmd('Import_SSH_Publickey', _xml)


def delete_ssh_key(username):
    '''
    Delete a users SSH key from the ILO

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.delete_user_sshkey damian
    '''
    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="admin" PASSWORD="admin123">
                  <USER_INFO MODE="write">
                    <MOD_USER USER_LOGIN="{0}">
                      <DEL_USERS_SSH_KEY/>
                    </MOD_USER>
                  </USER_INFO>
                </LOGIN>
              </RIBCL>""".format(username)

    return __execute_cmd('Delete_user_SSH_key', _xml)


def list_users():
    '''
    List all users

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.list_users
    '''
    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="x" PASSWORD="x">
                    <USER_INFO MODE="read">
                      <GET_ALL_USERS />
                    </USER_INFO>
                </LOGIN>
              </RIBCL>"""

    return __execute_cmd('All_users', _xml)


def list_users_info():
    '''
    List all users in detail

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.list_users_info
    '''
    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="adminname" PASSWORD="password">
                  <USER_INFO MODE="read">
                    <GET_ALL_USER_INFO />
                  </USER_INFO>
                </LOGIN>
              </RIBCL>"""

    return __execute_cmd('All_users_info', _xml)


def create_user(name, password, *privileges):
    '''
    Create user

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.create_user damian secretagent VIRTUAL_MEDIA_PRIV

    If no permissions are specify the user will only have a read-only account.

    Supported privelges:

    * ADMIN_PRIV
      Enables the user to administer user accounts.

    * REMOTE_CONS_PRIV
      Enables the user to access the Remote Console functionality.

    * RESET_SERVER_PRIV
      Enables the user to remotely manipulate the server power setting.

    * VIRTUAL_MEDIA_PRIV
      Enables the user permission to access the virtual media functionality.

    * CONFIG_ILO_PRIV
      Enables the user to configure iLO settings.
    '''
    _priv = ['ADMIN_PRIV',
             'REMOTE_CONS_PRIV',
             'RESET_SERVER_PRIV',
             'VIRTUAL_MEDIA_PRIV',
             'CONFIG_ILO_PRIV']

    _xml = """<RIBCL version="2.2">
                <LOGIN USER_LOGIN="x" PASSWORD="y">
                  <RIB_INFO mode="write">
                    <MOD_GLOBAL_SETTINGS>
                      <MIN_PASSWORD VALUE="7"/>
                    </MOD_GLOBAL_SETTINGS>
                  </RIB_INFO>

                 <USER_INFO MODE="write">
                   <ADD_USER USER_NAME="{0}" USER_LOGIN="{0}" PASSWORD="{1}">
                     {2}
                   </ADD_USER>
                 </USER_INFO>
               </LOGIN>
             </RIBCL>""".format(name, password, '\n'.join(['<{0} value="Y" />'.format(i.upper()) for i in privileges if i.upper() in _priv]))

    return __execute_cmd('Create_user', _xml)


def delete_user(username):
    '''
    Delete a user

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.delete_user damian
    '''
    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="adminname" PASSWORD="password">
                  <USER_INFO MODE="write">
                    <DELETE_USER USER_LOGIN="{0}" />
                  </USER_INFO>
                </LOGIN>
              </RIBCL>""".format(username)

    return __execute_cmd('Delete_user', _xml)


def get_user(username):
    '''
    Returns local user information, excluding the password

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.get_user damian
    '''
    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="adminname" PASSWORD="password">
                  <USER_INFO MODE="read">
                    <GET_USER USER_LOGIN="{0}" />
                  </USER_INFO>
                </LOGIN>
              </RIBCL>""".format(username)

    return __execute_cmd('User_Info', _xml)


def change_username(old_username, new_username):
    '''
    Change a username

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.change_username damian diana
    '''
    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="adminname" PASSWORD="password">
                  <USER_INFO MODE="write">
                    <MOD_USER USER_LOGIN="{0}">
                      <USER_NAME value="{1}"/>
                      <USER_LOGIN value="{1}"/>
                    </MOD_USER>
                  </USER_INFO>
                </LOGIN>
              </RIBCL>""".format(old_username, new_username)

    return __execute_cmd('Change_username', _xml)


def change_password(username, password):
    '''
    Reset a users password

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.change_password damianMyerscough
    '''
    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="adminname" PASSWORD="password">
                  <USER_INFO MODE="write">
                    <MOD_USER USER_LOGIN="{0}">
                      <PASSWORD value="{1}"/>
                    </MOD_USER>
                  </USER_INFO>
                </LOGIN>
              </RIBCL>""".format(username, password)

    return __execute_cmd('Change_password', _xml)


def network():
    '''
    Grab the current network settings

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.network
    '''
    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="adminname" PASSWORD="password">
                  <RIB_INFO MODE="read">
                    <GET_NETWORK_SETTINGS/>
                  </RIB_INFO>
                </LOGIN>
              </RIBCL>"""

    return __execute_cmd('Network_Settings', _xml)


def configure_network(ip, netmask, gateway):
    '''
    Configure Network Interface

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.configure_network [IP ADDRESS] [NETMASK] [GATEWAY]
    '''
    current = network()

    # Check to see if the network is already configured
    if (ip in current['Network Settings']['IP_ADDRESS']['VALUE'] and
            netmask in current['Network Settings']['SUBNET_MASK']['VALUE'] and
            gateway in current['Network Settings']['GATEWAY_IP_ADDRESS']['VALUE']):
        return True

    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="adminname" PASSWORD="password">
                  <RIB_INFO MODE="write">
                    <MOD_NETWORK_SETTINGS>
                      <IP_ADDRESS value="{0}"/>
                      <SUBNET_MASK value="{1}"/>
                      <GATEWAY_IP_ADDRESS value="{2}"/>
                    </MOD_NETWORK_SETTINGS>
                  </RIB_INFO>
                </LOGIN>
              </RIBCL> """.format(ip, netmask, gateway)

    return __execute_cmd('Configure_Network', _xml)


def enable_dhcp():
    '''
    Enable DHCP

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.enable_dhcp
    '''
    current = network()

    if current['Network Settings']['DHCP_ENABLE']['VALUE'] == 'Y':
        return True

    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="adminname" PASSWORD="password">
                  <RIB_INFO MODE="write">
                    <MOD_NETWORK_SETTINGS>
                      <DHCP_ENABLE value="Yes"/>
                    </MOD_NETWORK_SETTINGS>
                  </RIB_INFO>
                </LOGIN>
              </RIBCL>"""

    return __execute_cmd('Enable_DHCP', _xml)


def disable_dhcp():
    '''
    Disable DHCP

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.disable_dhcp
    '''
    current = network()

    if current['Network Settings']['DHCP_ENABLE']['VALUE'] == 'N':
        return True

    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="adminname" PASSWORD="password">
                  <RIB_INFO MODE="write">
                    <MOD_NETWORK_SETTINGS>
                      <DHCP_ENABLE value="No"/>
                    </MOD_NETWORK_SETTINGS>
                  </RIB_INFO>
                </LOGIN>
              </RIBCL>"""

    return __execute_cmd('Disable_DHCP', _xml)


def configure_snmp(community, snmp_port=161, snmp_trapport=161):
    '''
    Configure SNMP

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.configure_snmp [COMMUNITY STRING] [SNMP PORT] [SNMP TRAP PORT]
    '''
    _xml = """<RIBCL VERSION="2.2">
                <LOGIN USER_LOGIN="x" PASSWORD="y">
                  <RIB_INFO mode="write">
                    <MOD_GLOBAL_SETTINGS>
                      <SNMP_ACCESS_ENABLED VALUE="Yes"/>
                      <SNMP_PORT VALUE="{0}"/>
                      <SNMP_TRAP_PORT VALUE="{1}"/>
                    </MOD_GLOBAL_SETTINGS>

                   <MOD_SNMP_IM_SETTINGS>
                     <SNMP_ADDRESS_1 VALUE=""/>
                     <SNMP_ADDRESS_1_ROCOMMUNITY VALUE="{2}"/>
                     <SNMP_ADDRESS_1_TRAPCOMMUNITY VERSION="" VALUE=""/>
                     <RIB_TRAPS VALUE="Y"/>
                     <OS_TRAPS VALUE="Y"/>
                     <SNMP_PASSTHROUGH_STATUS VALUE="N"/>
                  </MOD_SNMP_IM_SETTINGS>
                </RIB_INFO>
              </LOGIN>
           </RIBCL>""".format(snmp_port, snmp_trapport, community)

    return __execute_cmd('Configure_SNMP', _xml)
