# -*- coding: utf-8 -*-
'''
This is a simple proxy-minion designed to connect to and communicate with
the bottle-based web service contained in salt/tests/rest.py.

Note this example needs the 'requests' library.
Requests is not a hard dependency for Salt
'''

# Import python libs
import requests
HAS_REST_EXAMPLE = True

__proxyenabled__ = ['rest_sample']


class Proxyconn(object):
    '''
    Interface with the REST sample web service (rest.py at
    https://github.com/cro/salt-proxy-rest)
    '''
    def __init__(self, details):
        self.url = details['url']
        self.grains_cache = {}

    def id(self, opts):
        '''
        Return a unique ID for this proxy minion
        '''
        r = requests.get(self.url+'id')
        return r.text.encode('ascii', 'ignore')

    def grains(self):
        '''
        Get the grains from the proxied device
        '''
        if not self.grains_cache:
            r = requests.get(self.url+'info')
            self.grains_cache = r.json()
        return self.grains_cache

    def grains_refresh(self):
        '''
        Refresh the grains from the proxied device
        '''
        self.grains_cache = {}
        return self.grains()

    def service_start(self, name):
        '''
        Start a "service" on the REST server
        '''
        r = requests.get(self.url+'service/start/'+name)
        return r.json()

    def service_stop(self, name):
        '''
        Stop a "service" on the REST server
        '''
        r = requests.get(self.url+'service/stop/'+name)
        return r.json()

    def service_restart(self, name):
        '''
        Restart a "service" on the REST server
        '''
        r = requests.get(self.url+'service/restart/'+name)
        return r.json()

    def service_list(self):
        '''
        List "services" on the REST server
        '''
        r = requests.get(self.url+'service/list')
        return r.json()

    def service_status(self, name):
        '''
        Check if a service is running on the REST server
        '''
        r = requests.get(self.url+'service/status/'+name)
        return r.json()

    def package_list(self):
        '''
        List "packages" installed on the REST server
        '''
        r = requests.get(self.url+'package/list')
        return r.json()

    def package_install(self, name, **kwargs):
        '''
        Install a "package" on the REST server
        '''
        cmd = self.url+'package/install/'+name
        if 'version' in kwargs:
            cmd += '/'+kwargs['version']
        else:
            cmd += '/1.0'
        r = requests.get(cmd)

    def package_remove(self, name):
        '''
        Remove a "package" on the REST server
        '''
        r = requests.get(self.url+'package/remove/'+name)
        return r.json()

    def package_status(self, name):
        '''
        Check the installation status of a package on the REST server
        '''
        r = requests.get(self.url+'package/status/'+name)
        return r.json()

    def ping(self):
        '''
        Is the REST server up?
        '''
        r = requests.get(self.url+'ping')
        try:
            if r.status_code == 200:
                return True
            else:
                return False
        except Exception:
            return False

    def shutdown(self, opts):
        '''
        For this proxy shutdown is a no-op
        '''
        pass
