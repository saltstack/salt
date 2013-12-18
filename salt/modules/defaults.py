# -*- coding: utf-8 -*-
import inspect
import json
import os
import yaml

import salt.fileclient
import salt.utils

__virtualname__ = 'defaults'

def _mk_client():
    if not 'cp.fileclient' in __context__:
        __context__['cp.fileclient'] = \
            salt.fileclient.get_file_client(__opts__)

def _get_files(pillar_name):
    _mk_client()
    pillar_name = pillar_name.replace(".", "/")
    paths = []

    for ext in ('yaml', 'json'):
        source_url = 'salt://%s/%s' % (pillar_name, 'defaults.' + ext)
        paths.append(source_url)

    return __context__['cp.fileclient'].cache_files(paths)

def _load(pillar_name, defaults_path):
    for loader in json, yaml:
        defaults_file = os.path.join(defaults_path, 'defaults.' + loader.__name__)
        if os.path.exists(defaults_file):
            defaults = loader.load(open(defaults_file))
            return defaults

def get(key, default=''):
    stack = inspect.stack()
    sls = inspect.getargvalues(stack[2][0]).locals.get('sls')
    tmplpath = inspect.getargvalues(stack[2][0]).locals.get('tmplpath')

    pillar_name = sls.split('.')[0]
    defaults_path = tmplpath.split(pillar_name)[0] + pillar_name

    _get_files(pillar_name)

    defaults = _load(pillar_name, defaults_path)
    data = salt.utils.dictupdate.update(defaults, __salt__['pillar.get'](pillar_name, {}))
    value = salt.utils.traverse_dict(data, key, default)

    if isinstance(value, unicode):
        value = str(value)

    return value
