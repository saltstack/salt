# -*- coding: utf-8 -*-
'''
Support for hadoop

:maintainer: Yann Jouanin <yann.jouanin@intelunix.fr>
:maturity: new
:depends:
:platform: linux


'''
from __future__ import absolute_import

# Import salt libs
import salt.utils

__authorized_modules__ = ['namenode', 'dfsadmin', 'dfs', 'fs']


def __virtual__():
    '''
    Check if hadoop is present, then load the module
    '''
    if salt.utils.which('hadoop'):
        return 'hadoop'
    return False


def version():
    '''
    Return version from hadoop version

    CLI Example:

    .. code-block:: bash

        salt '*' hadoop.version
    '''
    cmd = 'hadoop version'
    out = __salt__['cmd.run'](cmd).split()
    return out[1]


def _hadoop_cmd(module, command, *args):
    '''
       Hadoop command wrapper

       In order to prevent random execution the module name is checked

       Follows hadoop command template:
          hadoop module -command args
       E.g.: hadoop dfs -ls /
    '''
    out = None
    if module and command:
        if module in __authorized_modules__:
            cmd = 'hadoop {0} -{1} {2}'.format(module, command, ' '.join(args))
            out = __salt__['cmd.run'](cmd, python_shell=False)
        else:
            return 'Error: Unknown module'
    else:
        return 'Error: Module and command not defined'
    return out


def dfs(command=None, *args):
    '''
    Execute a command on DFS

    CLI Example:

    .. code-block:: bash

        salt '*' hadoop.dfs ls /
    '''
    if command:
        return _hadoop_cmd('dfs', command, *args)
    else:
        return 'Error: command must be provided'


def dfs_present(path):
    '''
    Check if a file or directory is present on the distributed FS.

    CLI Example:

    .. code-block:: bash

        salt '*' hadoop.dfs_present /some_random_file


    Returns True if the file is present
    '''

    cmd_return = _hadoop_cmd('dfs', 'stat', path)
    if 'No such file or directory' in cmd_return:
        return False
    else:
        return True


def dfs_absent(path):
    '''
    Check if a file or directory is absent on the distributed FS.

    CLI Example:

    .. code-block:: bash

        salt '*' hadoop.dfs_absent /some_random_file

    Returns True if the file is absent
    '''

    cmd_return = _hadoop_cmd('dfs', 'stat', path)
    if 'No such file or directory' in cmd_return:
        return True
    else:
        return False


def namenode_format(force=None):
    '''
    Format a name node

    .. code-block:: bash

        salt '*' hadoop.namenode_format force=True
    '''
    force_param = ''
    if force:
        force_param = '-force'

    return _hadoop_cmd('namenode', 'format', '-nonInteractive', force_param)
