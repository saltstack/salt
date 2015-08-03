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
from salt.exceptions import FileserverConfigError, SaltRenderError
import salt.utils
import salt.utils.gitfs
import logging
import salt.minion
import salt.loader
import salt.template

log = logging.getLogger(__name__)

PER_REMOTE_PARAMS = ('branch', 'root', 'ssl_verify')


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
                    log.debug(
                        'Failed to render {0}.'.format(
                            os.path.join(root, name)
                        )
                    )
                    log.debug('Error: {0}.'.format(exc))
                    continue
                if config:
                    revmap = {}
                    for pkgname, versions in six.iteritems(config):
                        log.info(
                            'Compiling winrepo data for package \'{0}\''
                            .format(pkgname)
                        )
                        for version, repodata in six.iteritems(versions):
                            log.info(
                                'Compiling winrepo data for {0} version {1}'
                                .format(pkgname, version)
                            )
                            log.info(repodata)
                            if not isinstance(version, six.string_types):
                                config[pkgname][str(version)] = \
                                    config[pkgname].pop(version)
                            if not isinstance(repodata, dict):
                                log.debug(
                                    'Failed to compile {0}.'.format(
                                        os.path.join(root, name)
                                    )
                                )
                                __jid_event__.fire_event(
                                    {'error': 'Failed to compile {0}.'.format(
                                        os.path.join(root, name))},
                                    'progress')
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
    if not any((salt.utils.gitfs.HAS_GITPYTHON, salt.utils.gitfs.HAS_PYGIT2)):
        # Use legacy code
        repo = __opts__['win_repo']
        salt.utils.warn_until(
            'Carbon',
            'winrepo git support now requires either GitPython or pygit2. '
            'Please install either GitPython >= {0} (or pygit2 >= {1} with '
            'libgit2 >= {2}), clear out the win_repo directory ({3}), and '
            'restart the salt-master service.'.format(
                salt.utils.gitfs.GITPYTHON_MINVER,
                salt.utils.gitfs.PYGIT2_MINVER,
                salt.utils.gitfs.LIBGIT2_MINVER,
                repo
            )
        )
        ret = {}
        gitrepos = __opts__['win_gitrepos']
        mminion = salt.minion.MasterMinion(__opts__)
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
    else:
        # New winrepo code utilizing salt.utils.gitfs
        try:
            winrepo = salt.utils.gitfs.WinRepo(__opts__)
            winrepo.init_remotes(__opts__['win_gitrepos'], PER_REMOTE_PARAMS)
            winrepo.fetch_remotes()
            winrepo.checkout()
        except Exception as exc:
            msg = 'Failed to update win_gitrepos: {0}'.format(exc)
            log.error(msg, exc_info_on_loglevel=logging.DEBUG)
            return msg
        return winrepo.win_repo_dirs
