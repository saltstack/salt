# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import print_function
from __future__ import absolute_import
import os
import re
import time

# Import salt libs
import salt.config
import salt.payload

# Import third party libs
try:
    import zmq
    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False


class CacheDict(dict):
    '''
    Subclass of dict that will lazily delete items past ttl
    '''
    def __init__(self, ttl, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self._ttl = ttl
        self._key_cache_time = {}

    def _enforce_ttl_key(self, key):
        '''
        Enforce the TTL to a specific key, delete if its past TTL
        '''
        if key not in self._key_cache_time:
            return
        if time.time() - self._key_cache_time[key] > self._ttl:
            del self._key_cache_time[key]
            dict.__delitem__(self, key)

    def __getitem__(self, key):
        '''
        Check if the key is ttld out, then do the get
        '''
        self._enforce_ttl_key(key)
        return dict.__getitem__(self, key)

    def __setitem__(self, key, val):
        '''
        Make sure to update the key cache time
        '''
        self._key_cache_time[key] = time.time()
        dict.__setitem__(self, key, val)

    def __contains__(self, key):
        self._enforce_ttl_key(key)
        return dict.__contains__(self, key)


class CacheCli(object):
    '''
    Connection client for the ConCache. Should be used by all
    components that need the list of currently connected minions
    '''

    def __init__(self, opts):
        '''
        Sets up the zmq-connection to the ConCache
        '''
        super(CacheCli, self).__init__()
        self.opts = opts
        self.serial = salt.payload.Serial(self.opts.get('serial', ''))
        self.cache_sock = os.path.join(self.opts['sock_dir'], 'con_cache.ipc')
        self.cache_upd_sock = os.path.join(
            self.opts['sock_dir'], 'con_upd.ipc')

        context = zmq.Context()

        # the socket for talking to the cache
        self.creq_out = context.socket(zmq.REQ)
        self.creq_out.setsockopt(zmq.LINGER, 100)
        self.creq_out.connect('ipc://' + self.cache_sock)

        # the socket for sending updates to the cache
        self.cupd_out = context.socket(zmq.PUB)
        self.cupd_out.setsockopt(zmq.LINGER, 1)
        self.cupd_out.connect('ipc://' + self.cache_upd_sock)

    def put_cache(self, minions):
        '''
        published the given minions to the ConCache
        '''
        self.cupd_out.send(self.serial.dumps(minions))

    def get_cached(self):
        '''
        queries the ConCache for a list of currently connected minions
        '''
        msg = self.serial.dumps('minions')
        self.creq_out.send(msg)
        min_list = self.serial.loads(self.creq_out.recv())
        return min_list


class CacheRegex(object):
    '''
    Create a regular expression object cache for the most frequently
    used patterns to minimize compilation of the same patterns over
    and over again
    '''
    def __init__(self, prepend='', append='', size=1000,
                 keep_fraction=0.8, max_age=3600):
        self.prepend = prepend
        self.append = append
        self.size = size
        self.clear_size = int(size - size * (keep_fraction))
        if self.clear_size >= size:
            self.clear_size = int(size/2) + 1
            if self.clear_size > size:
                self.clear_size = size
        self.max_age = max_age
        self.cache = {}
        self.timestamp = time.time()

    def clear(self):
        '''
        Clear the cache
        '''
        self.cache.clear()

    def sweep(self):
        '''
        Sweep the cache and remove the outdated or least frequently
        used entries
        '''
        if self.max_age < time.time() - self.timestamp:
            self.clear()
            self.timestamp = time.time()
        else:
            paterns = self.cache.values()
            paterns.sort()
            for i in xrange(self.clear_size):
                del self.cache[paterns[i][2]]

    def get(self, pattern):
        '''
        Get a compiled regular expression object based on pattern and
        cache it when it is not in the cache already
        '''
        try:
            self.cache[pattern][0] += 1
            return self.cache[pattern][1]
        except KeyError:
            pass
        if len(self.cache) > self.size:
            self.sweep()
        regex = re.compile('{0}{1}{2}'.format(
            self.prepend, pattern, self.append))
        self.cache[pattern] = [1, regex, pattern, time.time()]
        return regex


# test code for the CacheCli
if __name__ == '__main__':

    opts = salt.config.master_config('/etc/salt/master')

    ccli = CacheCli(opts)

    ccli.put_cache(['test1', 'test10', 'test34'])
    ccli.put_cache(['test12'])
    ccli.put_cache(['test18'])
    ccli.put_cache(['test21'])
    print('minions: {0}'.format(ccli.get_cached()))
