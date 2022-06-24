"""
Return cached data from minions
"""

import fnmatch
import logging
import os

import salt.cache
import salt.config
import salt.fileserver.gitfs
import salt.payload
import salt.pillar.git_pillar
import salt.runners.winrepo
import salt.utils.args
import salt.utils.gitfs
import salt.utils.master
from salt.exceptions import SaltInvocationError
from salt.fileserver import clear_lock as _clear_lock

log = logging.getLogger(__name__)

__func_alias__ = {
    "list_": "list",
}


def grains(tgt, tgt_type="glob", **kwargs):
    """
    .. versionchanged:: 2017.7.0
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Return cached grains of the targeted minions.

    tgt
        Target to match minion ids.

        .. versionchanged:: 2017.7.5,2018.3.0
            The ``tgt`` argument is now required to display cached grains. If
            not used, the function will not return grains. This optional
            argument will become mandatory in the Salt ``3001`` release.

    tgt_type
        The type of targeting to use for matching, such as ``glob``, ``list``,
        etc.

    CLI Example:

    .. code-block:: bash

        salt-run cache.grains '*'
    """
    pillar_util = salt.utils.master.MasterPillarUtil(
        tgt, tgt_type, use_cached_grains=True, grains_fallback=False, opts=__opts__
    )
    cached_grains = pillar_util.get_minion_grains()
    return cached_grains


def pillar(tgt=None, tgt_type="glob", **kwargs):
    """
    .. versionchanged:: 2017.7.0
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Return cached pillars of the targeted minions if tgt is set.
    If tgt is not set will return cached pillars for all minions.

    CLI Example:

    .. code-block:: bash

        salt-run cache.pillar
    """
    pillar_util = salt.utils.master.MasterPillarUtil(
        tgt,
        tgt_type,
        use_cached_grains=True,
        grains_fallback=False,
        use_cached_pillar=True,
        pillar_fallback=False,
        opts=__opts__,
    )
    cached_pillar = pillar_util.get_minion_pillar()
    return cached_pillar


def mine(tgt=None, tgt_type="glob", **kwargs):
    """
    .. versionchanged:: 2017.7.0
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Return cached mine data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.mine
    """
    pillar_util = salt.utils.master.MasterPillarUtil(
        tgt,
        tgt_type,
        use_cached_grains=False,
        grains_fallback=False,
        use_cached_pillar=False,
        pillar_fallback=False,
        opts=__opts__,
    )
    cached_mine = pillar_util.get_cached_mine_data()
    return cached_mine


def _clear_cache(
    tgt=None,
    tgt_type="glob",
    clear_pillar_flag=False,
    clear_grains_flag=False,
    clear_mine_flag=False,
    clear_mine_func_flag=None,
):
    """
    Clear the cached data/files for the targeted minions.
    """
    if tgt is None:
        return False

    pillar_util = salt.utils.master.MasterPillarUtil(
        tgt,
        tgt_type,
        use_cached_grains=True,
        grains_fallback=False,
        use_cached_pillar=True,
        pillar_fallback=False,
        opts=__opts__,
    )
    return pillar_util.clear_cached_minion_data(
        clear_pillar=clear_pillar_flag,
        clear_grains=clear_grains_flag,
        clear_mine=clear_mine_flag,
        clear_mine_func=clear_mine_func_flag,
    )


def clear_pillar(tgt=None, tgt_type="glob"):
    """
    .. versionchanged:: 2017.7.0
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Clear the cached pillar data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_pillar
    """
    return _clear_cache(tgt, tgt_type, clear_pillar_flag=True)


def clear_grains(tgt=None, tgt_type="glob"):
    """
    .. versionchanged:: 2017.7.0
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Clear the cached grains data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_grains
    """
    return _clear_cache(tgt, tgt_type, clear_grains_flag=True)


def clear_mine(tgt=None, tgt_type="glob"):
    """
    .. versionchanged:: 2017.7.0
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Clear the cached mine data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_mine
    """
    return _clear_cache(tgt, tgt_type, clear_mine_flag=True)


def clear_mine_func(tgt=None, tgt_type="glob", clear_mine_func_flag=None):
    """
    .. versionchanged:: 2017.7.0
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Clear the cached mine function data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_mine_func tgt='*' clear_mine_func_flag='network.interfaces'
    """
    return _clear_cache(tgt, tgt_type, clear_mine_func_flag=clear_mine_func_flag)


def clear_all(tgt=None, tgt_type="glob"):
    """
    .. versionchanged:: 2017.7.0
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Clear the cached pillar, grains, and mine data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_all
    """
    return _clear_cache(
        tgt,
        tgt_type,
        clear_pillar_flag=True,
        clear_grains_flag=True,
        clear_mine_flag=True,
    )


