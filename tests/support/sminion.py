# -*- coding: utf-8 -*-
'''
tests.support.sminion
~~~~~~~~~~~~~~~~~~~~~

SMinion's support functions
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import shutil
import hashlib
import logging

# Import salt libs
import salt.minion
import salt.utils.path
import salt.utils.stringutils

# Import testing libs
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


def build_minion_opts(minion_id=None,
                      root_dir=None,
                      initial_conf_file=None,
                      minion_opts_overrides=None,
                      skip_cached_opts=False,
                      cache_opts=True,
                      minion_role=None):
    if minion_id is None:
        minion_id = 'pytest-internal-sminion'
    if skip_cached_opts is False:
        try:
            opts_cache = build_minion_opts.__cached_opts__
        except AttributeError:
            opts_cache = build_minion_opts.__cached_opts__ = {}
        cached_opts = opts_cache.get(minion_id)
        if cached_opts:
            return cached_opts

    log.info('Generating testing minion %r configuration...', minion_id)
    if root_dir is None:
        hashed_minion_id = hashlib.sha1()
        hashed_minion_id.update(salt.utils.stringutils.to_bytes(minion_id))
        root_dir = os.path.join(RUNTIME_VARS.TMP_ROOT_DIR, hashed_minion_id.hexdigest()[:6])

    if initial_conf_file is not None:
        minion_opts = salt.config._read_conf_file(initial_conf_file)  # pylint: disable=protected-access
    else:
        minion_opts = {}

    conf_dir = os.path.join(root_dir, 'conf')
    conf_file = os.path.join(conf_dir, 'minion')

    minion_opts['id'] = minion_id
    minion_opts['conf_file'] = conf_file
    minion_opts['root_dir'] = root_dir
    minion_opts['cachedir'] = 'cache'
    minion_opts['user'] = RUNTIME_VARS.RUNNING_TESTS_USER
    minion_opts['pki_dir'] = 'pki'
    minion_opts['hosts.file'] = os.path.join(RUNTIME_VARS.TMP_ROOT_DIR, 'hosts')
    minion_opts['aliases.file'] = os.path.join(RUNTIME_VARS.TMP_ROOT_DIR, 'aliases')
    minion_opts['file_client'] = 'local'
    minion_opts['server_id_use_crc'] = 'adler32'
    minion_opts['pillar_roots'] = {
        'base': [
            RUNTIME_VARS.TMP_PILLAR_TREE,
        ]
    }
    minion_opts['file_roots'] = {
        'base': [
            # Let's support runtime created files that can be used like:
            #   salt://my-temp-file.txt
            RUNTIME_VARS.TMP_STATE_TREE
        ],
        # Alternate root to test __env__ choices
        'prod': [
            os.path.join(RUNTIME_VARS.FILES, 'file', 'prod'),
            RUNTIME_VARS.TMP_PRODENV_STATE_TREE
        ]
    }
    if initial_conf_file and initial_conf_file.startswith(RUNTIME_VARS.FILES):
        # We assume we were passed a minion configuration file defined fo testing and, as such
        # we define the file and pillar roots to include the testing states/pillar trees
        minion_opts['pillar_roots']['base'].append(
            os.path.join(RUNTIME_VARS.FILES, 'pillar', 'base'),
        )
        minion_opts['file_roots']['base'].append(
            os.path.join(RUNTIME_VARS.FILES, 'file', 'base'),
        )
        minion_opts['file_roots']['prod'].append(
            os.path.join(RUNTIME_VARS.FILES, 'file', 'prod'),
        )

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = os.path.join(root_dir, 'extension_modules')
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(
                RUNTIME_VARS.FILES, 'extension_modules'
            ),
            extension_modules_path
        )
    minion_opts['extension_modules'] = extension_modules_path

    # Custom grains
    if 'grains' not in minion_opts:
        minion_opts['grains'] = {}
    if minion_role is not None:
        minion_opts['grains']['role'] = minion_role

    # Under windows we can't seem to properly create a virtualenv off of another
    # virtualenv, we can on linux but we will still point to the virtualenv binary
    # outside the virtualenv running the test suite, if that's the case.
    try:
        real_prefix = sys.real_prefix
        # The above attribute exists, this is a virtualenv
        if salt.utils.platform.is_windows():
            virtualenv_binary = os.path.join(real_prefix, 'Scripts', 'virtualenv.exe')
        else:
            # We need to remove the virtualenv from PATH or we'll get the virtualenv binary
            # from within the virtualenv, we don't want that
            path = os.environ.get('PATH')
            if path is not None:
                path_items = path.split(os.pathsep)
                for item in path_items[:]:
                    if item.startswith(sys.base_prefix):
                        path_items.remove(item)
                os.environ['PATH'] = os.pathsep.join(path_items)
            virtualenv_binary = salt.utils.path.which('virtualenv')
            if path is not None:
                # Restore previous environ PATH
                os.environ['PATH'] = path
            if not virtualenv_binary.startswith(real_prefix):
                virtualenv_binary = None
        if virtualenv_binary and not os.path.exists(virtualenv_binary):
            # It doesn't exist?!
            virtualenv_binary = None
    except AttributeError:
        # We're not running inside a virtualenv
        virtualenv_binary = None
    if virtualenv_binary:
        minion_opts['venv_bin'] = virtualenv_binary

    # Override minion_opts with minion_opts_overrides
    if minion_opts_overrides:
        minion_opts.update(minion_opts_overrides)

    if not os.path.exists(conf_dir):
        os.makedirs(conf_dir)

    with salt.utils.files.fopen(conf_file, 'w') as fp_:
        salt.utils.yaml.safe_dump(minion_opts, fp_, default_flow_style=False)

    log.info('Generating testing minion %r configuration completed.', minion_id)
    minion_opts = salt.config.minion_config(conf_file, minion_id=minion_id, cache_minion_id=True)
    salt.utils.verify.verify_env(
        [
            os.path.join(minion_opts['pki_dir'], 'accepted'),
            os.path.join(minion_opts['pki_dir'], 'rejected'),
            os.path.join(minion_opts['pki_dir'], 'pending'),
            os.path.dirname(minion_opts['log_file']),
            minion_opts['extension_modules'],
            minion_opts['cachedir'],
            minion_opts['sock_dir'],
            RUNTIME_VARS.TMP_STATE_TREE,
            RUNTIME_VARS.TMP_PILLAR_TREE,
            RUNTIME_VARS.TMP_PRODENV_STATE_TREE,
            RUNTIME_VARS.TMP,
        ],
        RUNTIME_VARS.RUNNING_TESTS_USER,
        root_dir=root_dir
    )
    if cache_opts:
        try:
            opts_cache = build_minion_opts.__cached_opts__
        except AttributeError:
            opts_cache = build_minion_opts.__cached_opts__ = {}
        opts_cache[minion_id] = minion_opts
    return minion_opts


def create_sminion(minion_id=None,
                   root_dir=None,
                   initial_conf_file=None,
                   sminion_cls=salt.minion.SMinion,
                   minion_opts_overrides=None,
                   skip_cached_minion=False,
                   cache_sminion=True):
    if minion_id is None:
        minion_id = 'pytest-internal-sminion'
    if skip_cached_minion is False:
        try:
            minions_cache = create_sminion.__cached_minions__
        except AttributeError:
            create_sminion.__cached_minions__ = {}
        cached_minion = create_sminion.__cached_minions__.get(minion_id)
        if cached_minion:
            return cached_minion
    minion_opts = build_minion_opts(minion_id=minion_id,
                                    root_dir=root_dir,
                                    initial_conf_file=initial_conf_file,
                                    minion_opts_overrides=minion_opts_overrides,
                                    skip_cached_opts=skip_cached_minion,
                                    cache_opts=cache_sminion)
    log.info('Instantiating a testing %s(%s)', sminion_cls.__name__, minion_id)
    sminion = sminion_cls(minion_opts)
    if cache_sminion:
        try:
            minions_cache = create_sminion.__cached_minions__
        except AttributeError:
            minions_cache = create_sminion.__cached_minions__ = {}
        minions_cache[minion_id] = sminion
    return sminion
