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

__authorized_modules__ = ['version', 'namenode', 'dfsadmin', 'dfs', 'fs']


def __virtual__():
    '''
    Check if hadoop is present, then load the module
    '''
    if salt.utils.which('hadoop') or salt.utils.which('hdfs'):
        return 'hadoop'
    return (False, 'The hadoop execution module cannot be loaded: hadoop binary not in path.')


def _hadoop_cmd(module, command, *args):
    '''
       Hadoop/hdfs command wrapper

       As Hadoop command has been deprecated this module will default
       to use hdfs command and fall back to hadoop if it is not found

       In order to prevent random execution the module name is checked

       Follows hadoop command template:
          hadoop module -command args
       E.g.: hadoop dfs -ls /
    '''
    tool = 'hadoop'
    if salt.utils.which('hdfs'):
        tool = 'hdfs'

    out = None
    if module and command:
        if module in __authorized_modules__:
            mappings = {'tool': tool, 'module': module, 'command': command, 'args': ' '.join(args)}
            cmd = '{tool} {module} -{command} {args}'.format(**mappings)
            out = __salt__['cmd.run'](cmd, python_shell=False)
        else:
            return 'Error: Unknown module'
    else:
        return 'Error: Module and command not defined'
    return out


def version():
    '''
    Return version from hadoop version

    CLI Example:

    .. code-block:: bash

        salt '*' hadoop.version
    '''
    module = 'version'
    out = _hadoop_cmd(module, True).splitlines()[0].split()
    return out[1]


def dfs(command=None, *args):
    '''
    Execute a command on DFS

    trailing argument of use_hdfs will use hdfs command for execution

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
    match = 'No such file or directory'
    return False if match in cmd_return else True


def dfs_absent(path):
    '''
    Check if a file or directory is absent on the distributed FS.

    optional argument of use_hdfs=True will use hdfs command for execution

    CLI Example:

    .. code-block:: bash

        salt '*' hadoop.dfs_absent /some_random_file

    Returns True if the file is absent
    '''
    cmd_return = _hadoop_cmd('dfs', 'stat', path)
    match = 'No such file or directory'
    return True if match in cmd_return else False


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
