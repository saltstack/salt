# -*- coding: utf-8 -*-
'''
Package helper functions using ``salt.modules.pkg``

.. versionadded:: 2015.8.0
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
import salt.output
import salt.minion

# Import 3rd-party libs
from salt.ext import six


def _get_returner(returner_types):
    '''
    Helper to iterate over retuerner_types and pick the first one
    '''
    for returner in returner_types:
        if returner:
            return returner


def list_upgrades(jid,
                  style='group',
                  outputter='nested',
                  ext_source=None):
    '''
    Show list of available pkg upgrades using a specified format style

    CLI Example:

    .. code-block:: bash

        salt-run pkg.list_upgrades jid=20141120114114417719 style=group
    '''
    mminion = salt.minion.MasterMinion(__opts__)
    returner = _get_returner((
        __opts__['ext_job_cache'],
        ext_source,
        __opts__['master_job_cache']
    ))

    data = mminion.returners['{0}.get_jid'.format(returner)](jid)
    pkgs = {}

    if style == 'group':
        for minion in data:
            results = data[minion]['return']
            for pkg, pkgver in six.iteritems(results):
                if pkg not in six.iterkeys(pkgs):
                    pkgs[pkg] = {pkgver: {'hosts': []}}

                if pkgver not in six.iterkeys(pkgs[pkg]):
                    pkgs[pkg].update({pkgver: {'hosts': []}})

                pkgs[pkg][pkgver]['hosts'].append(minion)

    if outputter:
        salt.output.display_output(pkgs, outputter, opts=__opts__)

    return pkgs
