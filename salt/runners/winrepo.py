# -*- coding: utf-8 -*-
'''
Runner to manage Windows software repo
'''

# Import python libs
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
import salt.minion
from salt._compat import string_types

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
                        print 'Failed to compile {0}: {1}'.format(os.path.join(root, name), exc)
                if config:
                    revmap = {}
                    for pkgname, versions in config.iteritems():
                        for version, repodata in versions.iteritems():
                            if not isinstance(version, string_types):
                                config[pkgname][str(version)] = \
                                    config[pkgname].pop(version)
                            if not isinstance(repodata, dict):
                                log.debug('Failed to compile'
                                          '{0}.'.format(os.path.join(root, name)))
                                print 'Failed to compile {0}.'.format(os.path.join(root, name))
                                continue
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
    salt.output.display_output(ret, 'pprint', __opts__)
    return ret
