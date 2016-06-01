# -*- coding: utf-8 -*-
'''
Sync custom types to the Master

.. versionadded:: 2016.3.0
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils.extmods

log = logging.getLogger(__name__)


def sync_all(saltenv='base'):
    '''
    Sync all custom types

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_all
    '''
    log.debug('Syncing all')
    ret = {}
    ret['modules'] = sync_modules(saltenv=saltenv)
    ret['states'] = sync_states(saltenv=saltenv)
    ret['grains'] = sync_grains(saltenv=saltenv)
    ret['renderers'] = sync_renderers(saltenv=saltenv)
    ret['returners'] = sync_returners(saltenv=saltenv)
    ret['output'] = sync_output(saltenv=saltenv)
    ret['proxymodules'] = sync_proxymodules(saltenv=saltenv)
    ret['runners'] = sync_runners(saltenv=saltenv)
    ret['wheel'] = sync_wheel(saltenv=saltenv)
    ret['engines'] = sync_engines(saltenv=saltenv)
    ret['queues'] = sync_queues(saltenv=saltenv)
    ret['pillar'] = sync_pillar(saltenv=saltenv)
    return ret


def sync_modules(saltenv='base'):
    '''
    Sync execution modules from ``salt://_modules`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_modules
    '''
    return salt.utils.extmods.sync(__opts__, 'modules', saltenv=saltenv)[0]


def sync_states(saltenv='base'):
    '''
    Sync state modules from ``salt://_states`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_states
    '''
    return salt.utils.extmods.sync(__opts__, 'states', saltenv=saltenv)[0]


def sync_grains(saltenv='base'):
    '''
    Sync grains modules from ``salt://_grains`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_grains
    '''
    return salt.utils.extmods.sync(__opts__, 'grains', saltenv=saltenv)[0]


def sync_renderers(saltenv='base'):
    '''
    Sync renderer modules from from ``salt://_renderers`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_renderers
    '''
    return salt.utils.extmods.sync(__opts__, 'renderers', saltenv=saltenv)[0]


def sync_returners(saltenv='base'):
    '''
    Sync returner modules from ``salt://_returners`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_returners
    '''
    return salt.utils.extmods.sync(__opts__, 'returners', saltenv=saltenv)[0]


def sync_output(saltenv='base'):
    '''
    Sync output modules from ``salt://_output`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_output
    '''
    return salt.utils.extmods.sync(__opts__, 'output', saltenv=saltenv)[0]


def sync_proxymodules(saltenv='base'):
    '''
    Sync proxy modules from ``salt://_proxy`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_proxy
    '''
    return salt.utils.extmods.sync(__opts__, 'proxy', saltenv=saltenv)[0]


def sync_runners(saltenv='base'):
    '''
    Sync runners from ``salt://_runners`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_runners
    '''
    return salt.utils.extmods.sync(__opts__, 'runners', saltenv=saltenv)[0]


def sync_wheel(saltenv='base'):
    '''
    Sync wheel modules from ``salt://_wheel`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_wheel
    '''
    return salt.utils.extmods.sync(__opts__, 'wheel', saltenv=saltenv)[0]


def sync_engines(saltenv='base'):
    '''
    Sync engines from ``salt://_engines`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_engines
    '''
    return salt.utils.extmods.sync(__opts__, 'engines', saltenv=saltenv)[0]


def sync_queues(saltenv='base'):
    '''
    Sync queue modules from ``salt://_queues`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_queues
    '''
    return salt.utils.extmods.sync(__opts__, 'queues', saltenv=saltenv)[0]


def sync_pillar(saltenv='base'):
    '''
    Sync pillar modules from ``salt://_pillar`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_pillar
    '''
    return salt.utils.extmods.sync(__opts__, 'pillar', saltenv=saltenv)[0]
