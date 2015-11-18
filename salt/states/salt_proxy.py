# -*- coding: utf-8 -*-
'''
    State to deploy and run salt-proxy processes
    on a minion.

    Set up pillar data for your proxies per the documentation.

    Run the state as below

    ..code-block:: yaml

        salt-proxy-configure:
            salt_proxy.configure_proxy:
                - proxyname: p8000
                - start: True

    This state will configure the salt proxy settings
    within /etc/salt/proxy (if /etc/salt/proxy doesn't exists)
    and start the salt-proxy process (default true),
    if it isn't already running.
'''
from salt.ext.six.moves import shlex_quote as quote

import os
import logging

log = logging.getLogger(__name__)


def _write_proxy_conf(proxyfile):
    msg = 'Invalid value for proxy file provided!, Supplied value = {0}' \
        .format(proxyfile)

    log.trace('Salt Proxy Module: write proxy conf')

    if proxyfile:
        log.debug('Writing proxy conf file')
        with open(path, 'w') as proxy_conf:
            proxy_conf.write('master = {0}'
                             .format(__grains__['master']))
        msg = 'Wrote proxy file {0}'.format(proxyfile)
        log.debug(msg)

    return msg


def _proxy_conf_file(proxyfile):
    changes_old = []
    changes_new = []
    success = True
    if not os.path.exists(proxyfile):
        try:
            changes_new.append(_write_proxy_conf(proxyfile))
            msg = 'Salt Proxy: Wrote proxy conf {0}'.format(proxyfile)
        except (OSError, IOError) as err:
            success = False
            msg = 'Salt Proxy: Error writing proxy file {0}'.format(str(err))
            log.error(msg)
            changes_new.append(msg)
        changes_new.append(msg)
        log.debug(msg)
    else:
        msg = 'Salt Proxy: {0} already exists, skipping'.format(proxyfile)
        changes_old.append(msg)
        log.debug(msg)
    return success, changes_new, changes_old


def configure_proxy(proxyname='p8000', start=True, **kwargs):
    '''
    Create the salt proxy file and start the proxy process
    if required
    '''
    changes_new = []
    changes_old = []
    status = True

    # write the proxy file if necessary
    proxyfile = '/etc/salt/proxy'
    status, msg_new, msg_old = _proxy_conf_file(proxyfile)
    changes_new.extend(msg_new)
    changes_old.extend(msg_old)
    # start the proxy process
    if start:
        cmd = ('ps ax | grep "salt-proxy --proxyid={0}" | grep -v grep'
               .format(quote(proxyname)))
        cmdout = __salt__['cmd.run_all'](
            cmd,
            timeout=5,
            python_shell=True)
        if not cmdout['stdout']:
            __salt__['cmd.run'](
                'salt-proxy --proxyid={0} -l info -d'.format(proxyname),
                timeout=5)
            changes_new.append('Started salt proxy for {0}'.format(proxyname))
            log.debug('Proxy started')
        else:
            changes_old.append('Salt proxy already running for {0}'
                               .format(proxyname))
            log.debug('Proxy already running')

    return {
        'result': status,
        'changes': {
            'old': '\n'.join(changes_old),
            'new': '\n'.join(changes_new),
        },
        'name': proxyname,
        'comment': 'Proxy config messages'
    }
