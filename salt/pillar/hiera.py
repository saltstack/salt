# -*- coding: utf-8 -*-
'''
Use hiera data as a Pillar source
'''

# Import python libs
import logging

# Import salt libs
import salt.utils
from salt._compat import string_types

# Import third party libs
import yaml


# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only return if hiera is installed
    '''
    return 'hiera' if salt.utils.which('hiera') else False


def ext_pillar(minion_id, pillar, conf):
    '''
    Execute hiera and return the data
    '''
    cmd = 'hiera -c {0}'.format(conf)
    for key, val in __grains__.items():
        if isinstance(val, string_types):
            cmd += ' {0}=\'{1}\''.format(key, val)
    try:
        data = yaml.safe_load(__salt__['cmd.run'](cmd))
    except Exception:
        log.critical(
                'Hiera YAML data failed to parse from conf {0}'.format(conf)
                )
        return {}
    return data
