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
    Return the environments for the named backend or all back-ends

    CLI Example:

    .. code-block:: bash

        salt-run fileserver.envs
        salt-run fileserver.envs outputter=nested
        salt-run fileserver.envs backend='["root", "git"]'
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
    Update all of the file-servers that support the update function or the
    named fileserver only.

    CLI Example:

    .. code-block:: bash

        salt-run fileserver.update
        salt-run fileserver.update backend='["root", "git"]'
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    fileserver.update(back=backend)

    return True
