# -*- coding: utf-8 -*-
'''
Apache Traffic Server execution module.

.. versionadded:: 2015.8.0

``traffic_line`` is used to execute individual Traffic Server commands and to
script multiple commands in a shell.
'''
from __future__ import absolute_import

# Import python libs
import logging
import subprocess

# Import salt libs
from salt import utils

__virtualname__ = 'trafficserver'

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__ if utils.which('traffic_line') else False


_TRAFFICLINE = utils.which('traffic_line')


def _subprocess(cmd):
    '''
    Function to standardize the subprocess call
    '''

    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        ret = utils.to_str(proc.communicate()[0]).strip()
        retcode = proc.wait()

        if ret:
            return ret
        elif retcode != 1:
            return True
        else:
            return False
    except OSError as err:
        log.error(err)
        return False


def bounce_cluster():
    '''
    Bounce all Traffic Server nodes in the cluster. Bouncing Traffic Server
    shuts down and immediately restarts Traffic Server, node-by-node.

    .. code-block:: bash

        salt '*' trafficserver.bounce_cluster
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '-B')
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def bounce_local(drain=False):
    '''
    Bounce Traffic Server on the local node. Bouncing Traffic Server shuts down
    and immediately restarts the Traffic Server node.

    This option modifies the behavior of traffic_line -b and traffic_line -L
    such that traffic_server is not shut down until the number of active client
    connections drops to the number given by the
    proxy.config.restart.active_client_threshold configuration variable.

    .. code-block:: bash

        salt '*' trafficserver.bounce_local
        salt '*' trafficserver.bounce_local drain=True
    '''
    if drain:
        cmd = '{0} {1} {2}'.format(_TRAFFICLINE, '-b', '--drain')
    else:
        cmd = '{0} {1}'.format(_TRAFFICLINE, '-b')
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def clear_cluster():
    '''
    Clears accumulated statistics on all nodes in the cluster.

    .. code-block:: bash

        salt '*' trafficserver.clear_cluster
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '-C')
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def clear_node():
    '''
    Clears accumulated statistics on the local node.

    .. code-block:: bash

        salt '*' trafficserver.clear_node
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '-c')
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def restart_cluster():
    '''
    Restart the traffic_manager process and the traffic_server process on all
    the nodes in a cluster.

    .. code-block:: bash

        salt '*' trafficserver.restart_cluster
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '-M')
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def restart_local(drain=False):
    '''
    Restart the traffic_manager and traffic_server processes on the local node.

    This option modifies the behavior of traffic_line -b and traffic_line -L
    such that traffic_server is not shut down until the number of active client
    connections drops to the number given by the
    proxy.config.restart.active_client_threshold configuration variable.

    .. code-block:: bash

        salt '*' trafficserver.restart_local
        salt '*' trafficserver.restart_local drain=True
    '''
    if drain:
        cmd = '{0} {1} {2}'.format(_TRAFFICLINE, '-L', '--drain')
    else:
        cmd = '{0} {1}'.format(_TRAFFICLINE, '-L')
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def match_var(regex):
    '''
    Display the current values of all performance statistics or configuration
    variables whose names match the given regular expression.

    .. code-block:: bash

        salt '*' trafficserver.match_var regex
    '''
    cmd = '{0} {1} {2}'.format(_TRAFFICLINE, '-m', regex)
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def read_var(*args):
    '''
    Read variable definitions from the traffic_line command

    This allows reading arbitrary key=value pairs from within trafficserver

    .. code-block:: bash

        salt '*' trafficserver.read_var proxy.process.http.tcp_hit_count_stat
    '''

    ret = {}

    try:
        for arg in args:
            log.debug('Querying: %s', arg)
            cmd = '{0} {1} {2}'.format(_TRAFFICLINE, '-r', arg)
            ret[arg] = _subprocess(cmd)
    except KeyError:
        pass

    return ret


def set_var(variable, value):
    '''
    .. code-block:: bash

        salt '*' trafficserver.set_var proxy.config.http.server_ports
    '''

    cmd = '{0} {1} {2} {3} {4}'.format(_TRAFFICLINE, '-s', variable, '-v', value)
    log.debug('Setting %s to %s', variable, value)
    return _subprocess(cmd)


def shutdown():
    '''
    Shut down Traffic Server on the local node.

    .. code-block:: bash

        salt '*' trafficserver.shutdown
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '-S')
    status_cmd = '{0} {1}'.format(_TRAFFICLINE, '--status')
    log.debug('Running: %s', cmd)
    _subprocess(cmd)
    return _subprocess(status_cmd)


def startup():
    '''
    Start Traffic Server on the local node.

    .. code-block:: bash

        salt '*' trafficserver.start
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '-U')
    status_cmd = '{0} {1}'.format(_TRAFFICLINE, '--status')
    log.debug('Running: %s', cmd)
    _subprocess(cmd)
    return _subprocess(status_cmd)


def refresh():
    '''
    Initiate a Traffic Server configuration file reread. Use this command to
    update the running configuration after any configuration file modification.

    The timestamp of the last reconfiguration event (in seconds since epoch) is
    published in the proxy.node.config.reconfigure_time metric.

    .. code-block:: bash

        salt '*' trafficserver.refresh
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '-x')
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def zero_cluster():
    '''
    Reset performance statistics to zero across the cluster.

    .. code-block:: bash

        salt '*' trafficserver.zero_cluster
    '''
    cmd = '{0} {1}'.format(_TRAFFICLINE, '-Z')
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def zero_node():
    '''
    Reset performance statistics to zero on the local node.

    .. code-block:: bash

        salt '*' trafficserver.zero_cluster
    '''
    cmd = '{0} {1}'.format(_TRAFFICLINE, '-z')
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def offline(path):
    '''
    Mark a cache storage device as offline. The storage is identified by a path
    which must match exactly a path specified in storage.config. This removes
    the storage from the cache and redirects requests that would have used this
    storage to other storage. This has exactly the same effect as a disk
    failure for that storage. This does not persist across restarts of the
    traffic_server process.

    .. code-block:: bash

        salt '*' trafficserver.offline /path/to/cache
    '''

    cmd = '{0} {1} {2}'.format(_TRAFFICLINE, '--offline', path)
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def alarms():
    '''
    List all alarm events that have not been acknowledged (cleared).

    .. code-block:: bash

        salt '*' trafficserver.alarms
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '--alarms')
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def clear_alarms(alarm):
    '''
    Clear (acknowledge) an alarm event. The arguments are “all” for all current
    alarms, a specific alarm number (e.g. ‘‘1’‘), or an alarm string identifier
    (e.g. ‘’MGMT_ALARM_PROXY_CONFIG_ERROR’‘).

    .. code-block:: bash

        salt '*' trafficserver.clear_alarms [all | #event | name]
    '''

    cmd = '{0} {1} {2}'.format(_TRAFFICLINE, '--clear_alarms', alarm)
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def status():
    '''
    Show the current proxy server status, indicating if we’re running or not.

    .. code-block:: bash

        salt '*' trafficserver.status
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '--status')
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)
