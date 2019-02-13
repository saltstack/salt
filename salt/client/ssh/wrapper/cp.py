# -*- coding: utf-8 -*-
'''
Wrap the cp module allowing for managed ssh file transfers
'''
# Import Python libs
from __future__ import absolute_import, print_function
import logging
import os

# Import salt libs
import salt.client.ssh
import salt.fileclient
from salt.fileclient import FSClient
import salt.modules.cp

import salt.utils.files
import salt.utils.stringutils
import salt.utils.templates
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


class SSHClient(FSClient):
    '''
    A local client that uses the RemoteClient but substitutes the channel for
    the FSChan object
    '''
    def __init__(self, opts):  # pylint: disable=W0231
        opts['cachedir'] = os.path.join('salt-ssh', __salt__.kwargs['id_'])
        super().__init__(opts)

    def get_file(self,
                 path,
                 dest='',
                 makedirs=False,
                 saltenv='base',
                 gzip=None,
                 cachedir=None):

        log.warning('AWESOME DUDE!')

        src = super().get_file(
            path, dest, makedirs,
            saltenv, gzip, cachedir
        )
        single = salt.client.ssh.Single(
            __opts__,
            '',
            **__salt__.kwargs)
        ret = single.shell.send(src, dest, makedirs)
        log.warning('HERE BE {}'.format(ret))

        return src


def __mk_client():
    '''
    Create a file client and add it to the context.

    Each file client needs to correspond to a unique copy
    of the opts dictionary, therefore it's hashed by the
    id of the __opts__ dict
    '''

    if 'cp.fileclient_{0}'.format(id(__opts__)) not in __context__:
        __context__['cp.fileclient_{0}'.format(id(__opts__))] = \
            SSHClient(__opts__)


def _push(path, keep_symlinks=False, upload_path=None, remove_source=False):
    if not __opts__.get('file_recv', False):
        log.error('Push requested but master does not allow file_recv')
        return False

    log.debug('Trying to copy \'%s\' to master', path)
    if '../' in path or not os.path.isabs(path):
        log.debug('Path must be absolute, returning False')
        return False
    if not keep_symlinks:
        path = os.path.realpath(path)
    if not os.path.isfile(path):
        log.debug('Path failed os.path.isfile check, returning False')
        return False

    if upload_path:
        if '../' in upload_path:
            log.debug('Path must be absolute, returning False')
            log.debug('Bad path: %s', upload_path)
            return False
        load_path = upload_path.lstrip(os.sep)
    else:
        load_path = path.lstrip(os.sep)
    # Normalize the path. This does not eliminate
    # the possibility that relative entries will still be present
    load_path_normal = os.path.normpath(load_path)

    # If this is Windows and a drive letter is present, remove it
    load_path_split_drive = os.path.splitdrive(load_path_normal)[1]

    # Finally, split the remaining path into a list for delivery to the master
    load_path_list = [_f for _f in load_path_split_drive.split(os.sep) if _f]

    single = salt.client.ssh.Single(
        __opts__,
        '',
        **__salt__.kwargs)

    # TODO: yeah but no receive yet
    ret = single.shell.send()
    #ret = single.shell.send(src, dest, makedirs)

    return not ret[2]


def _fix_me():
    salt.modules.cp._mk_client = __mk_client
    salt.modules.cp.push = _push
    salt.modules.cp.__context__ = __context__
    salt.modules.cp.__pillar__ = __pillar__
    salt.modules.cp.__grains__ = __grains__
    salt.modules.cp.__opts__ = __opts__
    salt.modules.cp.__salt__ = __salt__
    log.warning('MODULE LOADED')


def cache_dir(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.cache_dir(*args, **kwargs)


def cache_file(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.cache_file(*args, **kwargs)


def cache_files(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.cache_files(*args, **kwargs)


def get_dir(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.get_dir(*args, **kwargs)


def get_file(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.get_file(*args, **kwargs)


def get_file_str(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.get_file_str(*args, **kwargs)


def get_template(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.get_template(*args, **kwargs)


def get_url(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.get_url(*args, **kwargs)


def hash_file(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.hash_file(*args, **kwargs)


def list_master(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.list_master(*args, **kwargs)


def list_master_dirs(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.list_master_dirs(*args, **kwargs)


def list_master_symlinks(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.list_master_symlinks(*args, **kwargs)


def list_states(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.list_states(*args, **kwargs)


def stat_file(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.stat_file(*args, **kwargs)


# def _render_filenames(path, dest, saltenv, template):
#     '''
#     Process markup in the :param:`path` and :param:`dest` variables (NOT the
#     files under the paths they ultimately point to) according to the markup
#     format provided by :param:`template`.
#     '''
#     if not template:
#         return (path, dest)
#
#     # render the path as a template using path_template_engine as the engine
#     if template not in salt.utils.templates.TEMPLATE_REGISTRY:
#         raise CommandExecutionError(
#             'Attempted to render file paths with unavailable engine '
#             '{0}'.format(template)
#         )
#
#     kwargs = {}
#     kwargs['salt'] = __salt__
#     kwargs['pillar'] = __pillar__
#     kwargs['grains'] = __grains__
#     kwargs['opts'] = __opts__
#     kwargs['saltenv'] = saltenv
#
#     def _render(contents):
#         '''
#         Render :param:`contents` into a literal pathname by writing it to a
#         temp file, rendering that file, and returning the result.
#         '''
#         # write out path to temp file
#         tmp_path_fn = salt.utils.files.mkstemp()
#         with salt.utils.files.fopen(tmp_path_fn, 'w+') as fp_:
#             fp_.write(salt.utils.stringutils.to_str(contents))
#         data = salt.utils.templates.TEMPLATE_REGISTRY[template](
#             tmp_path_fn,
#             to_str=True,
#             **kwargs
#         )
#         salt.utils.files.safe_rm(tmp_path_fn)
#         if not data['result']:
#             # Failed to render the template
#             raise CommandExecutionError(
#                 'Failed to render file path with error: {0}'.format(
#                     data['data']
#                 )
#             )
#         else:
#             return data['data']
#
#     path = _render(path)
#     dest = _render(dest)
#     return (path, dest)
