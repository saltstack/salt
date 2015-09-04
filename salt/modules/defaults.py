# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json
import logging
import os
import yaml

import salt.fileclient
import salt.utils


__virtualname__ = 'defaults'


log = logging.getLogger(__name__)


def _mk_client():
    '''
    Create a file client and add it to the context
    '''
    if 'cp.fileclient' not in __context__:
        __context__['cp.fileclient'] = \
            salt.fileclient.get_file_client(__opts__)


def _get_files(pillar_name):
    '''
    Generates a list of salt://<pillar_name>/defaults.(json|yaml) files
    and fetches them from the Salt master.
    '''
    _mk_client()
    pillar_name = pillar_name.replace('.', '/')
    paths = []

    for ext in ('yaml', 'json'):
        source_url = 'salt://{0}/{1}'.format(pillar_name, 'defaults.' + ext)
        paths.append(source_url)

    return __context__['cp.fileclient'].cache_files(paths)


def _load(defaults_files):
    '''
    Loads given defaults default_files with corresponding loader.
    '''

    for file_ in defaults_files:
        if not file_:
            continue

        suffix = file_.rsplit('.', 1)[-1]
        if suffix in ('yml', 'yaml'):
            loader = yaml
        elif suffix == 'json':
            loader = json
        else:
            continue

        if os.path.exists(file_):
            log.debug("Reading defaults from %r", file_)
            with salt.utils.fopen(file_) as fhr:
                defaults = loader.load(fhr)
                log.debug("Read defaults %r", defaults)

            return defaults


def get(key, default=''):
    '''
    defaults.get is used much like pillar.get except that it will read
    a default value for a pillar from defaults.json or defaults.yaml
    files that are stored in the root of a salt formula.

    CLI Example:

    .. code-block:: bash

        salt '*' defaults.get core:users:root

    The defaults is computed from pillar key. The first entry is considered as
    the formula namespace.

    For example, querying ``core:users:root`` will try to load
    ``salt://core/defaults.yaml`` and ``salt://core/defaults.json``.
    '''

    if ':' in key:
        namespace, key = key.split(':', 1)
    else:
        namespace, key = key, None

    defaults_files = _get_files(namespace)
    defaults = _load(defaults_files)

    if key:
        return salt.utils.traverse_dict_and_list(defaults, key, default)
    else:
        return defaults
