# -*- coding: utf-8 -*-
'''
Wrap the cp module allowing for managed ssh file transfers
'''
from __future__ import absolute_import

# Import salt libs
import salt.client.ssh
import logging
import os
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def get_file(path,
             dest,
             saltenv='base',
             makedirs=False,
             template=None,
             gzip=None):
    '''
    Send a file from the master to the location in specified

    .. note::

        gzip compression is not supported in the salt-ssh version of
        cp.get_file. The argument is only accepted for interface compatibility.
    '''
    if gzip is not None:
        log.warning('The gzip argument to cp.get_file in salt-ssh is '
                    'unsupported')

    if template is not None:
        (path, dest) = _render_filenames(path, dest, saltenv, template)

    src = __context__['fileclient'].cache_file(
        path,
        saltenv,
        cachedir=os.path.join('salt-ssh', __salt__.kwargs['id_']))
    single = salt.client.ssh.Single(
            __opts__,
            '',
            **__salt__.kwargs)
    ret = single.shell.send(src, dest, makedirs)
    return not ret[2]


def get_dir(path, dest, saltenv='base'):
    '''
    Transfer a directory down
    '''
    src = __context__['fileclient'].cache_dir(
        path,
        saltenv,
        cachedir=os.path.join('salt-ssh', __salt__.kwargs['id_']))
    src = ' '.join(src)
    single = salt.client.ssh.Single(
            __opts__,
            '',
            **__salt__.kwargs)
    ret = single.shell.send(src, dest)
    return not ret[2]


def get_url(path, dest, saltenv='base'):
    '''
    retrieve a URL
    '''
    src = __context__['fileclient'].get_url(
        path,
        saltenv,
        cachedir=os.path.join('salt-ssh', __salt__.kwargs['id_']))
    single = salt.client.ssh.Single(
            __opts__,
            '',
            **__salt__.kwargs)
    ret = single.shell.send(src, dest)
    return not ret[2]


def list_states(saltenv='base'):
    '''
    List all the available state modules in an environment
    '''
    return __context__['fileclient'].list_states(saltenv)


def list_master(saltenv='base', prefix=''):
    '''
    List all of the files stored on the master
    '''
    return __context__['fileclient'].file_list(saltenv, prefix)


def list_master_dirs(saltenv='base', prefix=''):
    '''
    List all of the directories stored on the master
    '''
    return __context__['fileclient'].dir_list(saltenv, prefix)


def list_master_symlinks(saltenv='base', prefix=''):
    '''
    List all of the symlinks stored on the master
    '''
    return __context__['fileclient'].symlink_list(saltenv, prefix)


def _render_filenames(path, dest, saltenv, template):
    '''
    Process markup in the :param:`path` and :param:`dest` variables (NOT the
    files under the paths they ultimately point to) according to the markup
    format provided by :param:`template`.
    '''
    if not template:
        return (path, dest)

    # render the path as a template using path_template_engine as the engine
    if template not in salt.utils.templates.TEMPLATE_REGISTRY:
        raise CommandExecutionError(
            'Attempted to render file paths with unavailable engine '
            '{0}'.format(template)
        )

    kwargs = {}
    kwargs['salt'] = __salt__
    kwargs['pillar'] = __pillar__
    kwargs['grains'] = __grains__
    kwargs['opts'] = __opts__
    kwargs['saltenv'] = saltenv

    def _render(contents):
        '''
        Render :param:`contents` into a literal pathname by writing it to a
        temp file, rendering that file, and returning the result.
        '''
        # write out path to temp file
        tmp_path_fn = salt.utils.mkstemp()
        with salt.utils.fopen(tmp_path_fn, 'w+') as fp_:
            fp_.write(contents)
        data = salt.utils.templates.TEMPLATE_REGISTRY[template](
            tmp_path_fn,
            to_str=True,
            **kwargs
        )
        salt.utils.safe_rm(tmp_path_fn)
        if not data['result']:
            # Failed to render the template
            raise CommandExecutionError(
                'Failed to render file path with error: {0}'.format(
                    data['data']
                )
            )
        else:
            return data['data']

    path = _render(path)
    dest = _render(dest)
    return (path, dest)
