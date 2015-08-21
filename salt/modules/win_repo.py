# -*- coding: utf-8 -*-
r'''
Module to manage Windows software repo on a Standalone Minion

``file_client: local`` must be set in the minion config file.

For documentation on Salt's Windows Repo feature, see :ref:`here
<windows-package-manager`
'''

# Import python libs
from __future__ import absolute_import, print_function
import logging

# Import salt libs
import salt.output
import salt.utils
import salt.loader
import salt.template
from salt.exceptions import CommandExecutionError
from salt.runners.winrepo import (
    genrepo as _genrepo,
    update_git_repos as _update_git_repos
)

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'winrepo'


def __virtual__():
    '''
    Set the winrepo module if the OS is Windows
    '''
    if salt.utils.is_windows():
        global _genrepo, _update_git_repos
        _genrepo = salt.utils.namespaced_function(_genrepo, globals())
        _update_git_repos = \
            salt.utils.namespaced_function(_update_git_repos, globals())
        return __virtualname__
    return False


def genrepo():
    r'''
    Generate winrepo_cachefile based on sls files in the winrepo_dir

    CLI Example:

    .. code-block:: bash

        salt-call winrepo.genrepo
    '''
    return _genrepo(opts=__opts__, fire_event=False)


def update_git_repos():
    '''
    Checkout git repos containing :ref:`Windows Software Package Definitions
    <windows-package-manager>`

    .. important::
        This function requires `Git for Windows`_ to be installed in order to
        work. When installing, make sure to select an installation option which
        permits the git executable to be run from the Command Prompt.

    .. _`Git for Windows`: https://git-for-windows.github.io/

    CLI Example:

    .. code-block:: bash

        salt-call winrepo.update_git_repos
    '''
    if not salt.utils.which('git'):
        raise CommandExecutionError(
            'Git for Windows is not installed, or not configured to be '
            'accessible from the Command Prompt'
        )
    return _update_git_repos(opts=__opts__, masterless=True)
