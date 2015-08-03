# -*- coding: utf-8 -*-
'''
Runner to manage Windows software repo
'''

# Import python libs
from __future__ import absolute_import, print_function
import os

# Import third party libs
import salt.ext.six as six
try:
    import msgpack
except ImportError:
    import msgpack_pure as msgpack  # pylint: disable=import-error

# Import salt libs
from salt.exceptions import SaltRenderError
import salt.utils
import logging
import salt.minion
import salt.loader
import salt.template

log = logging.getLogger(__name__)


def genrepo():
    '''
    Generate win_repo_cachefile based on sls files in the win_repo

    CLI Example:

    .. code-block:: bash

        salt-run winrepo.genrepo
    '''
    ret = {}
    repo = __opts__['win_repo']
    if not os.path.exists(repo):
        os.makedirs(repo)
    winrepo = __opts__['win_repo_mastercachefile']
    renderers = salt.loader.render(__opts__, __salt__)
    for root, _, files in os.walk(repo):
        for name in files:
            if name.endswith('.sls'):
                try:
                    config = salt.template.compile_template(
                            os.path.join(root, name),
                            renderers,
                            __opts__['renderer'])
                except SaltRenderError as exc:
                    log.debug('Failed to render {0}.'.format(os.path.join(root, name)))
                    log.debug('Error: {0}.'.format(exc))
                    continue
                if config:
                    revmap = {}
                    for pkgname, versions in six.iteritems(config):
                        for version, repodata in six.iteritems(versions):
                            if not isinstance(version, six.string_types):
                                config[pkgname][str(version)] = \
                                    config[pkgname].pop(version)
                            if not isinstance(repodata, dict):
                                log.debug('Failed to compile'
                                          '{0}.'.format(os.path.join(root, name)))
                                __jid_event__.fire_event({'error': 'Failed to compile {0}.'.format(os.path.join(root, name))}, 'progress')
                                continue
                            revmap[repodata['full_name']] = pkgname
                    ret.setdefault('repo', {}).update(config)
                    ret.setdefault('name_map', {}).update(revmap)
    with salt.utils.fopen(os.path.join(repo, winrepo), 'w+b') as repo:
        repo.write(msgpack.dumps(ret))
    return ret


def update_git_repos():
    '''
    Checkout git repos containing Windows Software Package Definitions

    CLI Example:

    .. code-block:: bash

        salt-run winrepo.update_git_repos
    '''
    ret = {}
    mminion = salt.minion.MasterMinion(__opts__)
    repo = __opts__['win_repo']
    gitrepos = __opts__['win_gitrepos']
    for gitrepo in gitrepos:
        if '/' in gitrepo:
            targetname = gitrepo.split('/')[-1]
        else:
            targetname = gitrepo
        rev = None
        # If a revision is specified, use it.
        if len(gitrepo.strip().split(' ')) > 1:
            rev, gitrepo = gitrepo.strip().split(' ')
        gittarget = os.path.join(repo, targetname)
        result = mminion.states['git.latest'](gitrepo,
                                              rev=rev,
                                              target=gittarget,
                                              force=True)
        ret[result['name']] = result['result']
    return ret
