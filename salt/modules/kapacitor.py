# -*- coding: utf-8 -*-
'''
Kapacitor execution module.

:configuration: This module accepts connection configuration details either as
    parameters or as configuration settings in /etc/salt/minion on the relevant
    minions::

        kapacitor.host: 'localhost'
        kapacitor.port: 9092

    This data can also be passed into pillar. Options passed into opts will
    overwrite options passed into pillar.

.. versionadded:: Carbon
'''

from __future__ import absolute_import

import json
import logging

import salt.utils
import salt.utils.http

LOG = logging.getLogger(__name__)


def __virtual__():
    return 'kapacitor' if salt.utils.which('kapacitor') else False


def get_task(name):
    '''
    Get a dict of data on a task.

    name
        Name of the task to get information about.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.get_task cpu
    '''
    host = __salt__['config.option']('kapacitor.host', 'localhost')
    port = __salt__['config.option']('kapacitor.port', 9092)
    url = 'http://{0}:{1}/task?name={2}'.format(host, port, name)
    response = salt.utils.http.query(url, status=True)

    if response['status'] == 404:
        return None

    data = json.loads(response['body'])

    return data


def _run_cmd(cmd):
    '''
    Run a Kapacitor task and return a dictionary of info.
    '''
    ret = {}
    result = __salt__['cmd.run_all'](cmd)

    if result.get('stdout'):
        ret['stdout'] = result['stdout']
    if result.get('stderr'):
        ret['stderr'] = result['stderr']
    ret['success'] = result['retcode'] == 0

    return ret


def define_task(name,
                tick_script,
                task_type='stream',
                database=None,
                retention_policy='default'):
    '''
    Define a task. Serves as both create/update.

    name
        Name of the task.

    tick_script
        Path to the TICK script for the task. Can be a salt:// source.

    task_type
        Task type. Defaults to 'stream'

    database
        Which database to fetch data from. Defaults to None, which will use the
        default database in InfluxDB.

    retention_policy
        Which retention policy to fetch data from. Defaults to 'default'.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.define_task cpu salt://kapacitor/cpu.tick database=telegraf
    '''
    cmd = 'kapacitor define -name {0} -tick {1}'.format(name, tick_script)

    if tick_script.startswith('salt://'):
        tick_script = __salt__['cp.cache_file'](tick_script, __env__)

    if task_type:
        cmd += ' -type {0}'.format(task_type)

    if database and retention_policy:
        cmd += ' -dbrp {0}.{1}'.format(database, retention_policy)

    return _run_cmd(cmd)


def delete_task(name):
    '''
    Delete a kapacitor task.

    name
        Name of the task to delete.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.delete_task cpu
    '''
    return _run_cmd('kapacitor delete tasks {0}'.format(name))


def enable_task(name):
    '''
    Enable a kapacitor task.

    name
        Name of the task to enable.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.enable_task cpu
    '''
    return _run_cmd('kapacitor enable {0}'.format(name))


def disable_task(name):
    '''
    Disable a kapacitor task.

    name
        Name of the task to disable.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.disable_task cpu
    '''
    return _run_cmd('kapacitor disable {0}'.format(name))
