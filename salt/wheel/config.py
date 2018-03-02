# -*- coding: utf-8 -*-
'''
Manage the master configuration file
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging
import os

# Import salt libs
import salt.config
import salt.utils.files
import salt.utils.yaml

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


def values():
    '''
    Return the raw values of the config file
    '''
    data = salt.config.master_config(__opts__['conf_file'])
    return data


def apply(key, value):
    '''
    Set a single key

    .. note::

        This will strip comments from your config file
    '''
    path = __opts__['conf_file']
    if os.path.isdir(path):
        path = os.path.join(path, 'master')
    data = values()
    data[key] = value
    with salt.utils.files.fopen(path, 'w+') as fp_:
        salt.utils.yaml.safe_dump(data, default_flow_style=False)


def update_config(file_name, yaml_contents):
    '''
    Update master config with
    ``yaml_contents``.

    Writes ``yaml_contents`` to a file named
    ``file_name.conf`` under the folder
    specified by ``default_include``.
    This folder is named ``master.d`` by
    default. Please look at
    :conf_master:`include-configuration`
    for more information.

    Example low data:

    .. code-block:: yaml

        data = {
            'username': 'salt',
            'password': 'salt',
            'fun': 'config.update_config',
            'file_name': 'gui',
            'yaml_contents': {'id': 1},
            'client': 'wheel',
            'eauth': 'pam',
        }
    '''
    file_name = '{0}{1}'.format(file_name, '.conf')
    dir_path = os.path.join(__opts__['config_dir'],
                            os.path.dirname(__opts__['default_include']))
    try:
        yaml_out = salt.utils.yaml.safe_dump(yaml_contents, default_flow_style=False)

        if not os.path.exists(dir_path):
            log.debug('Creating directory %s', dir_path)
            os.makedirs(dir_path, 0o755)

        file_path = os.path.join(dir_path, file_name)
        with salt.utils.files.fopen(file_path, 'w') as fp_:
            fp_.write(yaml_out)

        return 'Wrote {0}'.format(file_name)
    except (IOError, OSError, salt.utils.yaml.YAMLError, ValueError) as err:
        return six.text_type(err)
