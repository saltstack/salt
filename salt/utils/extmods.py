# -*- coding: utf-8 -*-
'''
Functions used to sync external modules
'''
from __future__ import absolute_import

# Import Python libs
import logging
import os
import shutil

# Import salt libs
import salt.fileclient
import salt.utils.url

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


def _list_emptydirs(rootdir):
    emptydirs = []
    for root, dirs, files in os.walk(rootdir):
        if not files and not dirs:
            emptydirs.append(root)
    return emptydirs


def _listdir_recursively(rootdir):
    file_list = []
    for root, dirs, files in os.walk(rootdir):
        for filename in files:
            relpath = os.path.relpath(root, rootdir).strip('.')
            file_list.append(os.path.join(relpath, filename))
    return file_list


def sync(opts, form, saltenv=None):
    '''
    Sync custom modules into the extension_modules directory
    '''
    if saltenv is None:
        saltenv = ['base']
    if isinstance(saltenv, six.string_types):
        saltenv = saltenv.split(',')
    ret = []
    remote = set()
    source = salt.utils.url.create('_' + form)
    mod_dir = os.path.join(opts['extension_modules'], '{0}'.format(form))
    cumask = os.umask(0o77)
    try:
        if not os.path.isdir(mod_dir):
            log.info('Creating module dir \'{0}\''.format(mod_dir))
            try:
                os.makedirs(mod_dir)
            except (IOError, OSError):
                log.error(
                    'Cannot create cache module directory {0}. Check '
                    'permissions.'.format(mod_dir)
                )
        fileclient = salt.fileclient.get_file_client(opts)
        for sub_env in saltenv:
            log.info(
                'Syncing {0} for environment \'{1}\''.format(form, sub_env)
            )
            cache = []
            log.info(
                'Loading cache from {0}, for {1})'.format(source, sub_env)
            )
            # Grab only the desired files (.py, .pyx, .so)
            cache.extend(
                fileclient.cache_dir(
                    source, sub_env, include_empty=False,
                    include_pat=r'E@\.(pyx?|so|zip)$', exclude_pat=None
                )
            )
            local_cache_dir = os.path.join(
                    opts['cachedir'],
                    'files',
                    sub_env,
                    '_{0}'.format(form)
                    )
            log.debug('Local cache dir: \'{0}\''.format(local_cache_dir))
            for fn_ in cache:
                relpath = os.path.relpath(fn_, local_cache_dir)
                relname = os.path.splitext(relpath)[0].replace(os.sep, '.')
                remote.add(relpath)
                dest = os.path.join(mod_dir, relpath)
                log.info('Copying \'{0}\' to \'{1}\''.format(fn_, dest))
                if os.path.isfile(dest):
                    # The file is present, if the sum differs replace it
                    hash_type = opts.get('hash_type', 'md5')
                    src_digest = salt.utils.get_hash(fn_, hash_type)
                    dst_digest = salt.utils.get_hash(dest, hash_type)
                    if src_digest != dst_digest:
                        # The downloaded file differs, replace!
                        shutil.copyfile(fn_, dest)
                        ret.append('{0}.{1}'.format(form, relname))
                else:
                    dest_dir = os.path.dirname(dest)
                    if not os.path.isdir(dest_dir):
                        os.makedirs(dest_dir)
                    shutil.copyfile(fn_, dest)
                    ret.append('{0}.{1}'.format(form, relname))

        touched = bool(ret)
        if opts.get('clean_dynamic_modules', True):
            current = set(_listdir_recursively(mod_dir))
            for fn_ in current - remote:
                full = os.path.join(mod_dir, fn_)
                if os.path.isfile(full):
                    touched = True
                    os.remove(full)
            # Cleanup empty dirs
            while True:
                emptydirs = _list_emptydirs(mod_dir)
                if not emptydirs:
                    break
                for emptydir in emptydirs:
                    touched = True
                    shutil.rmtree(emptydir, ignore_errors=True)
    except Exception as exc:
        log.error('Failed to sync {0} module: {1}'.format(form, exc))
    finally:
        os.umask(cumask)
    return ret, touched
