# -*- coding: utf-8 -*-
'''
Pull sdb values from a YAML file

:maintainer:    SaltStack
:maturity:      New
:platform:      all

.. versionadded:: 2017.7.0

Configuration:

.. code-block:: yaml

    my-yaml-file:
      driver: yaml
      files:
        - /path/to/foo.yaml
        - /path/to/bar.yaml

The files are merged together and the result is searched using the same
mechanism Salt uses for searching Grains and Pillar data structures.

Optional configuration:

.. code-block:: yaml

    my-yaml-file:
      driver: yaml
      files:
        - /path/to/foo.yaml
        - /path/to/bar.yaml
      merge:
        strategy: smart
        merge_list: false
'''

# import python libs
from __future__ import absolute_import
import logging

import salt.exceptions
import salt.loader
import salt.utils
import salt.utils.files
import salt.utils.dictupdate

log = logging.getLogger(__name__)

__func_alias__ = {
    'set_': 'set'
}


def set_(*args, **kwargs):
    '''
    Setting a value is not supported; edit the YAML files directly
    '''
    raise salt.exceptions.NotImplemented()


def get(key, profile=None):  # pylint: disable=W0613
    '''
    Get a value from the REST interface
    '''
    data = _get_values(profile)
    return salt.utils.traverse_dict_and_list(data, key, None)


def _get_values(profile=None):
    '''
    Retrieve all the referenced files, deserialize, then merge them together
    '''
    profile = profile or {}
    serializers = salt.loader.serializers(__opts__)

    ret = {}
    for fname in profile.get('files', []):
        try:
            with salt.utils.files.flopen(fname) as f:
                contents = serializers.yaml.deserialize(f)
                ret = salt.utils.dictupdate.merge(ret, contents,
                        **profile.get('merge', {}))
        except IOError:
            log.error("File not found '{0}'".format(fname))
        except TypeError:
            log.error("Error deserializing sdb file '{0}'".format(fname))
    return ret
