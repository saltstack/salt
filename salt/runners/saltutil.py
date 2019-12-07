# -*- coding: utf-8 -*-
'''
The Saltutil runner is used to sync custom types to the Master. See the
:mod:`saltutil module <salt.modules.saltutil>` for documentation on
managing updates to minions.

.. versionadded:: 2016.3.0
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import salt libs
import salt.utils.extmods

log = logging.getLogger(__name__)


def sync_all(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    Sync all custom types

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        dictionary of modules to sync based on type

    extmod_blacklist : None
        dictionary of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_all
        salt-run saltutil.sync_all extmod_whitelist={'runners': ['custom_runner'], 'grains': []}
    '''
    log.debug('Syncing all')
    ret = {}
    ret['clouds'] = sync_clouds(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['modules'] = sync_modules(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['states'] = sync_states(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['grains'] = sync_grains(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['renderers'] = sync_renderers(saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                      extmod_blacklist=extmod_blacklist)
    ret['returners'] = sync_returners(saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                      extmod_blacklist=extmod_blacklist)
    ret['output'] = sync_output(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['proxymodules'] = sync_proxymodules(saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                            extmod_blacklist=extmod_blacklist)
    ret['runners'] = sync_runners(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['wheel'] = sync_wheel(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['engines'] = sync_engines(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['thorium'] = sync_thorium(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['queues'] = sync_queues(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['pillar'] = sync_pillar(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['utils'] = sync_utils(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['sdb'] = sync_sdb(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['cache'] = sync_cache(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['fileserver'] = sync_fileserver(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['tops'] = sync_tops(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['tokens'] = sync_eauth_tokens(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['serializers'] = sync_serializers(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    ret['executors'] = sync_executors(saltenv=saltenv, extmod_whitelist=extmod_whitelist, extmod_blacklist=extmod_blacklist)
    return ret


def sync_modules(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    Sync execution modules from ``salt://_modules`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_modules
    '''
    return salt.utils.extmods.sync(__opts__, 'modules', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_states(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    Sync state modules from ``salt://_states`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_states
    '''
    return salt.utils.extmods.sync(__opts__, 'states', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_grains(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    Sync grains modules from ``salt://_grains`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_grains
    '''
    return salt.utils.extmods.sync(__opts__, 'grains', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_renderers(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    Sync renderer modules from from ``salt://_renderers`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_renderers
    '''
    return salt.utils.extmods.sync(__opts__, 'renderers', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_returners(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    Sync returner modules from ``salt://_returners`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_returners
    '''
    return salt.utils.extmods.sync(__opts__, 'returners', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_output(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    Sync output modules from ``salt://_output`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_output
    '''
    return salt.utils.extmods.sync(__opts__, 'output', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_proxymodules(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    Sync proxy modules from ``salt://_proxy`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_proxy
    '''
    return salt.utils.extmods.sync(__opts__, 'proxy', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_runners(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    Sync runners from ``salt://_runners`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_runners
    '''
    return salt.utils.extmods.sync(__opts__, 'runners', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_wheel(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    Sync wheel modules from ``salt://_wheel`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_wheel
    '''
    return salt.utils.extmods.sync(__opts__, 'wheel', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_engines(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    Sync engines from ``salt://_engines`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_engines
    '''
    return salt.utils.extmods.sync(__opts__, 'engines', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_thorium(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    .. versionadded:: 2018.3.0

    Sync Thorium from ``salt://_thorium`` to the master

    saltenv: ``base``
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist
        comma-seperated list of modules to sync

    extmod_blacklist
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_thorium
    '''
    return salt.utils.extmods.sync(__opts__, 'thorium', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_queues(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    Sync queue modules from ``salt://_queues`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_queues
    '''
    return salt.utils.extmods.sync(__opts__, 'queues', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_pillar(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    Sync pillar modules from ``salt://_pillar`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_pillar
    '''
    return salt.utils.extmods.sync(__opts__, 'pillar', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_utils(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    .. versionadded:: 2016.11.0

    Sync utils modules from ``salt://_utils`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_utils
    '''
    return salt.utils.extmods.sync(__opts__, 'utils', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_sdb(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    .. versionadded:: 2017.7.0

    Sync sdb modules from ``salt://_sdb`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_sdb
    '''
    return salt.utils.extmods.sync(__opts__, 'sdb', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_tops(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    .. versionadded:: 2016.3.7,2016.11.4,2017.7.0

    Sync master_tops modules from ``salt://_tops`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_tops
    '''
    return salt.utils.extmods.sync(__opts__, 'tops', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_cache(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    .. versionadded:: 2017.7.0

    Sync cache modules from ``salt://_cache`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_cache
    '''
    return salt.utils.extmods.sync(__opts__, 'cache', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_fileserver(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    .. versionadded:: 2018.3.0

    Sync fileserver modules from ``salt://_fileserver`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_fileserver
    '''
    return salt.utils.extmods.sync(__opts__, 'fileserver', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_clouds(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    .. versionadded:: 2017.7.0

    Sync cloud modules from ``salt://_clouds`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_clouds
    '''
    return salt.utils.extmods.sync(__opts__, 'clouds', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_roster(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    .. versionadded:: 2017.7.0

    Sync roster modules from ``salt://_roster`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_roster
    '''
    return salt.utils.extmods.sync(__opts__, 'roster', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_eauth_tokens(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    .. versionadded:: 2018.3.0

    Sync eauth token modules from ``salt://_tokens`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_eauth_tokens
    '''
    return salt.utils.extmods.sync(__opts__, 'tokens', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_serializers(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    .. versionadded:: 2019.2.0

    Sync serializer modules from ``salt://_serializers`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_utils
    '''
    return salt.utils.extmods.sync(__opts__, 'serializers', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]


def sync_executors(saltenv='base', extmod_whitelist=None, extmod_blacklist=None):
    '''
    .. versionadded:: Neon

    Sync executor modules from ``salt://_executors`` to the master

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    extmod_whitelist : None
        comma-seperated list of modules to sync

    extmod_blacklist : None
        comma-seperated list of modules to blacklist based on type

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_executors
    '''
    return salt.utils.extmods.sync(__opts__, 'executors', saltenv=saltenv, extmod_whitelist=extmod_whitelist,
                                   extmod_blacklist=extmod_blacklist)[0]
