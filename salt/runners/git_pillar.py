# -*- coding: utf-8 -*-
'''
Directly manage the salt git_pillar plugin
'''
from __future__ import absolute_import

# Import salt libs
import salt.pillar.git_pillar
from salt.exceptions import SaltRunnerError


def update(branch, repo):
    '''
    Execute an update for the configured git fileserver backend for Pillar

    CLI Example:

    .. code-block:: bash

        salt-run git_pillar.update branch='branch' repo='location'
    '''
    for opts_dict in __opts__.get('ext_pillar', []):
        parts = opts_dict.get('git', '').split()
        if len(parts) >= 2 and parts[:2] == [branch, repo]:
            salt.pillar.git_pillar.GitPillar(branch, repo, __opts__).update()
            break
    else:
        raise SaltRunnerError('git repo/branch not found in ext_pillar config')
