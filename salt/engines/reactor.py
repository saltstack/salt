# -*- coding: utf-8 -*-
'''
Setup Reactor

Example Config in Master or Minion config

.. code-block:: yaml

    engines:
      reactor:
        refresh_interval: 60
        worker_threads: 10
        worker_hwm: 10000

    reactor:
      - 'salt/cloud/*/destroyed':
        - /srv/reactor/destroy/*.sls

'''
# Import Python libs
from __future__ import absolute_import


# Import salt libs
import salt.utils.reactor


def start(refresh_interval=60, worker_threads=10, worker_hwm=10000):
    __opts__['reactor_refresh_interval'] = __opts__.get('reactor_refresh_interval') or refresh_interval
    __opts__['reactor_worker_threads'] = __opts__.get('reactor_worker_threads') or worker_threads
    __opts__['reactor_worker_hwm'] = __opts__.get('reactor_worker_hwm') or worker_hwm
    salt.utils.reactor.Reactor(__opts__).run()
