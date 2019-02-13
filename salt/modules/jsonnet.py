# -*- coding: utf-8 -*-
'''
Jsonnet - A data templating language

Module to provide parsing support of jsonnet format.

:depends:    - jsonnet Python module (>= 0.11.2)

:configuration: This module accepts library paths configuration that
    can be passed as function parameters or as configuration settings in
    /etc/salt/minion on the relevant minions::

        jsonnet.library_paths:
          - /path/to/jsonnet/library

'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
from functools import partial
import logging
import os

# Import salt libs
import salt.utils.json

# Import third party libs
try:
    import _jsonnet
    HAS_JSONNET = True
except ImportError:
    HAS_JSONNET = False

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if jsonnet lib is present
    '''
    if HAS_JSONNET:
        return True
    return (False, ('The jsonnet execution module could not be loaded:'
                    'jsonnet library not available.'))


#  Returns content if worked, None if file not found, or throws an exception
def _try_path(dir, rel, lpaths):
    if not rel:
        raise RuntimeError('Got invalid filename (empty string).')
    if rel[-1] == '/':
        raise RuntimeError('Attempted to import a directory')
    full_paths = [rel] if rel[0] == '/' else \
            [os.path.realpath(os.path.join(dir, rel))] + \
            [os.path.realpath(os.path.join(l, rel)) for l in lpaths or []]

    for full_path in full_paths:
        if os.path.isfile(full_path):
            with salt.utils.files.fopen(full_path) as f:
                return full_path, f.read()
    return full_paths[0], None


def _import_callback(dir, rel, library_paths):
    full_path, content = _try_path(dir, rel, lpaths=library_paths)
    if content:
        return str(full_path), str(content)
    raise RuntimeError('File not found')


def evaluate(contents, jsonnet_library_paths=None):
    '''
    Evaluate a jsonnet input string.

    contents
        Raw jsonnet string to evaluate.

    jsonnet_library_paths
        List of jsonnet library paths.
    '''

    if not jsonnet_library_paths:
        jsonnet_library_paths = __salt__['config.option'](
                'jsonnet.library_paths', ['.'])
    return salt.utils.json.loads(
            _jsonnet.evaluate_snippet(
                "snippet",
                contents,
                import_callback=partial(
                    _import_callback, library_paths=jsonnet_library_paths)))
