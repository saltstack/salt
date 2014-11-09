# -*- coding: utf-8 -*-
'''
Manage HP ILOM
'''

import xml.etree.cElementTree as ET
import salt.utils
import os

import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''

    '''
    if salt.utils.which('hponcfg'):
        return True

    return False


def __execute_cmd(name, xml):
    '''
    Execute ilom commands
    '''
    ret = {name.replace('_', ' '): {}}
    id = 0

    with salt.utils.fopen('/tmp/{0}.{1}'.format(name, os.getpid()), 'w') as fh:
        fh.write(xml)

    cmd = __salt__['cmd.run_all']('hponcfg -f /tmp/{0}.{1}'.format(name, os.getpid()))

    # Clean up the temp file
    __salt__['file.remove']('/tmp/{0}.{1}'.format(name, os.getpid()))

    if cmd['retcode'] != 0:
        for i in cmd['stderr'].splitlines():
            if i.startswith('     MESSAGE='):
                return {'Failed': i.split('=')[-1]}
        return False

    if len(cmd['stdout'].splitlines()) == 4:
        return True

    for i in ET.fromstring(''.join(cmd['stdout'].splitlines()[3:-1])):
        ret[name.replace('_', ' ')].update({i.tag + '_' + str(id): i.attrib})
        id += 1

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


def all_users():
    '''
    List all users

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.all_users
    '''
    _xml = """<RIBCL VERSION="2.0">
                <LOGIN USER_LOGIN="x" PASSWORD="x">
                    <USER_INFO MODE="read">
                      <GET_ALL_USERS />
                    </USER_INFO>
                </LOGIN>
              </RIBCL>"""

    return __execute_cmd('All_users', _xml)


def all_users_info():
    '''
    List all users in detail

    CLI Example:

    .. code-block:: bash

        salt '*' ilo.all_users_info
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

        salt '*' ilo.create_user damian secret

    Privelges:

    * ADMIN_PRIV - Enables the user to administer user accounts.
    * REMOTE_CONS_PRIV - Enables the user to access the Remote Console functionality.
    * RESET_SERVER_PRIV - Enables the user to remotely manipulate the server power setting.
    * VIRTUAL_MEDIA_PRIV - Enables the user permission to access the virtual media functionality.
    * CONFIG_ILO_PRIV - Enables the user to configure iLO settings.
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
