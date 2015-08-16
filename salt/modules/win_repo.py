# -*- coding: utf-8 -*-
r'''
Module to manage Windows software repo on a Standalone Minion

``file_client: local`` must be set in the minion config file. Other config
options of interest include:

* :conf_minion:`winrepo_dir`
* :conf_minion:`winrepo_cachefile`

Place all Windows package files in the 'win_repo' directory.
'''

# Import python libs
from __future__ import absolute_import, print_function
import os
import logging

# Import third party libs
import salt.ext.six as six
# pylint: disable=import-error
try:
    import msgpack
except ImportError:
    import msgpack_pure as msgpack

# Import salt libs
import salt.output
import salt.utils
import salt.loader
import salt.template

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'winrepo'


def __virtual__():
    '''
    Set the winrepo module if the OS is Windows
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return False


def genrepo():
    r'''
    Generate winrepo_cachefile based on sls files in the win_repo

    CLI Example:

    .. code-block:: bash

        salt-call winrepo.genrepo -c c:\salt\conf
    '''
    if 'win_repo' in __opts__:
        salt.utils.warn_until(
            'Nitrogen',
            'The \'win_repo\' config option is deprecated, please use '
            '\'winrepo_dir\' instead.'
        )
        winrepo_dir = __opts__['win_repo']
    else:
        winrepo_dir = __opts__['winrepo_dir']

    if 'win_repo_cachefile' in __opts__:
        salt.utils.warn_until(
            'Nitrogen',
            'The \'win_repo_cachefile\' config option is deprecated, please '
            'use \'winrepo_cachefile\' instead.'
        )
        winrepo_cachefile = __opts__['win_repo_cachefile']
    else:
        winrepo_cachefile = __opts__['winrepo_cachefile']

    ret = {}
    if not os.path.exists(winrepo_dir):
        os.makedirs(winrepo_dir)
    renderers = salt.loader.render(__opts__, __salt__)
    for root, dirs, files in os.walk(winrepo_dir):
        for name in files:
            if name.endswith('.sls'):
                config = salt.template.compile_template(
                            os.path.join(root, name),
                            renderers,
                            __opts__['renderer'])
                if config:
                    revmap = {}
                    for pkgname, versions in six.iteritems(config):
                        for version, repodata in six.iteritems(versions):
                            if not isinstance(version, six.string_types):
                                config[pkgname][str(version)] = \
                                    config[pkgname].pop(version)
                            revmap[repodata['full_name']] = pkgname
                    ret.setdefault('repo', {}).update(config)
                    ret.setdefault('name_map', {}).update(revmap)
    with salt.utils.fopen(
            os.path.join(winrepo_dir, winrepo_cachefile), 'w+b') as repo:
        repo.write(msgpack.dumps(ret))
    salt.output.display_output(ret, 'pprint', __opts__)
    return ret


def update_git_repos():
    '''
    Checkout git repos containing Windows Software Package Definitions

    .. note::

        This function will not work unless git is installed and the git module
        is further updated to work on Windows. In the meantime just place all
        Windows package files in the :conf_minion:`winrepo_dir` directory.
    '''
    if 'win_repo' in __opts__:
        salt.utils.warn_until(
            'Nitrogen',
            'The \'win_repo\' config option is deprecated, please use '
            '\'winrepo_dir\' instead.'
        )
        winrepo_dir = __opts__['win_repo']
    else:
        winrepo_dir = __opts__['winrepo_dir']

    if 'win_gitrepos' in __opts__:
        salt.utils.warn_until(
            'Nitrogen',
            'The \'win_gitrepos\' config option is deprecated, please use '
            '\'winrepo_remotes\' instead.'
        )
        winrepo_remotes = __opts__['win_gitrepos']
    else:
        winrepo_remotes = __opts__['winrepo_remotes']

    ret = {}
    #mminion = salt.minion.MasterMinion(__opts__)
    for remote in winrepo_remotes:
        #if '/' in remote:
            #targetname = remote.split('/')[-1]
        #else:
            #targetname = remote
        targetname = remote
        rev = None
        # If a revision is specified, use it.
        if len(remote.strip().split(' ')) > 1:
            rev, remote = remote.strip().split(' ')
        gittarget = os.path.join(winrepo_dir, targetname)
        #result = mminion.states['git.latest'](remote,
        result = __salt__['git.latest'](remote,
                                        rev=rev,
                                        target=gittarget,
                                        force=True)
        ret[result['name']] = result['result']
    salt.output.display_output(ret, 'pprint', __opts__)
    return ret
