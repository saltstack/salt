# -*- coding: utf-8 -*-
'''
Manage Windows Package Repository
'''
from __future__ import absolute_import

# Python Libs
import os
import stat
import itertools

# Salt Modules
import salt.runner
import salt.config


def __virtual__():
    return 'winrepo'


def genrepo(name, force=False, allow_empty=False):
    '''
    Refresh the winrepo.p file of the repository (salt-run winrepo.genrepo)

    If ``force`` is ``True`` no checks will be made and the repository will be
    generated if ``allow_empty`` is ``True`` then the state will not return an
    error if there are 0 packages,

    .. note::

        This state only loads on minions that have the ``roles: salt-master``
        grain set.

    Example:

    .. code-block:: yaml

        winrepo:
          winrepo.genrepo
    '''

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    master_config = salt.config.master_config(os.path.join(salt.syspaths.CONFIG_DIR, 'master'))
    win_repo = master_config['win_repo']
    win_repo_mastercachefile = master_config['win_repo_mastercachefile']

    # Check if the win_repo directory exists
    # if not search for a file with a newer mtime than the win_repo_mastercachefile file
    execute = False
    if not force:
        if not os.path.exists(win_repo):
            ret['result'] = False
            ret['comment'] = 'missing {0}'.format(win_repo)
            return ret
        elif not os.path.exists(win_repo_mastercachefile):
            execute = True
            ret['comment'] = 'missing {0}'.format(win_repo_mastercachefile)
        else:
            win_repo_mastercachefile_mtime = os.stat(win_repo_mastercachefile)[stat.ST_MTIME]
            for root, dirs, files in os.walk(win_repo):
                for name in itertools.chain(files, dirs):
                    full_path = os.path.join(root, name)
                    if os.stat(full_path)[stat.ST_MTIME] > win_repo_mastercachefile_mtime:
                        ret['comment'] = 'mtime({0}) < mtime({1})'.format(win_repo_mastercachefile, full_path)
                        execute = True
                        break

    if __opts__['test']:
        ret['result'] = None
        return ret

    if not execute and not force:
        return ret

    runner = salt.runner.RunnerClient(master_config)
    runner_ret = runner.cmd('winrepo.genrepo', [])
    ret['changes'] = {'winrepo': runner_ret}
    if isinstance(runner_ret, dict) and runner_ret == {} and not allow_empty:
        os.remove(win_repo_mastercachefile)
        ret['result'] = False
        ret['comment'] = 'winrepo.genrepo returned empty'
    return ret
