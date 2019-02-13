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

        return not ret[2]





def _mk_client():
    '''
    Create a file client and add it to the context.

    Each file client needs to correspond to a unique copy
    of the opts dictionary, therefore it's hashed by the
    id of the __opts__ dict
    '''

    if 'cp.fileclient_{0}'.format(id(__opts__)) not in __context__:
        __context__['cp.fileclient_{0}'.format(id(__opts__))] = \
            SSHClient(__opts__)


def _fix_me():
    salt.modules.cp._mk_client = _mk_client
    salt.modules.cp.__context__ = __context__
    salt.modules.cp.__opts__ = __opts__
    salt.modules.cp.__salt__ = __salt__
    log.warning('MODULE LOADED')
    

def get_file(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.get_file(*args, **kwargs)


def cache_file(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.cache_file(*args, **kwargs)


def get_dir(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.get_dir(*args, **kwargs)


def get_url(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.get_url(*args, **kwargs)


def list_states(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.list_states(*args, **kwargs)


def list_master(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.list_master(*args, **kwargs)


def list_master_dirs(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.list_master_dirs(*args, **kwargs)


def list_master_symlinks(*args, **kwargs):
    _fix_me()
    return salt.modules.cp.list_master_symlinks(*args, **kwargs)


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
