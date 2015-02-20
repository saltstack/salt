# -*- coding: utf-8 -*-
'''
Directly manage the Salt fileserver plugins
'''
from __future__ import absolute_import

# Import Salt libs
import salt.fileserver


def dir_list(saltenv='base', outputter='nested'):
    '''
    List all directories in the given environment

    CLI Example:

    .. code-block:: bash

        salt-run fileserver.dir_list
        salt-run fileserver.dir_list saltenv=prod
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    load = {'saltenv': saltenv}
    output = fileserver.dir_list(load=load)

    if outputter:
        return {'outputter': outputter, 'data': output}
    else:
        return output


def envs(backend=None, sources=False, outputter='nested'):
    '''
    Return the available fileserver environments. If no backend is provided,
    then the environments for all configured backends will be returned.

    CLI Example:

    .. code-block:: bash

        salt-run fileserver.envs
        salt-run fileserver.envs outputter=nested
        salt-run fileserver.envs backend=roots,git
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    output = fileserver.envs(back=backend, sources=sources)

    if outputter:
        return {'outputter': outputter, 'data': output}
    else:
        return output


def file_list(saltenv='base', outputter='nested'):
    '''
    Return a list of files from the dominant environment

    CLI Example:

    .. code-block:: bash

        salt-run fileserver.file_list
        salt-run fileserver.file_list saltenv=prod
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    load = {'saltenv': saltenv}
    output = fileserver.file_list(load=load)

    if outputter:
        return {'outputter': outputter, 'data': output}
    else:
        return output


def symlink_list(saltenv='base', outputter='nested'):
    '''
    Return a list of symlinked files and dirs

    CLI Example:

    .. code-block:: bash

        salt-run fileserver.symlink_list
        salt-run fileserver.symlink_list saltenv=prod
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    load = {'saltenv': saltenv}
    output = fileserver.symlink_list(load=load)

    if outputter:
        return {'outputter': outputter, 'data': output}
    else:
        return output


def update(backend=None):
    '''
    Update the fileserver cache. If no backend is provided, then the cache for
    all configured backends will be updated.

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

    Clear the fileserver cache. If no backend is provided, then the cache for
    all configured backends will be cleared, provided the backend has a
    ``clear_cache()`` function. This currently only includes the VCS backends
    (:mod:`git <salt.fileserver.gitfs>`, :mod:`hg <salt.fileserver.hgfs>`,
    :mod:`svn <salt.fileserver.svnfs>`).

    CLI Example:

    .. code-block:: bash

        salt-run fileserver.update
        salt-run fileserver.update backend=git
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    ret = fileserver.clear_cache(back=backend)
    salt.output.display_output(ret, 'nested', opts=__opts__)