def clear_git_lock(role, remote=None, **kwargs):
    """
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

    type : update,checkout,mountpoint
        The types of lock to clear. Can be one or more of ``update``,
        ``checkout``, and ``mountpoint``, and can be passed either as a
        comma-separated or Python list.

        .. versionadded:: 2015.8.8
        .. versionchanged:: 2018.3.0
            ``mountpoint`` lock type added

    CLI Examples:

    .. code-block:: bash

        salt-run cache.clear_git_lock gitfs
        salt-run cache.clear_git_lock git_pillar
        salt-run cache.clear_git_lock git_pillar type=update
        salt-run cache.clear_git_lock git_pillar type=update,checkout
        salt-run cache.clear_git_lock git_pillar type='["update", "mountpoint"]'
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    type_ = salt.utils.args.split_input(
        kwargs.pop("type", ["update", "checkout", "mountpoint"])
    )
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)

    if role == "gitfs":
        git_objects = [
            salt.utils.gitfs.GitFS(
                __opts__,
                __opts__["gitfs_remotes"],
                per_remote_overrides=salt.fileserver.gitfs.PER_REMOTE_OVERRIDES,
                per_remote_only=salt.fileserver.gitfs.PER_REMOTE_ONLY,
            )
        ]
    elif role == "git_pillar":
        git_objects = []
        for ext_pillar in __opts__["ext_pillar"]:
            key = next(iter(ext_pillar))
            if key == "git":
                if not isinstance(ext_pillar["git"], list):
                    continue
                obj = salt.utils.gitfs.GitPillar(
                    __opts__,
                    ext_pillar["git"],
                    per_remote_overrides=salt.pillar.git_pillar.PER_REMOTE_OVERRIDES,
                    per_remote_only=salt.pillar.git_pillar.PER_REMOTE_ONLY,
                    global_only=salt.pillar.git_pillar.GLOBAL_ONLY,
                )
                git_objects.append(obj)
    elif role == "winrepo":
        winrepo_dir = __opts__["winrepo_dir"]
        winrepo_remotes = __opts__["winrepo_remotes"]

        git_objects = []
        for remotes, base_dir in (
            (winrepo_remotes, winrepo_dir),
            (__opts__["winrepo_remotes_ng"], __opts__["winrepo_dir_ng"]),
        ):
            obj = salt.utils.gitfs.WinRepo(
                __opts__,
                remotes,
                per_remote_overrides=salt.runners.winrepo.PER_REMOTE_OVERRIDES,
                per_remote_only=salt.runners.winrepo.PER_REMOTE_ONLY,
                global_only=salt.runners.winrepo.GLOBAL_ONLY,
                cache_root=base_dir,
            )
            git_objects.append(obj)
    else:
        raise SaltInvocationError("Invalid role '{}'".format(role))

    ret = {}
    for obj in git_objects:
        for lock_type in type_:
            cleared, errors = _clear_lock(
                obj.clear_lock, role, remote=remote, lock_type=lock_type
            )
            if cleared:
                ret.setdefault("cleared", []).extend(cleared)
            if errors:
                ret.setdefault("errors", []).extend(errors)
    if not ret:
        return "No locks were removed"
    return ret


def cloud(tgt, provider=None):
    """
    Return cloud cache data for target.

    .. note:: Only works with glob matching

    tgt
      Glob Target to match minion ids

    provider
      Cloud Provider

    CLI Example:

    .. code-block:: bash

        salt-run cache.cloud 'salt*'
        salt-run cache.cloud glance.example.org provider=openstack
    """
    if not isinstance(tgt, str):
        return {}

    opts = salt.config.cloud_config(
        os.path.join(os.path.dirname(__opts__["conf_file"]), "cloud")
    )
    if not opts.get("update_cachedir"):
        return {}

    cloud_cache = __utils__["cloud.list_cache_nodes_full"](opts=opts, provider=provider)
    if cloud_cache is None:
        return {}

    ret = {}
    for driver, providers in cloud_cache.items():
        for provider, servers in providers.items():
            for name, data in servers.items():
                if fnmatch.fnmatch(name, tgt):
                    ret[name] = data
                    ret[name]["provider"] = provider
    return ret


def store(bank, key, data, cachedir=None):
    """
    Lists entries stored in the specified bank.

    CLI Example:

    .. code-block:: bash

        salt-run cache.store mycache mykey 'The time has come the walrus said'
    """
    if cachedir is None:
        cachedir = __opts__["cachedir"]

    try:
        cache = salt.cache.Cache(__opts__, cachedir=cachedir)
    except TypeError:
        cache = salt.cache.Cache(__opts__)
    return cache.store(bank, key, data)


def list_(bank, cachedir=None):
    """
    Lists entries stored in the specified bank.

    CLI Example:

    .. code-block:: bash

        salt-run cache.list cloud/active/ec2/myec2 cachedir=/var/cache/salt/
    """
    if cachedir is None:
        cachedir = __opts__["cachedir"]

    try:
        cache = salt.cache.Cache(__opts__, cachedir=cachedir)
    except TypeError:
        cache = salt.cache.Cache(__opts__)
    return cache.list(bank)


def fetch(bank, key, cachedir=None):
    """
    Fetch data from a salt.cache bank.

    CLI Example:

    .. code-block:: bash

        salt-run cache.fetch cloud/active/ec2/myec2 myminion cachedir=/var/cache/salt/
    """
    if cachedir is None:
        cachedir = __opts__["cachedir"]

    try:
        cache = salt.cache.Cache(__opts__, cachedir=cachedir)
    except TypeError:
        cache = salt.cache.Cache(__opts__)
    return cache.fetch(bank, key)


def flush(bank, key=None, cachedir=None):
    """
    Remove the key from the cache bank with all the key content. If no key is
    specified remove the entire bank with all keys and sub-banks inside.

    CLI Examples:

    .. code-block:: bash

        salt-run cache.flush cloud/active/ec2/myec2 cachedir=/var/cache/salt/
        salt-run cache.flush cloud/active/ec2/myec2 myminion cachedir=/var/cache/salt/
    """
    if cachedir is None:
        cachedir = __opts__["cachedir"]

    try:
        cache = salt.cache.Cache(__opts__, cachedir=cachedir)
    except TypeError:
        cache = salt.cache.Cache(__opts__)
    return cache.flush(bank, key)
