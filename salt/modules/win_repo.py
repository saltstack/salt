# -*- coding: utf-8 -*-
r'''
Module to manage Windows software repo on a Standalone Minion

The following options must be set in the Minion config:
  file_client: local
  win_repo_cachefile: c:\salt\file_roots\winrepo\winrepo.p
  win_repo: c:\salt\file_roots\winrepo

Place all Windows package files in the 'win_repo' directory.
'''

# Import python libs
from __future__ import absolute_import
from __future__ import print_function
import os

# Import third party libs
import yaml
try:
    import msgpack
except ImportError:
    import msgpack_pure as msgpack

# Import salt libs
import salt.output
import salt.utils
import logging
from salt.ext.six import string_types

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
    Generate win_repo_cachefile based on sls files in the win_repo

    CLI Example:

    .. code-block:: bash

        salt-call winrepo.genrepo -c c:\salt\conf
    '''
    ret = {}
    repo = __opts__['win_repo']
    if not os.path.exists(repo):
        os.makedirs(repo)
    winrepo = __opts__['win_repo_cachefile']
    for root, dirs, files in os.walk(repo):
        for name in files:
            if name.endswith('.sls'):
                with salt.utils.fopen(os.path.join(root, name), 'r') as slsfile:
                    try:
                        config = yaml.safe_load(slsfile.read()) or {}
                    except yaml.parser.ParserError as exc:
                        # log.debug doesn't seem to be working
                        # delete the following print statement
                        # when log.debug works
                        log.debug('Failed to compile'
                                  '{0}: {1}'.format(os.path.join(root, name), exc))
                        print('Failed to compile {0}: {1}'.format(os.path.join(root, name), exc))
                if config:
                    revmap = {}
                    for pkgname, versions in config.items():
                        for version, repodata in versions.items():
                            if not isinstance(version, string_types):
                                config[pkgname][str(version)] = \
                                    config[pkgname].pop(version)
                            revmap[repodata['full_name']] = pkgname
                    ret.setdefault('repo', {}).update(config)
                    ret.setdefault('name_map', {}).update(revmap)
    with salt.utils.fopen(os.path.join(repo, winrepo), 'w+b') as repo:
        repo.write(msgpack.dumps(ret))
    salt.output.display_output(ret, 'pprint', __opts__)
    return ret


def update_git_repos():
    '''
    Checkout git repos containing Windows Software Package Definitions

    .. note::

        This function will not work unless git is installed and the git module
        is further updated to work on Windows. In the meantime just place all
        Windows package files in the ``win_repo`` directory.
    '''
    ret = {}
    #mminion = salt.minion.MasterMinion(__opts__)
    repo = __opts__['win_repo']
    gitrepos = __opts__['win_gitrepos']
    for gitrepo in gitrepos:
        #if '/' in gitrepo:
            #targetname = gitrepo.split('/')[-1]
        #else:
            #targetname = gitrepo
        targetname = gitrepo
        rev = None
        # If a revision is specified, use it.
        if len(gitrepo.strip().split(' ')) > 1:
            rev, gitrepo = gitrepo.strip().split(' ')
        gittarget = os.path.join(repo, targetname)
        #result = mminion.states['git.latest'](gitrepo,
        result = __salt__['git.latest'](gitrepo,
                                        rev=rev,
                                        target=gittarget,
                                        force=True)
        ret[result['name']] = result['result']
    salt.output.display_output(ret, 'pprint', __opts__)
    return ret
