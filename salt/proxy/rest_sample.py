# -*- coding: utf-8 -*-
'''
This is a simple proxy-minion designed to connect to and communicate with
the bottle-based web service contained in salt/tests/rest.py.

Note this example needs the 'requests' library.
Requests is not a hard dependency for Salt
'''
from __future__ import absolute_import

# Import python libs
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

HAS_REST_EXAMPLE = True

__proxyenabled__ = ['rest_sample']

grains_cache = {}
url = 'http://172.16.207.1:8000/'


def __virtual__():
    '''
    Only return if all the modules are available
    '''
    if not HAS_REQUESTS:
        return False
    return True


#    Interface with the REST sample web service (rest.py at
#    https://github.com/cro/salt-proxy-rest)
def init():
    pass

def id():
    '''
    Return a unique ID for this proxy minion
    '''
    r = requests.get(url+'id')
    return r.text.encode('ascii', 'ignore')

def grains():
    '''
    Get the grains from the proxied device
    '''
    if not grains_cache:
        r = requests.get(url+'info')
        self.grains_cache = r.json()
    return grains_cache

def grains_refresh():
    '''
    Refresh the grains from the proxied device
    '''
    grains_cache = {}
    return grains()

def service_start(name):
    '''
    Start a "service" on the REST server
    '''
    r = requests.get(url+'service/start/'+name)
    return r.json()

def service_stop(name):
    '''
    Stop a "service" on the REST server
    '''
    r = requests.get(url+'service/stop/'+name)
    return r.json()

def service_restart(name):
    '''
    Restart a "service" on the REST server
    '''
    r = requests.get(url+'service/restart/'+name)
    return r.json()

def service_list():
    '''
    List "services" on the REST server
    '''
    r = requests.get(url+'service/list')
    return r.json()

def service_status(name):
    '''
    Check if a service is running on the REST server
    '''
    r = requests.get(url+'service/status/'+name)
    return r.json()

def package_list():
    '''
    List "packages" installed on the REST server
    '''
    r = requests.get(url+'package/list')
    return r.json()

def package_install(name, **kwargs):
    '''
    Install a "package" on the REST server
    '''
    cmd = self.url+'package/install/'+name
    if 'version' in kwargs:
        cmd += '/'+kwargs['version']
    else:
        cmd += '/1.0'
    r = requests.get(cmd)

def package_remove(name):
    '''
    Remove a "package" on the REST server
    '''
    r = requests.get(url+'package/remove/'+name)
    return r.json()

def package_status(name):
    '''
    Check the installation status of a package on the REST server
    '''
    r = requests.get(self.url+'package/status/'+name)
    return r.json()

def ping():
    '''
    Is the REST server up?
    '''
    r = requests.get(url+'ping')
    try:
        if r.status_code == 200:
            return True
        else:
            return False
    except Exception:
        return False

def shutdown(opts):
    '''
    For this proxy shutdown is a no-op
    '''
    pass
