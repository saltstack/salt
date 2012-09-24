'''
Manage configuration files in salt-cloud
'''

# Import python libs
import os

# Import salt libs
import salt.config


def api_config(path):
    '''
    Read in the salt master config file and add additional configs that
    need to be stubbed out for cloudapi
    '''
    opts = {
            'extension_modules': [],
            }

    salt.config.load_config(opts, path, 'SALT_MASTER_CONFIG')

    if 'include' in opts:
        opts = salt.config.include_config(opts, path)

    return opts
