# -*- coding: utf-8 -*-
'''
Watch for pkgs that have upgrades, then fire an event.

.. versionadded:: 2016.3.0
'''

# Import python libs
from __future__ import absolute_import

__virtualname__ = 'pkg'

import logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if strace is installed
    '''
    return __virtualname__ if 'pkg.upgrade_available' in __salt__ else False


def validate(config):
    '''
    Validate the beacon configuration
    '''
    # Configuration for pkg beacon should be a list
    if not isinstance(config, dict):
        return False, ('Configuration for pkg beacon must be a dictionary.')
    if 'pkgs' not in config:
        return False, ('Configuration for pkg beacon requires list of pkgs.')
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    Check if installed packages are the latest versions
    and fire an event for those that have upgrades.

    .. code-block:: yaml

        beacons:
          pkg:
            - pkgs:
                - zsh
                - apache2
            - refresh: True
    '''
    ret = []
    _validate = validate(config)
    if not _validate[0]:
        return ret

    _refresh = False
    if 'refresh' in config and config['refresh']:
        _refresh = True
    for pkg in config['pkgs']:
        _installed = __salt__['pkg.version'](pkg)
        _latest = __salt__['pkg.latest_version'](pkg, refresh=_refresh)
        if _installed and _latest:
            _pkg = {'pkg': pkg,
                    'version': _latest
                    }
            ret.append(_pkg)
    return ret
