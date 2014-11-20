# -*- coding: utf-8 -*-
'''
Package helper functions which provide other formatted output of
salt.modules.pkg
'''

# Import salt libs
import salt.output
import salt.minion


def _get_returner(returner_types):
    '''
    Helper to iterate over retuerner_types and pick the first one
    '''
    for returner in returner_types:
        if returner:
            return returner


def group_upgrades(jid, outputter='nested', ext_source=None):
    '''
    List available pkg upgrades and group by packages

    CLI Example:

    .. code-block:: bash

        salt-run pkg.group_upgrades jid=20141120114114417719
    '''
    mminion = salt.minion.MasterMinion(__opts__)
    returner = _get_returner((
        __opts__['ext_job_cache'],
        ext_source,
        __opts__['master_job_cache']
    ))

    data = mminion.returners['{0}.get_jid'.format(returner)](jid)
    pkgs = {}

    for minion in data:
        results = data[minion]['return']
        for pkg, pkgver in results.items():
            if pkg not in pkgs.keys():
                pkgs[pkg] = {pkgver: {'hosts': []}}

            if pkgver not in pkgs[pkg].keys():
                pkgs[pkg].update({pkgver: {'hosts': []}})

            pkgs[pkg][pkgver]['hosts'].append(minion)

    if outputter:
        salt.output.display_output(pkgs, outputter, opts=__opts__)
    return pkgs
