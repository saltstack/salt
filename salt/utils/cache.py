# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import, print_function
import os
import re
import time
import logging
try:
    import msgpack
    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False

# Import salt libs
import salt.config
import salt.payload
import salt.utils.dictupdate

# Import third party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin
try:
    import zmq
    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

log = logging.getLogger(__name__)


class CacheFactory(object):
    '''
    Cache which can use a number of backends
    '''
    @classmethod
    def factory(cls, backend, ttl, *args, **kwargs):
        log.info('Factory backend: {0}'.format(backend))
        if backend == 'memory':
            return CacheDict(ttl, *args, **kwargs)
        elif backend == 'disk':
            return CacheDisk(ttl, kwargs['minion_cache_path'], *args, **kwargs)
        else:
            log.error('CacheFactory received unrecognized cache type')


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


class CacheDisk(CacheDict):
    '''
    Class that represents itself as a dictionary to a consumer
    but uses a disk-based backend. Serialization and de-serialization
    is done with msgpack
    '''
    def __init__(self, ttl, path, *args, **kwargs):
        super(CacheDisk, self).__init__(ttl, *args, **kwargs)
        self._path = path
        self._dict = {}
        self._read()

    def _enforce_ttl_key(self, key):
        '''
        Enforce the TTL to a specific key, delete if its past TTL
        '''
        if key not in self._key_cache_time:
            return
        if time.time() - self._key_cache_time[key] > self._ttl:
            del self._key_cache_time[key]
            self._dict.__delitem__(key)

    def __contains__(self, key):
        self._enforce_ttl_key(key)
        return self._dict.__contains__(key)

    def __getitem__(self, key):
        '''
        Check if the key is ttld out, then do the get
        '''
        self._enforce_ttl_key(key)
        return self._dict.__getitem__(key)

    def __setitem__(self, key, val):
        '''
        Make sure to update the key cache time
        '''
        self._key_cache_time[key] = time.time()
        self._dict.__setitem__(key, val)
        # Do the same as the parent but also persist
        self._write()

    def __delitem__(self, key):
        '''
        Make sure to remove the key cache time
        '''
        del self._key_cache_time[key]
        self._dict.__delitem__(key)
        # Do the same as the parent but also persist
        self._write()

    def _read(self):
        '''
        Read in from disk
        '''
        if not HAS_MSGPACK or not os.path.exists(self._path):
            return
        with salt.utils.fopen(self._path, 'rb') as fp_:
            cache = msgpack.load(fp_, encoding=__salt_system_encoding__)
        if "CacheDisk_cachetime" in cache:  # new format
            self._dict = cache["CacheDisk_data"]
            self._key_cache_time = cache["CacheDisk_cachetime"]
        else:  # old format
            self._dict = cache
            timestamp = os.path.getmtime(self._path)
            for key in self._dict:
                self._key_cache_time[key] = timestamp
        if log.isEnabledFor(logging.DEBUG):
            log.debug('Disk cache retrieved: {0}'.format(cache))

    def _write(self):
        '''
        Write out to disk
        '''
        if not HAS_MSGPACK:
            return
        # TODO Add check into preflight to ensure dir exists
        # TODO Dir hashing?
        with salt.utils.fopen(self._path, 'wb+') as fp_:
            cache = {
                "CacheDisk_data": self._dict,
                "CacheDisk_cachetime": self._key_cache_time
            }
            msgpack.dump(cache, fp_, use_bin_type=True)


class CacheCli(object):
    '''
    Connection client for the ConCache. Should be used by all
    components that need the list of currently connected minions
    '''

    def __init__(self, opts):
        '''
        Sets up the zmq-connection to the ConCache
        '''
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
            paterns = list(self.cache.values())
            paterns.sort()
            for idx in range(self.clear_size):
                del self.cache[paterns[idx][2]]

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


class ContextCache(object):
    def __init__(self, opts, name):
        '''
        Create a context cache
        '''
        self.opts = opts
        self.cache_path = os.path.join(opts['cachedir'], 'context', '{0}.p'.format(name))
        self.serial = salt.payload.Serial(self.opts)

    def cache_context(self, context):
        '''
        Cache the given context to disk
        '''
        if not os.path.isdir(os.path.dirname(self.cache_path)):
            os.mkdir(os.path.dirname(self.cache_path))
        with salt.utils.fopen(self.cache_path, 'w+b') as cache:
            self.serial.dump(context, cache)

    def get_cache_context(self):
        '''
        Retrieve a context cache from disk
        '''
        with salt.utils.fopen(self.cache_path, 'rb') as cache:
            return self.serial.load(cache)


def context_cache(func):
    '''
    A decorator to be used module functions which need to cache their
    context.

    To evaluate a __context__ and re-hydrate it if a given key
    is empty or contains no items, pass a list of keys to evaulate.
    '''
    def context_cache_wrap(*args, **kwargs):
        func_context = func.__globals__['__context__']
        func_opts = func.__globals__['__opts__']
        func_name = func.__globals__['__name__']

        context_cache = ContextCache(func_opts, func_name)
        if not func_context and os.path.isfile(context_cache.cache_path):
            salt.utils.dictupdate.update(func_context, context_cache.get_cache_context())
        else:
            context_cache.cache_context(func_context)
        return func(*args, **kwargs)
    return context_cache_wrap


# test code for the CacheCli
if __name__ == '__main__':

    opts = salt.config.master_config('/etc/salt/master')

    ccli = CacheCli(opts)

    ccli.put_cache(['test1', 'test10', 'test34'])
    ccli.put_cache(['test12'])
    ccli.put_cache(['test18'])
    ccli.put_cache(['test21'])
    print('minions: {0}'.format(ccli.get_cached()))
