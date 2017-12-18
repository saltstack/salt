# -*- coding: utf-8 -*-
'''
Directly manage the Salt fileserver plugins
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.fileserver


def envs(backend=None, sources=False):
    '''
    Return the available fileserver environments. If no backend is provided,
    then the environments for all configured backends will be returned.

    backend
        Narrow fileserver backends to a subset of the enabled ones.

        .. versionchanged:: 2015.5.0
            If all passed backends start with a minus sign (``-``), then these
            backends will be excluded from the enabled backends. However, if
            there is a mix of backends with and without a minus sign (ex:
            ``backend=-roots,git``) then the ones starting with a minus
            sign will be disregarded.

            Additionally, fileserver backends can now be passed as a
            comma-separated list. In earlier versions, they needed to be passed
            as a python list (ex: ``backend="['roots', 'git']"``)

    CLI Example:

    .. code-block:: bash

        salt-run fileserver.envs
        salt-run fileserver.envs backend=roots,git
        salt-run fileserver.envs git
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    return sorted(fileserver.envs(back=backend, sources=sources))


def clear_file_list_cache(saltenv=None, backend=None):
    '''
    .. versionadded:: 2016.11.0

    The Salt fileserver caches the files/directories/symlinks for each
    fileserver backend and environment as they are requested. This is done to
    help the fileserver scale better. Without this caching, when
    hundreds/thousands of minions simultaneously ask the master what files are
    available, this would cause the master's CPU load to spike as it obtains
    the same information separately for each minion.

    saltenv
        By default, this runner will clear the file list caches for all
        environments. This argument allows for a list of environments to be
        passed, to clear more selectively. This list can be passed either as a
        comma-separated string, or a Python list.

    backend
        Similar to the ``saltenv`` parameter, this argument will restrict the
        cache clearing to specific fileserver backends (the default behavior is
        to clear from all enabled fileserver backends). This list can be passed
        either as a comma-separated string, or a Python list.

    .. note:
        The maximum age for the cached file lists (i.e. the age at which the
        cache will be disregarded and rebuilt) is defined by the
        :conf_master:`fileserver_list_cache_time` configuration parameter.

    Since the ability to clear these caches is often required by users writing
    custom runners which add/remove files, this runner can easily be called
    from within a custom runner using any of the following examples:

    .. code-block:: python

        # Clear all file list caches
        __salt__['fileserver.clear_file_list_cache']()
        # Clear just the 'base' saltenv file list caches
        __salt__['fileserver.clear_file_list_cache'](saltenv='base')
        # Clear just the 'base' saltenv file list caches from just the 'roots'
        # fileserver backend
        __salt__['fileserver.clear_file_list_cache'](saltenv='base', backend='roots')
        # Clear all file list caches from the 'roots' fileserver backend
        __salt__['fileserver.clear_file_list_cache'](backend='roots')

    .. note::
        In runners, the ``__salt__`` dictionary will likely be renamed to
        ``__runner__`` in a future Salt release to distinguish runner functions
        from remote execution functions. See `this GitHub issue`_ for
        discussion/updates on this.

    .. _`this GitHub issue`: https://github.com/saltstack/salt/issues/34958

    If using Salt's Python API (not a runner), the following examples are
    equivalent to the ones above:

    .. code-block:: python

        import salt.config
        import salt.runner

        opts = salt.config.master_config('/etc/salt/master')
        opts['fun'] = 'fileserver.clear_file_list_cache'

        # Clear all file list_caches
        opts['arg'] = []  # No arguments
        runner = salt.runner.Runner(opts)
        cleared = runner.run()

        # Clear just the 'base' saltenv file list caches
        opts['arg'] = ['base', None]
        runner = salt.runner.Runner(opts)
        cleared = runner.run()

        # Clear just the 'base' saltenv file list caches from just the 'roots'
        # fileserver backend
        opts['arg'] = ['base', 'roots']
        runner = salt.runner.Runner(opts)
        cleared = runner.run()

        # Clear all file list caches from the 'roots' fileserver backend
        opts['arg'] = [None, 'roots']
        runner = salt.runner.Runner(opts)
        cleared = runner.run()


    This function will return a dictionary showing a list of environments which
    were cleared for each backend. An empty return dictionary means that no
    changes were made.

    CLI Examples:

    .. code-block:: bash

        # Clear all file list caches
        salt-run fileserver.clear_file_list_cache
        # Clear just the 'base' saltenv file list caches
        salt-run fileserver.clear_file_list_cache saltenv=base
        # Clear just the 'base' saltenv file list caches from just the 'roots'
        # fileserver backend
        salt-run fileserver.clear_file_list_cache saltenv=base backend=roots
        # Clear all file list caches from the 'roots' fileserver backend
        salt-run fileserver.clear_file_list_cache backend=roots
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    load = {'saltenv': saltenv, 'fsbackend': backend}
    return fileserver.clear_file_list_cache(load=load)


def file_list(saltenv='base', backend=None):
    '''
    Return a list of files from the salt fileserver

    saltenv : base
        The salt fileserver environment to be listed

    backend
        Narrow fileserver backends to a subset of the enabled ones. If all
        passed backends start with a minus sign (``-``), then these backends
        will be excluded from the enabled backends. However, if there is a mix
        of backends with and without a minus sign (ex:
        ``backend=-roots,git``) then the ones starting with a minus sign will
        be disregarded.

        .. versionadded:: 2015.5.0

    CLI Examples:

    .. code-block:: bash

        salt-run fileserver.file_list
        salt-run fileserver.file_list saltenv=prod
        salt-run fileserver.file_list saltenv=dev backend=git
        salt-run fileserver.file_list base hg,roots
        salt-run fileserver.file_list -git
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    load = {'saltenv': saltenv, 'fsbackend': backend}
    return fileserver.file_list(load=load)


