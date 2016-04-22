# -*- coding: utf-8 -*-
'''
State modules to interact with Junos devices.
==============================================

These modules call the corresponding execution modules.
Refer to :mod:`junos <salt.modules.junos>` for further information.
'''
from __future__ import absolute_import
import logging

log = logging.getLogger()


def call_rpc(name, args=None, **kwargs):
    '''
    Executes the given rpc. The returned data can be stored in a file
    by specifying the destination path with dest as an argument

    .. code-block:: yaml

            get config:
              junos:
        - call_rpc
                    - args:
          - <configuration><system/></configuration>
          - dest: /home/user/rpc_data.txt

name: the rpc to be executed.

args: other arguments as taken by rpc call of PyEZ

kwargs: keyworded arguments taken by rpc call of PyEZ
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
    if args is not None:
        ret['changes'] = __salt__['junos.call_rpc'](name, *args, **kwargs)
    else:
        ret['changes'] = __salt__['junos.call_rpc'](name, **kwargs)
    return ret


def set_hostname(name, commit_changes=True):
    '''
    Changes the hostname of the device.

    .. code-block:: yaml

            device name:
              junos:
                - set_hostname
                - commit_changes: False

name: the name to be given to the device

commit_changes: whether to commit the changes
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
    ret['changes'] = __salt__['junos.set_hostname'](name, commit_changes)
    return ret


def commit(name):
    '''
    Commits the changes loaded into the candidate configuration.

    .. code-block:: yaml

            commit the changes:
              junos.commit

    name: can be anything
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
    ret['changes'] = __salt__['junos.commit']()
    return ret


def rollback(name):
    '''
    Rollbacks the committed changes.
    .. code-block:: yaml

            rollback the changes:
              junos.rollback

    name: can be anything
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
    ret['changes'] = __salt__['junos.rollback']()
    return ret


def diff(name):
    '''
    Gets the difference between the candidate and the current configuration.

    .. code-block:: yaml

            get the diff:
              junos.diff

    name: can be anything
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
    ret['changes'] = __salt__['junos.diff']()
    return ret


def cli(name):
    '''
    Executes the CLI commands and reuturns the text output.

    .. code-block:: yaml

            show version:
              junos.cli

    name: the command to be executed on junos CLI.
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
    ret['changes'] = __salt__['junos.cli'](name)
    return ret


def shutdown(name, time=0):
    '''
    Shuts down the device.

    .. code-block:: yaml

            shut the device:
              junos:
                - shutdown
                - time: 10

    name: can be anything

    time: time after which the system should shutdown(in seconds, default=0)
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
    ret['changes'] = __salt__['junos.shutdown'](time)
    return ret


def install_config(name, **kwargs):
    '''
    Loads and commits the configuration provided.

    .. code-block:: yaml

            /home/user/config.set:
              junos:
                - install_config
                - timeout: 100

    name: path to the configuration file.

    keyworded arguments taken by load fucntion of PyEZ
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
    ret['changes'] = __salt__['junos.install_config'](name, **kwargs)
    return ret


def zeroize(name):
    '''
    Resets the device to default factory settings.

    .. code-block:: yaml

            reset my device:
              junos.zeroize

    name: can be anything
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
    ret['changes'] = __salt__['junos.zeroize']()
    return ret


def install_os(name, **kwargs):
    '''
    Installs the given image on the device. After the installation is complete
    the device is rebooted, if reboot=True is given as a keyworded argument.

    .. code-block:: yaml

            /home/user/junos_image.tgz:
              junos:
                - install_os
                - timeout: 100
                - reboot: True

    name: path to the image file.

    kwargs: keyworded arguments to be given such as timeout, reboot etc
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
    ret['changes'] = __salt__['junos.install_os'](name, **kwargs)
    return ret


def file_copy(name, dest=None):
    '''
    Copies the file from the local device to the junos device.

    .. code-block:: yaml

            /home/m2/info.txt:
              junos:
                - file_copy
                - dest: info_copy.txt

    name: source path of the file.

    dest: destination path where the file will be placed.
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
    ret['changes'] = __salt__['junos.file_copy'](name, dest)
    return ret
