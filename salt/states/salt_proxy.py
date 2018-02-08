# -*- coding: utf-8 -*-
'''
    Salt proxy state

    .. versionadded:: 2015.8.2

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
from __future__ import absolute_import, unicode_literals, print_function

import logging

log = logging.getLogger(__name__)


def configure_proxy(name, proxyname='p8000', start=True):
    '''
    Create the salt proxy file and start the proxy process
    if required

    Parameters:
        name:
            The name of this state
        proxyname:
            Name to be used for this proxy (should match entries in pillar)
        start:
            Boolean indicating if the process should be started

    Example:

    ..code-block:: yaml

        salt-proxy-configure:
            salt_proxy.configure_proxy:
                - proxyname: p8000
                - start: True

    '''
    ret = __salt__['salt_proxy.configure_proxy'](proxyname,
                                                 start=start)
    ret.update({
        'name': name,
        'comment': '{0} config messages'.format(name)
    })
    return ret
