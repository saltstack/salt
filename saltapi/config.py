'''
Manage configuration files in salt-api
'''

# Import salt libs
import salt.config

DEFAULT_API_OPTS = {
    # ----- Salt master settings overridden by Salt-API --------------------->
    'pidfile': '/var/run/salt-api.pid',
    'logfile': '/var/log/salt/api',
    # <---- Salt master settings overridden by Salt-API ----------------------
}


def api_config(path):
    '''
    Read in the salt master config file and add additional configs that
    need to be stubbed out for salt-api
    '''
    # Let's grab a copy of salt's master default opts
    defaults = salt.config.DEFAULT_MASTER_OPTS
    # Let's override them with salt-api's required defaults
    defaults.update(DEFAULT_API_OPTS)

    return salt.config.master_config(path, defaults=defaults)
