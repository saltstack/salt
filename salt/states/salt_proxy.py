# -*- coding: utf-8 -*-

import os
import logging

log = logging.getLogger(__name__)


def _proxy_conf_file(proxyfile):
    changes = []
    success = True
    if not os.path.exists(proxyfile):
        __salt__['salt_proxy.write_proxy_conf'](path=proxyfile)
        try:
            msg = 'Salt Proxy: Wrote proxy conf {0}'.format(proxyfile)
        except (OSError, IOError) as err:
            success = False
            msg = 'Salt Proxy: Error writing proxy file {0}'.format(str(err))
            log.error(msg)
            changes.append(msg)
        changes.append(msg)
        log.debug(msg)
    else:
        msg = 'Salt Proxy: {0} already exists, skipping'.format(proxyfile)
        changes.append(msg)
        log.debug(msg)
    return success, changes


def configure_proxy(proxyname='p8000', start=True, **kwargs):
    changes = []
    status = True

    # write the proxy file if necessary
    proxyfile = '/etc/salt/proxy'
    status, msg = _proxy_conf_file(proxyfile)
    changes.extend(msg)
    # start the proxy process
    if start:
        __salt__['cmd.run'](
            'salt-proxy --proxyid={0} -l info -d'.format(proxyname),
            timeout=5)
        msg = 'Started salt proxy for {0}'.format(proxyname)
        changes.append(msg)
        log.info(msg)

    return {'result': status, 'changes': '\n'.join(changes), 'name': proxyname,
            'comment': 'Proxy config messages'}
