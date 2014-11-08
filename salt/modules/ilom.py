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

    with salt.utils.fopen('/tmp/{0}.{1}'.format(name, os.getpid()), 'w') as fh:
        fh.write(xml)

    cmd = __salt__['cmd.run_all']('hponcfg -f /tmp/{0}.{1}'.format(name, os.getpid()))

    # Clean up the temp file
    __salt__['file.remove']('/tmp/{0}.{1}'.format(name, os.getpid()))

    if cmd['retcode'] != 0:
        log.warn('hponcfg return an exit code \'{0}\'.'.format(cmd['retcode']))
        return False

    for i in ET.fromstring(''.join(cmd['stdout'].splitlines()[3:-1])):
        ret[name.replace('_', ' ')].update({i.tag: i.attrib.get('VALUE', None)})

    return ret


def global_settings():
    '''

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
