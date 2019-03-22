# -*- coding: utf-8 -*-
'''
Module to work with salt formula defaults files

'''

from __future__ import absolute_import, print_function, unicode_literals
import copy
import logging
import os

import salt.fileclient
import salt.utils.data
import salt.utils.dictupdate as dictupdate
import salt.utils.files
import salt.utils.json
import salt.utils.url
import salt.utils.yaml

__virtualname__ = 'defaults'

log = logging.getLogger(__name__)


def _mk_client():
    '''
    Create a file client and add it to the context
    '''
    if 'cp.fileclient' not in __context__:
        __context__['cp.fileclient'] = \
            salt.fileclient.get_file_client(__opts__)


def _load(formula):
    '''
    Generates a list of salt://<formula>/defaults.(json|yaml) files
    and fetches them from the Salt master.

    Returns first defaults file as python dict.
    '''

    # Compute possibilities
    _mk_client()
    paths = []
    for ext in ('yaml', 'json'):
        source_url = salt.utils.url.create(formula + '/defaults.' + ext)
        paths.append(source_url)
    # Fetch files from master
    defaults_files = __context__['cp.fileclient'].cache_files(paths)

    for file_ in defaults_files:
        if not file_:
            # Skip empty string returned by cp.fileclient.cache_files.
            continue

        suffix = file_.rsplit('.', 1)[-1]
        if suffix == 'yaml':
            loader = salt.utils.yaml.safe_load
        elif suffix == 'json':
            loader = salt.utils.json.load
        else:
            log.debug("Failed to determine loader for %r", file_)
            continue

        if os.path.exists(file_):
            log.debug("Reading defaults from %r", file_)
            with salt.utils.files.fopen(file_) as fhr:
                defaults = loader(fhr)
                log.debug("Read defaults %r", defaults)

            return defaults or {}


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

    # Determine formula namespace from query
    if ':' in key:
        namespace, key = key.split(':', 1)
    else:
        namespace, key = key, None

    # Fetch and load defaults formula files from states.
    defaults = _load(namespace)

    # Fetch value
    if key:
        return salt.utils.data.traverse_dict_and_list(defaults, key, default)
    else:
        return defaults


def merge(dest, src, merge_lists=False, in_place=True):
    '''
    defaults.merge
        Allows deep merging of dicts in formulas.

    merge_lists : False
        If True, it will also merge lists instead of replace their items.

    in_place : True
        If True, it will merge into dest dict,
        if not it will make a new copy from that dict and return it.

        CLI Example:
        .. code-block:: bash

        salt '*' default.merge a=b d=e

    It is more typical to use this in a templating language in formulas,
    instead of directly on the command-line.
    '''
    if in_place:
        merged = dest
    else:
        merged = copy.deepcopy(dest)
    return dictupdate.update(merged, src, merge_lists=merge_lists)


def deepcopy(source):
    '''
    defaults.deepcopy
        Allows deep copy of objects in formulas.

        By default, Python does not copy objects,
        it creates bindings between a target and an object.

    It is more typical to use this in a templating language in formulas,
    instead of directly on the command-line.
    '''
    return copy.deepcopy(source)