def symlink_list(saltenv='base', backend=None):
    '''
    Return a list of symlinked files and dirs

    saltenv : base
        The salt fileserver environment to be listed

    backend
        Narrow fileserver backends to a subset of the enabled ones. If all
        passed backends start with a minus sign (``-``), then these backends
        will be excluded from the enabled backends. However, if there is a mix
        of backends with and without a minus sign (ex:
        ``backend=-roots,git``) then the ones starting with a minus sign will
        be disregarded.

        .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt-run fileserver.symlink_list
        salt-run fileserver.symlink_list saltenv=prod
        salt-run fileserver.symlink_list saltenv=dev backend=git
        salt-run fileserver.symlink_list base hg,roots
        salt-run fileserver.symlink_list -git
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    load = {'saltenv': saltenv, 'fsbackend': backend}
    return fileserver.symlink_list(load=load)


def dir_list(saltenv='base', backend=None):
    '''
    Return a list of directories in the given environment

    saltenv : base
        The salt fileserver environment to be listed

    backend
        Narrow fileserver backends to a subset of the enabled ones. If all
        passed backends start with a minus sign (``-``), then these backends
        will be excluded from the enabled backends. However, if there is a mix
        of backends with and without a minus sign (ex:
        ``backend=-roots,git``) then the ones starting with a minus sign will
        be disregarded.

        .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt-run fileserver.dir_list
        salt-run fileserver.dir_list saltenv=prod
        salt-run fileserver.dir_list saltenv=dev backend=git
        salt-run fileserver.dir_list base hg,roots
        salt-run fileserver.dir_list -git
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    load = {'saltenv': saltenv, 'fsbackend': backend}
    return fileserver.dir_list(load=load)


def empty_dir_list(saltenv='base', backend=None):
    '''
    .. versionadded:: 2015.5.0

    Return a list of empty directories in the given environment

    saltenv : base
        The salt fileserver environment to be listed

    backend
        Narrow fileserver backends to a subset of the enabled ones. If all
        passed backends start with a minus sign (``-``), then these backends
        will be excluded from the enabled backends. However, if there is a mix
        of backends with and without a minus sign (ex:
        ``backend=-roots,git``) then the ones starting with a minus sign will
        be disregarded.

        .. note::

            Some backends (such as :mod:`git <salt.fileserver.gitfs>` and
            :mod:`hg <salt.fileserver.hgfs>`) do not support empty directories.
            So, passing ``backend=git`` or ``backend=hg`` will result in an
            empty list being returned.

    CLI Example:

    .. code-block:: bash

        salt-run fileserver.empty_dir_list
        salt-run fileserver.empty_dir_list saltenv=prod
        salt-run fileserver.empty_dir_list backend=roots
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    load = {'saltenv': saltenv, 'fsbackend': backend}
    return fileserver.file_list_emptydirs(load=load)


def update(backend=None):
    '''
    Update the fileserver cache. If no backend is provided, then the cache for
    all configured backends will be updated.

    backend
        Narrow fileserver backends to a subset of the enabled ones.

        .. versionchanged:: 2015.5.0
            If all passed backends start with a minus sign (``-``), then these
            backends will be excluded from the enabled backends. However, if
            there is a mix of backends with and without a minus sign (ex:
            ``backend=-roots,git``) then the ones starting with a minus
            sign will be disregarded.

            Additionally, fileserver backends can now be passed as a
            comma-separated list. In earlier versions, they needed to be passed
            as a python list (ex: ``backend="['roots', 'git']"``)

    CLI Example:

    .. code-block:: bash

        salt-run fileserver.update
        salt-run fileserver.update backend=roots,git
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    fileserver.update(back=backend)
    return True


