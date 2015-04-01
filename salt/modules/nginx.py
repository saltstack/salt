# -*- coding: utf-8 -*-
'''
Support for nginx
'''
from __future__ import absolute_import

# Import 3rd-party libs
from salt.ext.six.moves.urllib.request import urlopen as _urlopen  # pylint: disable=no-name-in-module,import-error

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators

import re


# Cache the output of running which('nginx') so this module
# doesn't needlessly walk $PATH looking for the same binary
# for nginx over and over and over for each function herein
@decorators.memoize
def __detect_os():
    return salt.utils.which('nginx')


def __virtual__():
    '''
    Only load the module if nginx is installed
    '''
    if __detect_os():
        return True
    return False


def version():
    '''
    Return server version from nginx -v

    CLI Example:

    .. code-block:: bash

        salt '*' nginx.version
    '''
    cmd = '{0} -v'.format(__detect_os())
    out = __salt__['cmd.run'](cmd).splitlines()
    ret = out[0].split(': ')
    return ret[-1]


def build_info():
    '''
    Return server and build arguments

    CLI Example:

    .. code-block:: bash

        salt '*' nginx.build_info
    '''
    ret = {'info': []}
    out = __salt__['cmd.run']('{0} -V'.format(__detect_os()))

    for i in out.splitlines():
        if i.startswith('configure argument'):
            ret['build arguments'] = re.findall(r"(?:[^\s]*'.*')|(?:[^\s]+)", i)[2:]
            continue

        ret['info'].append(i)

    return ret


def configtest():
    '''
    test configuration and exit

    CLI Example:

    .. code-block:: bash

        salt '*' nginx.configtest
    '''
    ret = {}

    cmd = '{0} -t'.format(__detect_os())
    out = __salt__['cmd.run_all'](cmd)

    if out['retcode'] != 0:
        ret['comment'] = 'Syntax Error'
        ret['stderr'] = out['stderr']
        ret['result'] = False

        return ret

    ret['comment'] = 'Syntax OK'
    ret['stdout'] = out['stderr']
    ret['result'] = True

    return ret


def signal(signal=None):
    '''
    Signals nginx to start, reload, reopen or stop.

    CLI Example:

    .. code-block:: bash

        salt '*' nginx.signal reload
    '''
    valid_signals = ('start', 'reopen', 'stop', 'quit', 'reload')

    if signal not in valid_signals:
        return

    # Make sure you use the right arguments
    if signal == "start":
        arguments = ''
    else:
        arguments = ' -s {0}'.format(signal)
    cmd = __detect_os() + arguments
    out = __salt__['cmd.run_all'](cmd)

    # A non-zero return code means fail
    if out['retcode'] and out['stderr']:
        ret = out['stderr'].strip()
    # 'nginxctl configtest' returns 'Syntax OK' to stderr
    elif out['stderr']:
        ret = out['stderr'].strip()
    elif out['stdout']:
        ret = out['stdout'].strip()
    # No output for something like: nginxctl graceful
    else:
        ret = 'Command: "{0}" completed successfully!'.format(cmd)
    return ret


def status(url="http://127.0.0.1/status"):
    """
    Return the data from an Nginx status page as a dictionary.
    http://wiki.nginx.org/HttpStubStatusModule

    url
        The URL of the status page. Defaults to 'http://127.0.0.1/status'

    CLI Example:

    .. code-block:: bash

        salt '*' nginx.status
    """
    resp = _urlopen(url)
    status_data = resp.read()
    resp.close()

    lines = status_data.splitlines()
    if not len(lines) == 4:
        return
    # "Active connections: 1 "
    active_connections = lines[0].split()[2]
    # "server accepts handled requests"
    # "  12 12 9 "
    accepted, handled, requests = lines[2].split()
    # "Reading: 0 Writing: 1 Waiting: 0 "
    _, reading, _, writing, _, waiting = lines[3].split()
    return {
        'active connections': int(active_connections),
        'accepted': int(accepted),
        'handled': int(handled),
        'requests': int(requests),
        'reading': int(reading),
        'writing': int(writing),
        'waiting': int(waiting),
    }
