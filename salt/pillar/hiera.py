'''
Take in a hiera configuration file location and execute it.
Adds the hiera data to pillar
'''

# Import python libs
import logging

# Import salt libs
import salt.utils

# Import third party libs
import yaml


# Set up logging
log = logging.getLogger(__name__)

def __virtual__():
    '''
    Only return if hiera is installed
    '''
    return 'hiera' if salt.utils.which('hiera') else False


def ext_pillar(conf):
    '''
    Execute hiera and return the data
    '''
    cmd = 'hiera {0}'.format(conf)
    for key, val in __grains__.items():
        if isinstance(val, string_types):
            cmd += ' {0}={1}'.format(key, val)
    try:
        data = yaml.safe_load(__salt__['cmd.run'](cmd))
    except Exception:
        log.critical(
                'Hiera yaml data failed to parse from conf {0}'.format(conf)
                )
        return {}
    return data
