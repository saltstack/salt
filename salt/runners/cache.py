# -*- coding: utf-8 -*-
'''
Return cached data from minions
'''
from __future__ import absolute_import
# Import python libs
import logging

# Import salt libs
import salt.log
import salt.utils
import salt.utils.master
import salt.payload
from salt.exceptions import SaltInvocationError
from salt.fileserver import clear_lock as _clear_lock
from salt.fileserver.gitfs import PER_REMOTE_OVERRIDES as __GITFS_OVERRIDES
from salt.pillar.git_pillar \
    import PER_REMOTE_OVERRIDES as __GIT_PILLAR_OVERRIDES
from salt.runners.winrepo import PER_REMOTE_OVERRIDES as __WINREPO_OVERRIDES

log = logging.getLogger(__name__)


def grains(tgt=None, tgt_type='glob', **kwargs):
    '''
    .. versionchanged:: Nitrogen
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Return cached grains of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.grains
    '''
    if 'expr_form' in kwargs:
        salt.utils.warn_until(
            'Fluorine',
            'The target type should be passed using the \'tgt_type\' '
            'argument instead of \'expr_form\'. Support for using '
            '\'expr_form\' will be removed in Salt Fluorine.'
        )
        tgt_type = kwargs.pop('expr_form')

    pillar_util = salt.utils.master.MasterPillarUtil(tgt, tgt_type,
                                                     use_cached_grains=True,
                                                     grains_fallback=False,
                                                     opts=__opts__)
    cached_grains = pillar_util.get_minion_grains()
    return cached_grains


def pillar(tgt=None, tgt_type='glob', **kwargs):
    '''
    .. versionchanged:: Nitrogen
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Return cached pillars of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.pillar
    '''
    if 'expr_form' in kwargs:
        salt.utils.warn_until(
            'Fluorine',
            'The target type should be passed using the \'tgt_type\' '
            'argument instead of \'expr_form\'. Support for using '
            '\'expr_form\' will be removed in Salt Fluorine.'
        )
        tgt_type = kwargs.pop('expr_form')

    pillar_util = salt.utils.master.MasterPillarUtil(tgt, tgt_type,
                                                     use_cached_grains=True,
                                                     grains_fallback=False,
                                                     use_cached_pillar=True,
                                                     pillar_fallback=False,
                                                     opts=__opts__)
    cached_pillar = pillar_util.get_minion_pillar()
    return cached_pillar


def mine(tgt=None, tgt_type='glob', **kwargs):
    '''
    .. versionchanged:: Nitrogen
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Return cached mine data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.mine
    '''
    if 'expr_form' in kwargs:
        salt.utils.warn_until(
            'Fluorine',
            'The target type should be passed using the \'tgt_type\' '
            'argument instead of \'expr_form\'. Support for using '
            '\'expr_form\' will be removed in Salt Fluorine.'
        )
        tgt_type = kwargs.pop('expr_form')

    pillar_util = salt.utils.master.MasterPillarUtil(tgt, tgt_type,
                                                     use_cached_grains=False,
                                                     grains_fallback=False,
                                                     use_cached_pillar=False,
                                                     pillar_fallback=False,
                                                     opts=__opts__)
    cached_mine = pillar_util.get_cached_mine_data()
    return cached_mine


def _clear_cache(tgt=None,
                 tgt_type='glob',
                 clear_pillar_flag=False,
                 clear_grains_flag=False,
                 clear_mine_flag=False,
                 clear_mine_func_flag=None):
    '''
    Clear the cached data/files for the targeted minions.
    '''
    if tgt is None:
        return False
    pillar_util = salt.utils.master.MasterPillarUtil(tgt, tgt_type,
                                                     use_cached_grains=True,
                                                     grains_fallback=False,
                                                     use_cached_pillar=True,
                                                     pillar_fallback=False,
                                                     opts=__opts__)
    return pillar_util.clear_cached_minion_data(clear_pillar=clear_pillar_flag,
                                                clear_grains=clear_grains_flag,
                                                clear_mine=clear_mine_flag,
                                                clear_mine_func=clear_mine_func_flag)


def clear_pillar(tgt=None, tgt_type='glob', expr_form=None):
    '''
    .. versionchanged:: Nitrogen
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Clear the cached pillar data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_pillar
    '''
    # remember to remove the expr_form argument from this function when
    # performing the cleanup on this deprecation.
    if expr_form is not None:
        salt.utils.warn_until(
            'Fluorine',
            'the target type should be passed using the \'tgt_type\' '
            'argument instead of \'expr_form\'. Support for using '
            '\'expr_form\' will be removed in Salt Fluorine.'
        )
        tgt_type = expr_form

    return _clear_cache(tgt, tgt_type, clear_pillar_flag=True)


