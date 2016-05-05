# -*- coding: utf-8 -*-
'''
Apache Traffic Server execution module.

.. versionadded:: 2015.8.0

``traffic_ctl`` is used to execute individual Traffic Server commands and to
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
    if utils.which('traffic_ctl') or utils.which('traffic_line'):
        return __virtualname__
    return (False, 'trafficserver execution module not loaded: '
            'neither traffic_ctl nor traffic_line was found.')


_TRAFFICLINE = utils.which('traffic_line')
_TRAFFICCTL = utils.which('traffic_ctl')


def _traffic_ctl(*args):
    return ' '.join([_TRAFFICCTL] + args)


def _traffic_line(*args):
    return ' '.join([_TRAFFICLINE] + args)


def _statuscmd():
    if _TRAFFICCTL:
        cmd = _traffic_ctl('server', 'status')
    else:
        cmd = _traffic_line('--status')

    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


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

    if _TRAFFICCTL:
        cmd = _traffic_ctl('cluster', 'restart')
    else:
        cmd = _traffic_line('-B')
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def bounce_local(drain=False):
    '''
    Bounce Traffic Server on the local node. Bouncing Traffic Server shuts down
    and immediately restarts the Traffic Server node.

    drain
        This option modifies the restart behavior such that traffic_server
        is not shut down until the number of active client connections
        drops to the number given by the
        proxy.config.restart.active_client_threshold configuration
        variable.

    .. code-block:: bash

        salt '*' trafficserver.bounce_local
        salt '*' trafficserver.bounce_local drain=True
    '''
    if _TRAFFICCTL:
        cmd = _traffic_ctl('server', 'restart')
    else:
        cmd = _traffic_line('-b')

    if drain:
        cmd = '{0} {1}'.format(cmd, '--drain')

    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def clear_cluster():
    '''
    Clears accumulated statistics on all nodes in the cluster.

    .. code-block:: bash

        salt '*' trafficserver.clear_cluster
    '''

    if _TRAFFICCTL:
        cmd = _traffic_ctl('metric', 'clear', '--cluster')
    else:
        cmd = _traffic_line('-C')

    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def clear_node():
    '''
    Clears accumulated statistics on the local node.

    .. code-block:: bash

        salt '*' trafficserver.clear_node
    '''

    if _TRAFFICCTL:
        cmd = _traffic_ctl('metric', 'clear')
    else:
        cmd = _traffic_line('-c')

    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def restart_cluster():
    '''
    Restart the traffic_manager process and the traffic_server process on all
    the nodes in a cluster.

    .. code-block:: bash

        salt '*' trafficserver.restart_cluster
    '''

    if _TRAFFICCTL:
        cmd = _traffic_ctl('cluster', 'restart', '--manager')
    else:
        cmd = _traffic_line('-M')

    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def restart_local(drain=False):
    '''
    Restart the traffic_manager and traffic_server processes on the local node.

    drain
        This option modifies the restart behavior such that
        ``traffic_server`` is not shut down until the number of
        active client connections drops to the number given by the
        ``proxy.config.restart.active_client_threshold`` configuration
        variable.

    .. code-block:: bash

        salt '*' trafficserver.restart_local
        salt '*' trafficserver.restart_local drain=True
    '''
    if _TRAFFICCTL:
        cmd = _traffic_ctl('server', 'restart', '--manager')
    else:
        cmd = _traffic_line('-L')

    if drain:
        cmd = '{0} {1}'.format(cmd, '--drain')

    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def match_var(regex):
    '''
    Display the current values of all performance statistics or configuration
    variables whose names match the given regular expression.

    .. deprecated:: Oxygen
        Use ``match_metric`` or ``match_config`` instead.

    .. code-block:: bash

        salt '*' trafficserver.match_var regex
    '''
    cmd = _traffic_line('-m', regex)
    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def match_metric(regex):
    '''
    Display the current values of all metrics whose names match the
    given regular expression.

    .. versionadded:: Carbon

    .. code-block:: bash

        salt '*' trafficserver.match_metric regex
    '''
    if _TRAFFICCTL:
        cmd = _traffic_ctl('metric', 'match', regex)
    else:
        cmd = _traffic_ctl('-m', regex)

    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def match_config(regex):
    '''
    Display the current values of all configuration variables whose
    names match the given regular expression.

    .. versionadded:: Carbon

    .. code-block:: bash

        salt '*' trafficserver.match_config regex
    '''
    if _TRAFFICCTL:
        cmd = _traffic_ctl('config', 'match', regex)
    else:
        cmd = _traffic_line('-m', regex)

    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def read_config(*args):
    '''
    Read Traffic Server configuration variable definitions.

    .. versionadded:: Carbon

    .. code-block:: bash

        salt '*' trafficserver.read_config proxy.config.http.keep_alive_post_out
    '''

    ret = {}
    if _TRAFFICCTL:
        cmd = _traffic_ctl('config', 'get')
    else:
        cmd = _traffic_line('-r')

    try:
        for arg in args:
            log.debug('Querying: %s', arg)
            ret[arg] = _subprocess('{0} {1}'.format(cmd, arg))
    except KeyError:
        pass

    return ret


def read_metric(*args):
    '''
    Read Traffic Server one or more metrics.

    .. versionadded:: Carbon

    .. code-block:: bash

        salt '*' trafficserver.read_metric proxy.process.http.tcp_hit_count_stat
    '''

    ret = {}
    if _TRAFFICCTL:
        cmd = _traffic_ctl('metric', 'get')
    else:
        cmd = _traffic_line('-r')

    try:
        for arg in args:
            log.debug('Querying: %s', arg)
            ret[arg] = _subprocess('{0} {1}'.format(cmd, arg))
    except KeyError:
        pass

    return ret


def set_config(variable, value):
    '''
    Set the value of a Traffic Server configuration variable.

    variable
        Name of a Traffic Server configuration variable.

    value
        The new value to set.

    .. versionadded:: Carbon

    .. code-block:: bash

        salt '*' trafficserver.set_config proxy.config.http.keep_alive_post_out 0
    '''

    if _TRAFFICCTL:
        cmd = _traffic_ctl('config', 'set', variable, value)
    else:
        cmd = _traffic_line('-s', variable, '-v', value)

    log.debug('Setting %s to %s', variable, value)
    return _subprocess(cmd)


def read_var(*args):
    '''
    Read variable definitions from the traffic_line command.

    .. deprecated:: Oxygen
        Use ``read_metric`` or ``read_config`` instead. Note that this
        function does not work for Traffic Server versions >= 7.0.

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

    .. deprecated:: Oxygen
        Use ``set_config`` instead. Note that this function does
        not work for Traffic Server versions >= 7.0.

        salt '*' trafficserver.set_var proxy.config.http.server_ports
    '''

    cmd = _traffic_line('-s', variable, '-v', value)
    log.debug('Setting %s to %s', variable, value)
    return _subprocess(cmd)


def shutdown():
    '''
    Shut down Traffic Server on the local node.

    .. code-block:: bash

        salt '*' trafficserver.shutdown
    '''

    # Earlier versions of traffic_ctl do not support
    # "server stop", so we prefer traffic_line here.
    if _TRAFFICLINE:
        cmd = _traffic_line('-S')
    else:
        cmd = _traffic_ctl('server', 'stop')

    log.debug('Running: %s', cmd)
    _subprocess(cmd)
    return _statuscmd()


def startup():
    '''
    Start Traffic Server on the local node.

    .. code-block:: bash

        salt '*' trafficserver.start
    '''

    # Earlier versions of traffic_ctl do not support
    # "server start", so we prefer traffic_line here.
    if _TRAFFICLINE:
        cmd = _traffic_line('-U')
    else:
        cmd = _traffic_ctl('server', 'start')

    log.debug('Running: %s', cmd)
    _subprocess(cmd)
    return _statuscmd()


def refresh():
    '''
    Initiate a Traffic Server configuration file reread. Use this command to
    update the running configuration after any configuration file modification.

    The timestamp of the last reconfiguration event (in seconds since epoch) is
    published in the proxy.node.config.reconfigure_time metric.

    .. code-block:: bash

        salt '*' trafficserver.refresh
    '''

    if _TRAFFICCTL:
        cmd = _traffic_ctl('config', 'reload')
    else:
        cmd = _traffic_line('-x')

    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def zero_cluster():
    '''
    Reset performance statistics to zero across the cluster.

    .. code-block:: bash

        salt '*' trafficserver.zero_cluster
    '''
    if _TRAFFICCTL:
        cmd = _traffic_ctl('metric', 'clear', '--cluster')
    else:
        cmd = _traffic_line('-Z')

    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def zero_node():
    '''
    Reset performance statistics to zero on the local node.

    .. code-block:: bash

        salt '*' trafficserver.zero_cluster
    '''
    if _TRAFFICCTL:
        cmd = _traffic_ctl('metric', 'clear')
    else:
        cmd = _traffic_line('-z')

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

    if _TRAFFICCTL:
        cmd = _traffic_ctl('storage', 'offline', path)
    else:
        cmd = _traffic_line('--offline', path)

    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def alarms():
    '''
    List all alarm events that have not been acknowledged (cleared).

    .. code-block:: bash

        salt '*' trafficserver.alarms
    '''

    if _TRAFFICCTL:
        cmd = _traffic_ctl('alarm', 'list')
    else:
        cmd = _traffic_line('--alarms')

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

    if _TRAFFICCTL:
        cmd = _traffic_ctl('alarm', 'clear', alarm)
    else:
        cmd = _traffic_line('--clear_alarms', alarm)

    log.debug('Running: %s', cmd)
    return _subprocess(cmd)


def status():
    '''
    Show the current proxy server status, indicating if we’re running or not.

    .. code-block:: bash

        salt '*' trafficserver.status
    '''

    return _statuscmd()
