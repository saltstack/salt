# -*- coding: utf-8 -*-
'''
Directly manage the Salt fileserver plugins
'''

# Import Salt libs
import salt.fileserver


def envs(backend=None, sources=False, outputter='nested'):
    '''
    Return the available fileserver environments. If no backend is provided,
    then the environments for all configured backends will be returned.

    backend
        Narrow fileserver backends to a subset of the enabled ones.

        .. versionchanged:: 2015.2.0::
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
        salt-run fileserver.envs outputter=nested
        salt-run fileserver.envs backend=roots,git
        salt-run fileserver.envs git
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    output = fileserver.envs(back=backend, sources=sources)

    if outputter:
        salt.output.display_output(output, outputter, opts=__opts__)
    return output


def file_list(saltenv='base', backend=None, outputter='nested'):
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

        .. versionadded:: 2015.2.0

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
    output = fileserver.file_list(load=load)

    if outputter:
        salt.output.display_output(output, outputter, opts=__opts__)
    return output


def symlink_list(saltenv='base', backend=None, outputter='nested'):
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

        .. versionadded:: 2015.2.0

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
    output = fileserver.symlink_list(load=load)

    if outputter:
        salt.output.display_output(output, outputter, opts=__opts__)
    return output


def dir_list(saltenv='base', backend=None, outputter='nested'):
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

        .. versionadded:: 2015.2.0

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
    output = fileserver.dir_list(load=load)

    if outputter:
        salt.output.display_output(output, outputter, opts=__opts__)
    return output


def empty_dir_list(saltenv='base', backend=None, outputter='nested'):
    '''
    .. versionadded:: 2015.2.0

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
    output = fileserver.file_list_emptydirs(load=load)

    if outputter:
        salt.output.display_output(output, outputter, opts=__opts__)
    return output


def update(backend=None):
    '''
    Update the fileserver cache. If no backend is provided, then the cache for
    all configured backends will be updated.

    backend
        Narrow fileserver backends to a subset of the enabled ones.

        .. versionchanged:: 2015.2.0
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
    .. versionadded:: 2015.2.0

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
        ret = 'No cache was cleared'
    salt.output.display_output(ret, 'nested', opts=__opts__)


def clear_lock(backend=None, remote=None):
    '''
    .. versionadded:: 2015.2.0

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
        If not None, then any remotes which contain the passed string will have
        their lock cleared. For example, a ``remote`` value of **github** will
        remove the lock from all github.com remotes.

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
        ret = 'No locks were removed'
    salt.output.display_output(ret, 'nested', opts=__opts__)


def lock(backend=None, remote=None):
    '''
    .. versionadded:: 2015.2.0

    Set a fileserver update lock for VCS fileserver backends (:mod:`git
    <salt.fileserver.gitfs>`, :mod:`hg <salt.fileserver.hgfs>`, :mod:`svn
    <salt.fileserver.svnfs>`).

    .. note::

        This will only operate on enabled backends (those configured in
        :master_conf:`fileserver_backend`).

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
        ret = 'No locks were set'
    salt.output.display_output(ret, 'nested', opts=__opts__)
