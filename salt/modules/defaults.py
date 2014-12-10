# -*- coding: utf-8 -*-
from __future__ import absolute_import
import inspect
import json
import os
import yaml

import salt.fileclient
import salt.utils
import salt.ext.six as six

__virtualname__ = 'defaults'


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


def _load(defaults_path):
    '''
    Given a pillar_name and the template cache location, attempt to load
    the defaults.json from the cache location. If it does not exist, try
    defaults.yaml.
    '''
    for loader in json, yaml:
        defaults_file = os.path.join(defaults_path, 'defaults.' + loader.__name__)
        if os.path.exists(defaults_file):
            with salt.utils.fopen(defaults_file) as fhr:
                defaults = loader.load(fhr)
            return defaults


def get(key, default=''):
    '''
    defaults.get is used much like pillar.get except that it will read
    a default value for a pillar from defaults.json or defaults.yaml
    files that are stored in the root of a salt formula.

    When called from the CLI it works exactly like pillar.get.

    CLI Example:

    .. code-block:: bash

        salt '*' defaults.get core:users:root

    When called from an SLS file, it works by first reading a defaults.json
    and second a defaults.yaml file. If the key exists in these files and
    does not exist in a pillar named after the formula, the value from the
    defaults file is used.

    Example core/defaults.json file for the 'core' formula:

    .. code-block:: json

        {
            "users": {
                "root": 0
            }
        }

    With this, from a state file you can use salt['defaults.get']('users:root')
    to read the '0' value from defaults.json if a core:users:root pillar
    key is not defined.
    '''

    sls = None
    tmplpath = None

    for frame in inspect.stack():
        if sls is not None and tmplpath is not None:
            break

        frame_args = inspect.getargvalues(frame[0]).locals

        for _sls in (
            None if not isinstance(frame_args.get('context'), dict) else frame_args.get('context').get('__sls__'),
            frame_args.get('mods', [None])[0],
            frame_args.get('sls')
        ):
            if sls is not None:
                break
            sls = _sls

        for _tmpl in (
            frame_args.get('tmplpath'),
            frame_args.get('tmplsrc')
        ):
            if tmplpath is not None:
                break
            tmplpath = _tmpl

    if not sls:  # this is the case when called from CLI
        return __salt__['pillar.get'](key, default)

    pillar_name = sls.split('.')[0]
    defaults_path = tmplpath.split(pillar_name)[0] + pillar_name

    _get_files(pillar_name)

    defaults = _load(defaults_path)

    value = __salt__['pillar.get']('{0}:{1}'.format(pillar_name, key), None)

    if value is None:
        value = salt.utils.traverse_dict_and_list(defaults, key, None)

    if value is None:
        value = default

    if isinstance(value, six.text_type):
        value = str(value)

    return value
