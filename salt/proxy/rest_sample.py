# -*- coding: utf-8 -*-
'''
Routines to set up a minion
'''

# Import python libs
import logging
import os
import requests
HAS_REST_EXAMPLE = True

__proxyenabled__ = ['rest_sample']

class Proxyconn(object):

    def __init__(self, details):
        self.url = details['url']
        self.grains_cache = {}

    def id(self, opts):
        r = requests.get(self.url+'id')
        return r.text.encode('ascii', 'ignore')

    def proxytype(self):
        return 'rest_example'

    def grains(self):
        if not self.grains_cache:
            r = requests.get(self.url+'info')
            self.grains_cache = r.json()
        return self.grains_cache

    def grains_refresh(self):
       self.grains_cache = {}
       return self.grains()


    def service_start(self, name):
        r = requests.get(self.url+'service/start/'+name)
        return r.json()


    def service_stop(self, name):
        r = requests.get(self.url+'service/stop/'+name)
        return r.json()


    def service_restart(self, name):
        r = requests.get(self.url+'service/restart/'+name)
        return r.json()


    def service_list(self):
        r = requests.get(self.url+'service/list')
        return r.json()

    def service_status(self, name):
        r = requests.get(self.url+'service/status/'+name)
        return r.json()


    def package_list(self):
        r = requests.get(self.url+'package/list')
        return r.json()

    def package_install(self, name, **kwargs):
        cmd = self.url+'package/install/'+name
        if 'version' in kwargs:
            cmd += '/'+kwargs['version']
        else:
            cmd += '/1.0'
        r = requests.get(cmd)

    def package_remove(self, name):
        r = requests.get(self.url+'package/remove/'+name)
        return r.json()

    def package_status(self, name):
        r = requests.get(self.url+'package/status/'+name)
        return r.json()

    def ping(self):
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
