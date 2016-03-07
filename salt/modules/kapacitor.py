import json
import logging

import logging

from salt.utils import http, which

LOG = logging.getLogger(__name__)


def __virtual__():
    return 'kapacitor' if which('kapacitor') else False


def get_task(name):
    '''
    Get a dict of data on a task.

    name
        Name of the task to get information about.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.get_task cpu
    '''
    url = 'http://localhost:9092/task?name={}'.format(name)
    response = http.query(url)
    data = json.loads(response['body'])
    if 'Error' in data and data['Error'].startswith('unknown task'):
        return None
    return data


def define_task(name, tick_script, task_type='stream', database=None,
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
    cmd = 'kapacitor define -name {} -tick {}'.format(name, tick_script)

    if tick_script.startswith('salt://'):
        tick_script = __salt__['cp.cache_file'](tick_script, __env__)

    if task_type:
        cmd += ' -type {}'.format(task_type)

    if database and retention_policy:
        cmd += ' -dbrp {}.{}'.format(database, retention_policy)

    return __salt__['cmd.run_all'](cmd)


def delete_task(name):
    '''
    Delete a kapacitor task.

    name
        Name of the task to delete.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.delete_task cpu
    '''
    cmd = 'kapacitor delete -name {}'.format(name)
    return __salt__['cmd.run_all'](cmd)


def enable_task(name):
    '''
    Enable a kapacitor task.

    name
        Name of the task to enable.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.enable_task cpu
    '''
    cmd = 'kapacitor enable {}'.format(name)
    return __salt__['cmd.run_all'](cmd)


def disable_task(name):
    '''
    Disable a kapacitor task.

    name
        Name of the task to disable.

    CLI Example:

    .. code-block:: bash

        salt '*' kapacitor.disable_task cpu
    '''
    cmd = 'kapacitor disable {}'.format(name)
    return __salt__['cmd.run_all'](cmd)
