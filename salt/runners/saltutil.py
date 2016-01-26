# -*- coding: utf-8 -*-
'''
Sync custom types to the Master
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils.extmods

log = logging.getLogger(__name__)


def sync_all(saltenv=None):
    '''
    Sync all custom types

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.sync_all
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
    return ret


def sync_modules(saltenv='base'):
    '''
    Sync execution modules to the Master's :conf_master:`extension_modules`
    directory

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_modules
    '''
    return salt.utils.extmods.sync(__opts__, 'modules', saltenv=saltenv)[0]


def sync_states(saltenv='base'):
    '''
    Sync state modules to the Master's :conf_master:`extension_modules`
    directory

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_states
    '''
    return salt.utils.extmods.sync(__opts__, 'states', saltenv=saltenv)[0]


def sync_grains(saltenv='base'):
    '''
    Sync grains modules to the Master's :conf_master:`extension_modules`
    directory

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_grains
    '''
    return salt.utils.extmods.sync(__opts__, 'grains', saltenv=saltenv)[0]


def sync_renderers(saltenv='base'):
    '''
    Sync renderer modules to the Master's :conf_master:`extension_modules`
    directory

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_renderers
    '''
    return salt.utils.extmods.sync(__opts__, 'renderers', saltenv=saltenv)[0]


def sync_returners(saltenv='base'):
    '''
    Sync returner modules to the Master's :conf_master:`extension_modules`
    directory

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_returners
    '''
    return salt.utils.extmods.sync(__opts__, 'returners', saltenv=saltenv)[0]


def sync_output(saltenv='base'):
    '''
    Sync output modules to the Master's :conf_master:`extension_modules`
    directory

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_output
    '''
    return salt.utils.extmods.sync(__opts__, 'output', saltenv=saltenv)[0]


def sync_proxymodules(saltenv='base'):
    '''
    Sync proxy modules to the Master's :conf_master:`extension_modules`
    directory

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_proxy
    '''
    return salt.utils.extmods.sync(__opts__, 'proxy', saltenv=saltenv)[0]


def sync_runners(saltenv='base'):
    '''
    Sync runners to the Master's :conf_master:`extension_modules` directory

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_runners
    '''
    return salt.utils.extmods.sync(__opts__, 'runners', saltenv=saltenv)[0]


def sync_wheel(saltenv='base'):
    '''
    Sync wheel modules to the Master's :conf_master:`extension_modules`
    directory

    CLI Example:

    .. code-block:: bash

        salt-run saltutil.sync_wheel
    '''
    return salt.utils.extmods.sync(__opts__, 'wheel', saltenv=saltenv)[0]
