# -*- coding: utf-8 -*-
'''
Directly manage the salt git_pillar plugin
'''

# Import salt libs
import salt.pillar.git_pillar


def update(branch, repo):
    '''
    Execute an update for the configured git fileserver backend for Pillar

    CLI Example:

    .. code-block:: bash

        salt-run git_pillar.update branch='branch' repo='location'
    '''
    fileserver = salt.pillar.git_pillar.GitPillar(branch, repo, __opts__)
    fileserver.update()
