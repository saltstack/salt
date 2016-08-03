# -*- coding: utf-8 -*-
'''
This is a dummy proxy-minion designed for testing the proxy minion subsystem.
'''
from __future__ import absolute_import

# Import python libs
import logging

# This must be present or the Salt loader won't load this module
__proxyenabled__ = ['dummy']


# Variables are scoped to this module so we can have persistent data
# across calls to fns in here.
GRAINS_CACHE = {}
DETAILS = {'services': {'apache':'running',
                        'ntp':'running',
                        'samba':'stopped'}}

# Want logging!
log = logging.getLogger(__file__)


# This does nothing, it's here just as an example and to provide a log
# entry when the module is loaded.
def __virtual__():
    '''
    Only return if all the modules are available
    '''
    log.debug('dummy proxy __virtual__() called...')
    return True


# Every proxy module needs an 'init', though you can
# just put DETAILS['initialized'] = True here if nothing
# else needs to be done.

def init(opts):
    log.debug('dummy proxy init() called...')
    DETAILS['initialized'] = True


def initialized():
    '''
    Since grains are loaded in many different places and some of those
    places occur before the proxy can be initialized, return whether
    our init() function has been called
    '''
    return DETAILS.get('initialized', False)


def grains():
    '''
    Make up some grains
    '''
    DETAILS['grains_cache'] = { 'dummy_grain_1': 'one',
                                'dummy_grain_2': 'two',
                                'dummy_grain_3': 'three',
    }
    return DETAILS['grains_cache']


def grains_refresh():
    '''
    Refresh the grains
    '''
    DETAILS['grains_cache'] = None
    return grains()


def fns():
    return {'details': 'This key is here because a function in '
                       'grains/rest_sample.py called fns() here in the proxymodule.'}


def service_start(name):
    '''
    Start a "service" on the dummy server
    '''
    DETAILS['services'][name] = 'running'
    return 'running' 


def service_stop(name):
    '''
    Stop a "service" on the dummy server
    '''
    DETAILS['services'][name] = 'stopped'
    return 'stopped' 


def service_restart(name):
    '''
    Restart a "service" on the REST server
    '''
    return True


def service_list():
    '''
    List "services" on the REST server
    '''
    return DETAILS['services'].keys()


def service_status(name):
    '''
    Check if a service is running on the REST server
    '''
    if DETAILS['services'][name] == 'running':
        return True


def package_list():
    '''
    List "packages" installed on the REST server
    '''
    r = salt.utils.http.query(DETAILS['url']+'package/list', decode_type='json', decode=True)
    return r['dict']


def package_install(name, **kwargs):
    '''
    Install a "package" on the REST server
    '''
    cmd = DETAILS['url']+'package/install/'+name
    if kwargs.get('version', False):
        cmd += '/'+kwargs['version']
    else:
        cmd += '/1.0'
    r = salt.utils.http.query(cmd, decode_type='json', decode=True)
    return r['dict']


def fix_outage():
    r = salt.utils.http.query(DETAILS['url']+'fix_outage')
    return r


def uptodate(name):

    '''
    Call the REST endpoint to see if the packages on the "server" are up to date.
    '''
    r = salt.utils.http.query(DETAILS['url']+'package/remove/'+name, decode_type='json', decode=True)
    return r['dict']


def package_remove(name):

    '''
    Remove a "package" on the REST server
    '''
    r = salt.utils.http.query(DETAILS['url']+'package/remove/'+name, decode_type='json', decode=True)
    return r['dict']


def package_status(name):
    '''
    Check the installation status of a package on the REST server
    '''
    r = salt.utils.http.query(DETAILS['url']+'package/status/'+name, decode_type='json', decode=True)
    return r['dict']


def ping():
    '''
    Is the REST server up?
    '''
    r = salt.utils.http.query(DETAILS['url']+'ping', decode_type='json', decode=True)
    try:
        return r['dict'].get('ret', False)
    except Exception:
        return False


def shutdown(opts):
    '''
    For this proxy shutdown is a no-op
    '''
    log.debug('rest_sample proxy shutdown() called...')


def test_from_state():
    '''
    Test function so we have something to call from a state
    :return:
    '''
    log.debug('test_from_state called')
    return 'testvalue'
