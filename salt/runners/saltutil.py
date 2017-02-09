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


def sync_all(saltenv='base', extmod_whitelist=None):
    '''
    Sync all custom types

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        dictionary of modules to sync based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_all
        salt-run saltutil.sync_all extmod_whitelist={'runners': ['custom_runner'], 'grains': []}
    '''
    log.debug('Syncing all')
    ret = {}
    ret['modules'] = sync_modules(saltenv=saltenv, extmod_whitelist=extmod_whitelist)
    ret['states'] = sync_states(saltenv=saltenv, extmod_whitelist=extmod_whitelist)
    ret['grains'] = sync_grains(saltenv=saltenv, extmod_whitelist=extmod_whitelist)
    ret['renderers'] = sync_renderers(saltenv=saltenv, extmod_whitelist=extmod_whitelist)
    ret['returners'] = sync_returners(saltenv=saltenv, extmod_whitelist=extmod_whitelist)
    ret['output'] = sync_output(saltenv=saltenv, extmod_whitelist=extmod_whitelist)
    ret['proxymodules'] = sync_proxymodules(saltenv=saltenv, extmod_whitelist=extmod_whitelist)
    ret['runners'] = sync_runners(saltenv=saltenv, extmod_whitelist=extmod_whitelist)
    ret['wheel'] = sync_wheel(saltenv=saltenv, extmod_whitelist=extmod_whitelist)
    ret['engines'] = sync_engines(saltenv=saltenv, extmod_whitelist=extmod_whitelist)
    ret['queues'] = sync_queues(saltenv=saltenv, extmod_whitelist=extmod_whitelist)
    ret['pillar'] = sync_pillar(saltenv=saltenv, extmod_whitelist=extmod_whitelist)
    ret['utils'] = sync_utils(saltenv=saltenv, extmod_whitelist=extmod_whitelist)
    ret['sdb'] = sync_sdb(saltenv=saltenv, extmod_whitelist=extmod_whitelist)
    return ret


def sync_modules(saltenv='base', extmod_whitelist=None):
    '''
    Sync execution modules from ``salt://_modules`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_modules
    '''
    return salt.utils.extmods.sync(__opts__, 'modules', saltenv=saltenv, extmod_whitelist=extmod_whitelist)[0]


def sync_states(saltenv='base', extmod_whitelist=None):
    '''
    Sync state modules from ``salt://_states`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_states
    '''
    return salt.utils.extmods.sync(__opts__, 'states', saltenv=saltenv, extmod_whitelist=extmod_whitelist)[0]


def sync_grains(saltenv='base', extmod_whitelist=None):
    '''
    Sync grains modules from ``salt://_grains`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_grains
    '''
    return salt.utils.extmods.sync(__opts__, 'grains', saltenv=saltenv, extmod_whitelist=extmod_whitelist)[0]


def sync_renderers(saltenv='base', extmod_whitelist=None):
    '''
    Sync renderer modules from from ``salt://_renderers`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_renderers
    '''
    return salt.utils.extmods.sync(__opts__, 'renderers', saltenv=saltenv, extmod_whitelist=extmod_whitelist)[0]


def sync_returners(saltenv='base', extmod_whitelist=None):
    '''
    Sync returner modules from ``salt://_returners`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_returners
    '''
    return salt.utils.extmods.sync(__opts__, 'returners', saltenv=saltenv, extmod_whitelist=extmod_whitelist)[0]


def sync_output(saltenv='base', extmod_whitelist=None):
    '''
    Sync output modules from ``salt://_output`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_output
    '''
    return salt.utils.extmods.sync(__opts__, 'output', saltenv=saltenv, extmod_whitelist=extmod_whitelist)[0]


def sync_proxymodules(saltenv='base', extmod_whitelist=None):
    '''
    Sync proxy modules from ``salt://_proxy`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_proxy
    '''
    return salt.utils.extmods.sync(__opts__, 'proxy', saltenv=saltenv, extmod_whitelist=extmod_whitelist)[0]


def sync_runners(saltenv='base', extmod_whitelist=None):
    '''
    Sync runners from ``salt://_runners`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_runners
    '''
    return salt.utils.extmods.sync(__opts__, 'runners', saltenv=saltenv, extmod_whitelist=extmod_whitelist)[0]


def sync_wheel(saltenv='base', extmod_whitelist=None):
    '''
    Sync wheel modules from ``salt://_wheel`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_wheel
    '''
    return salt.utils.extmods.sync(__opts__, 'wheel', saltenv=saltenv, extmod_whitelist=extmod_whitelist)[0]


def sync_engines(saltenv='base', extmod_whitelist=None):
    '''
    Sync engines from ``salt://_engines`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_engines
    '''
    return salt.utils.extmods.sync(__opts__, 'engines', saltenv=saltenv, extmod_whitelist=extmod_whitelist)[0]


def sync_queues(saltenv='base', extmod_whitelist=None):
    '''
    Sync queue modules from ``salt://_queues`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_queues
    '''
    return salt.utils.extmods.sync(__opts__, 'queues', saltenv=saltenv, extmod_whitelist=extmod_whitelist)[0]


def sync_pillar(saltenv='base', extmod_whitelist=None):
    '''
    Sync pillar modules from ``salt://_pillar`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_pillar
    '''
    return salt.utils.extmods.sync(__opts__, 'pillar', saltenv=saltenv, extmod_whitelist=extmod_whitelist)[0]


def sync_utils(saltenv='base', extmod_whitelist=None):
    '''
    .. versionadded:: 2016.11.0

    Sync utils modules from ``salt://_utils`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_utils
    '''
    return salt.utils.extmods.sync(__opts__, 'utils', saltenv=saltenv, extmod_whitelist=extmod_whitelist)[0]


def sync_sdb(saltenv='base', extmod_whitelist=None):
    '''
    .. versionadded:: Nitrogen

    Sync utils modules from ``salt://_sdb`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_sdb
    '''
    return salt.utils.extmods.sync(__opts__, 'sdb', saltenv=saltenv, extmod_whitelist=extmod_whitelist)[0]
