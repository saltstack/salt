'''
The status beacon is intended to send a basic health check event up to the
master, this allows for event driven routines based on presence to be set up.

The intention of this beacon is to add the config options to add monitoring
stats to the health beacon making it a one stp shop for gathering systems
health and status data
'''

# Import python libs
import time


def validate(config):
    '''
    Validate the the config is a dict
    '''
    if not isinstance(config, dict):
        return False, ('Configuration for status beacon must be a dictionary.')
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    Just say that we are ok!
    '''
    return [{'tag': '{0}'.format(int(time.time()))}]
