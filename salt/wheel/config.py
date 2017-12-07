# -*- coding: utf-8 -*-
'''
Manage the master configuration file
'''
from __future__ import absolute_import

# Import python libs
import logging
import os

# Import third party libs
import yaml

# Import salt libs
import salt.config
import salt.utils.files
from salt.utils.yamldumper import SafeOrderedDumper

log = logging.getLogger(__name__)


def values():
    '''
    Return the raw values of the config file
    '''
    data = salt.config.master_config(__opts__[u'conf_file'])
    return data


def apply(key, value):
    '''
    Set a single key

    .. note::

        This will strip comments from your config file
    '''
    path = __opts__[u'conf_file']
    if os.path.isdir(path):
        path = os.path.join(path, u'master')
    data = values()
    data[key] = value
    with salt.utils.files.fopen(path, u'w+') as fp_:
        fp_.write(
            yaml.dump(
                data,
                default_flow_style=False,
                Dumper=SafeOrderedDumper
            )
        )


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
    file_name = u'{0}{1}'.format(file_name, u'.conf')
    dir_path = os.path.join(__opts__[u'config_dir'],
                            os.path.dirname(__opts__[u'default_include']))
    try:
        yaml_out = yaml.safe_dump(yaml_contents, default_flow_style=False)

        if not os.path.exists(dir_path):
            log.debug(u'Creating directory %s', dir_path)
            os.makedirs(dir_path, 0o755)

        file_path = os.path.join(dir_path, file_name)
        with salt.utils.files.fopen(file_path, u'w') as fp_:
            fp_.write(yaml_out)

        return u'Wrote {0}'.format(file_name)
    except (IOError, OSError, yaml.YAMLError, ValueError) as err:
        return str(err)