def clear_cache(backend=None):
    '''
    .. versionadded:: 2015.5.0

    Clear the fileserver cache from VCS fileserver backends (:mod:`git
    <salt.fileserver.gitfs>`, :mod:`hg <salt.fileserver.hgfs>`, :mod:`svn
    <salt.fileserver.svnfs>`). Executing this runner with no arguments will
    clear the cache for all enabled VCS fileserver backends, but this
    can be narrowed using the ``backend`` argument.

    backend
        Only clear the update lock for the specified backend(s). If all passed
        backends start with a minus sign (``-``), then these backends will be
        excluded from the enabled backends. However, if there is a mix of
        backends with and without a minus sign (ex: ``backend=-roots,git``)
        then the ones starting with a minus sign will be disregarded.

    CLI Example:

    .. code-block:: bash

        salt-run fileserver.clear_cache
        salt-run fileserver.clear_cache backend=git,hg
        salt-run fileserver.clear_cache hg
        salt-run fileserver.clear_cache -roots
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    cleared, errors = fileserver.clear_cache(back=backend)
    ret = {}
    if cleared:
        ret['cleared'] = cleared
    if errors:
        ret['errors'] = errors
    if not ret:
        return 'No cache was cleared'
    return ret


def clear_lock(backend=None, remote=None):
    '''
    .. versionadded:: 2015.5.0

    Clear the fileserver update lock from VCS fileserver backends (:mod:`git
    <salt.fileserver.gitfs>`, :mod:`hg <salt.fileserver.hgfs>`, :mod:`svn
    <salt.fileserver.svnfs>`). This should only need to be done if a fileserver
    update was interrupted and a remote is not updating (generating a warning
    in the Master's log file). Executing this runner with no arguments will
    remove all update locks from all enabled VCS fileserver backends, but this
    can be narrowed by using the following arguments:

    backend
        Only clear the update lock for the specified backend(s).

    remote
        If specified, then any remotes which contain the passed string will
        have their lock cleared. For example, a ``remote`` value of **github**
        will remove the lock from all github.com remotes.

    CLI Example:

    .. code-block:: bash

        salt-run fileserver.clear_lock
        salt-run fileserver.clear_lock backend=git,hg
        salt-run fileserver.clear_lock backend=git remote=github
        salt-run fileserver.clear_lock remote=bitbucket
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    cleared, errors = fileserver.clear_lock(back=backend, remote=remote)
    ret = {}
    if cleared:
        ret['cleared'] = cleared
    if errors:
        ret['errors'] = errors
    if not ret:
        return 'No locks were removed'
    return ret


def lock(backend=None, remote=None):
    '''
    .. versionadded:: 2015.5.0

    Set a fileserver update lock for VCS fileserver backends (:mod:`git
    <salt.fileserver.gitfs>`, :mod:`hg <salt.fileserver.hgfs>`, :mod:`svn
    <salt.fileserver.svnfs>`).

    .. note::

        This will only operate on enabled backends (those configured in
        :conf_master:`fileserver_backend`).

    backend
        Only set the update lock for the specified backend(s).

    remote
        If not None, then any remotes which contain the passed string will have
        their lock cleared. For example, a ``remote`` value of ``*github.com*``
        will remove the lock from all github.com remotes.

    CLI Example:

    .. code-block:: bash

        salt-run fileserver.lock
        salt-run fileserver.lock backend=git,hg
        salt-run fileserver.lock backend=git remote='*github.com*'
        salt-run fileserver.lock remote=bitbucket
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    locked, errors = fileserver.lock(back=backend, remote=remote)
    ret = {}
    if locked:
        ret['locked'] = locked
    if errors:
        ret['errors'] = errors
    if not ret:
        return 'No locks were set'
    return ret