def clear_grains(tgt=None, tgt_type='glob', expr_form=None):
    '''
    .. versionchanged:: Nitrogen
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Clear the cached grains data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_grains
    '''
    # remember to remove the expr_form argument from this function when
    # performing the cleanup on this deprecation.
    if expr_form is not None:
        salt.utils.warn_until(
            'Fluorine',
            'the target type should be passed using the \'tgt_type\' '
            'argument instead of \'expr_form\'. Support for using '
            '\'expr_form\' will be removed in Salt Fluorine.'
        )
        tgt_type = expr_form

    return _clear_cache(tgt, tgt_type, clear_grains_flag=True)


def clear_mine(tgt=None, tgt_type='glob', expr_form=None):
    '''
    .. versionchanged:: Nitrogen
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Clear the cached mine data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_mine
    '''
    # remember to remove the expr_form argument from this function when
    # performing the cleanup on this deprecation.
    if expr_form is not None:
        salt.utils.warn_until(
            'Fluorine',
            'the target type should be passed using the \'tgt_type\' '
            'argument instead of \'expr_form\'. Support for using '
            '\'expr_form\' will be removed in Salt Fluorine.'
        )
        tgt_type = expr_form

    return _clear_cache(tgt, tgt_type, clear_mine_flag=True)


def clear_mine_func(tgt=None,
                    tgt_type='glob',
                    clear_mine_func_flag=None,
                    expr_form=None):
    '''
    .. versionchanged:: Nitrogen
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Clear the cached mine function data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_mine_func tgt='*' clear_mine_func_flag='network.interfaces'
    '''
    return _clear_cache(tgt, tgt_type, clear_mine_func_flag=clear_mine_func_flag)


def clear_all(tgt=None, tgt_type='glob', expr_form=None):
    '''
    .. versionchanged:: Nitrogen
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Clear the cached pillar, grains, and mine data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_all
    '''
    # remember to remove the expr_form argument from this function when
    # performing the cleanup on this deprecation.
    if expr_form is not None:
        salt.utils.warn_until(
            'Fluorine',
            'the target type should be passed using the \'tgt_type\' '
            'argument instead of \'expr_form\'. Support for using '
            '\'expr_form\' will be removed in Salt Fluorine.'
        )
        tgt_type = expr_form

    return _clear_cache(tgt,
                        tgt_type,
                        clear_pillar_flag=True,
                        clear_grains_flag=True,
                        clear_mine_flag=True)


def clear_git_lock(role, remote=None, **kwargs):
    '''
    .. versionadded:: 2015.8.2

    Remove the update locks for Salt components (gitfs, git_pillar, winrepo)
    which use gitfs backend code from salt.utils.gitfs.

    .. note::
        Running :py:func:`cache.clear_all <salt.runners.cache.clear_all>` will
        not include this function as it does for pillar, grains, and mine.

        Additionally, executing this function with a ``role`` of ``gitfs`` is
        equivalent to running ``salt-run fileserver.clear_lock backend=git``.

    role
        Which type of lock to remove (``gitfs``, ``git_pillar``, or
        ``winrepo``)

    remote
        If specified, then any remotes which contain the passed string will
        have their lock cleared. For example, a ``remote`` value of **github**
        will remove the lock from all github.com remotes.

    type : update,checkout
        The types of lock to clear. Can be ``update``, ``checkout``, or both of
    et (either comma-separated or as a Python list).

        .. versionadded:: 2015.8.8

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_git_lock git_pillar
    '''
    kwargs = salt.utils.clean_kwargs(**kwargs)
    type_ = salt.utils.split_input(kwargs.pop('type', ['update', 'checkout']))
    if kwargs:
        salt.utils.invalid_kwargs(kwargs)

    if role == 'gitfs':
        git_objects = [salt.utils.gitfs.GitFS(__opts__)]
        git_objects[0].init_remotes(__opts__['gitfs_remotes'],
                                    __GITFS_OVERRIDES)
    elif role == 'git_pillar':
        git_objects = []
        for ext_pillar in __opts__['ext_pillar']:
            key = next(iter(ext_pillar))
            if key == 'git':
                if not isinstance(ext_pillar['git'], list):
                    continue
                obj = salt.utils.gitfs.GitPillar(__opts__)
                obj.init_remotes(ext_pillar['git'], __GIT_PILLAR_OVERRIDES)
                git_objects.append(obj)
    elif role == 'winrepo':
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

        git_objects = []
        for remotes, base_dir in (
            (winrepo_remotes, winrepo_dir),
            (__opts__['winrepo_remotes_ng'], __opts__['winrepo_dir_ng'])
        ):
            obj = salt.utils.gitfs.WinRepo(__opts__, base_dir)
            obj.init_remotes(remotes, __WINREPO_OVERRIDES)
            git_objects.append(obj)
    else:
        raise SaltInvocationError('Invalid role \'{0}\''.format(role))

    ret = {}
    for obj in git_objects:
        for lock_type in type_:
            cleared, errors = _clear_lock(obj.clear_lock,
                                          role,
                                          remote=remote,
                                          lock_type=lock_type)
            if cleared:
                ret.setdefault('cleared', []).extend(cleared)
            if errors:
                ret.setdefault('errors', []).extend(errors)
    if not ret:
        return 'No locks were removed'
    return ret
