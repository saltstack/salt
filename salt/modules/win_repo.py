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
    renderers = salt.loader.render(__opts__, __salt__)
    for root, dirs, files in os.walk(repo):
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
