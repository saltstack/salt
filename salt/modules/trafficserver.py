# -*- coding: utf-8 -*-
'''
Apache Traffic Server Module

This module is a work in progress, initially designed to query for statistics
out of the http_ui, specifically /stat/. Eventually it will support clearing
cache itesm and bouncing the service.

The only requirement for this module is the existence of the ``traffic_line``
binary.
'''

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
        return subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]
    except OSError as err:
        log.error(err)
        return False


def alarms():
    '''
    Show all alarms

    .. code-block:: bash

        salt '*' trafficserver.alarms
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '--alarms')
    log.debug('running: cmd=%s', cmd)
    return _subprocess(cmd)


def bounce_local():
    '''
    Bounce local traffic_server

    .. code-block:: bash

        salt '*' trafficserver.bounce_local
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '-b')
    log.debug('running: cmd=%s', cmd)
    return _subprocess(cmd)


def clear_alarms(alarm):
    '''
    Clear Apache Traffic Server alarms

    .. code-block:: bash

        salt '*' trafficserver.clear_alarms foo
    '''

    cmd = '{0} {1} {2}'.format(_TRAFFICLINE, '--clear_alarms', alarm)
    log.debug('running: cmd=%s', cmd)
    return _subprocess(cmd)


def clear_local():
    '''
    Clear Statistics (local node)

    .. code-block:: bash

        salt '*' trafficserver.clear_local
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '-c')
    log.debug('running: cmd=%s', cmd)
    return _subprocess(cmd)


def offline():
    '''
    Mark cache storage offline

    .. code-block:: bash

        salt '*' trafficserver.offline
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '--offline')
    log.debug('running: cmd=%s', cmd)
    return _subprocess(cmd)


def restart_local():
    '''
    Restart traffic_manager (local node)

    .. code-block:: bash

        salt '*' trafficserver.restart_local
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '-L')
    log.debug('running: cmd=%s', cmd)
    return _subprocess(cmd)


def refresh():
    '''
    Reload the Traffic Server configuration

    .. code-block:: bash

        salt '*' trafficserver.reload
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '-x')
    log.debug('running: cmd=%s', cmd)
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
            log.debug('querying: arg=%s', arg)
            cmd = '{0} {1} {2}'.format(_TRAFFICLINE, '-r', arg)
            ret[arg] = _subprocess(cmd)
    except KeyError:
        pass

    return ret


def start():
    '''
    Start Apache Traffic Server proxy

    .. code-block:: bash

        salt '*' trafficserver.start
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '-U')
    status_cmd = '{0} {1}'.format(_TRAFFICLINE, '--status')
    log.debug('running: cmd=%s', cmd)
    _subprocess(cmd)
    return _subprocess(status_cmd)


def status():
    '''
    Query Apache Traffic Server status

    .. code-block:: bash

        salt '*' trafficserver.status
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '--status')
    log.debug('running: cmd=%s', cmd)
    return _subprocess(cmd)


def stop():
    '''
    Shutdown Apache Traffic Server

    .. code-block:: bash

        salt '*' trafficserver.stop
    '''

    cmd = '{0} {1}'.format(_TRAFFICLINE, '-S')
    status_cmd = '{0} {1}'.format(_TRAFFICLINE, '--status')
    log.debug('running: cmd=%s', cmd)
    _subprocess(cmd)
    return _subprocess(status_cmd)


