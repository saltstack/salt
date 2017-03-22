# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
from datetime import datetime

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.modules.redismod as redismod


class Mockredis(object):
    '''
    Mock redis class
    '''
    class ConnectionError(Exception):
        '''
        Mock ConnectionError class
        '''
        pass


class MockConnect(object):
    '''
    Mock Connect class
    '''
    counter = 0

    def __init__(self):
        self.name = None
        self.pattern = None
        self.value = None
        self.key = None
        self.seconds = None
        self.timestamp = None
        self.field = None
        self.start = None
        self.stop = None
        self.master_host = None
        self.master_port = None

    @staticmethod
    def bgrewriteaof():
        '''
        Mock bgrewriteaof method
        '''
        return 'A'

    @staticmethod
    def bgsave():
        '''
        Mock bgsave method
        '''
        return 'A'

    def config_get(self, pattern):
        '''
        Mock config_get method
        '''
        self.pattern = pattern
        return 'A'

    def config_set(self, name, value):
        '''
        Mock config_set method
        '''
        self.name = name
        self.value = value
        return 'A'

    @staticmethod
    def dbsize():
        '''
        Mock dbsize method
        '''
        return 'A'

    @staticmethod
    def delete():
        '''
        Mock delete method
        '''
        return 'A'

    def exists(self, key):
        '''
        Mock exists method
        '''
        self.key = key
        return 'A'

    def expire(self, key, seconds):
        '''
        Mock expire method
        '''
        self.key = key
        self.seconds = seconds
        return 'A'

    def expireat(self, key, timestamp):
        '''
        Mock expireat method
        '''
        self.key = key
        self.timestamp = timestamp
        return 'A'

    @staticmethod
    def flushall():
        '''
        Mock flushall method
        '''
        return 'A'

    @staticmethod
    def flushdb():
        '''
        Mock flushdb method
        '''
        return 'A'

    def get(self, key):
        '''
        Mock get method
        '''
        self.key = key
        return 'A'

    def hget(self, key, field):
        '''
        Mock hget method
        '''
        self.key = key
        self.field = field
        return 'A'

    def hgetall(self, key):
        '''
        Mock hgetall method
        '''
        self.key = key
        return 'A'

    @staticmethod
    def info():
        '''
        Mock info method
        '''
        return 'A'

    def keys(self, pattern):
        '''
        Mock keys method
        '''
        self.pattern = pattern
        return 'A'

    def type(self, key):
        '''
        Mock type method
        '''
        self.key = key
        return 'A'

    @staticmethod
    def lastsave():
        '''
        Mock lastsave method
        '''
        return datetime.now()

    def llen(self, key):
        '''
        Mock llen method
        '''
        self.key = key
        return 'A'

    def lrange(self, key, start, stop):
        '''
        Mock lrange method
        '''
        self.key = key
        self.start = start
        self.stop = stop
        return 'A'

    @staticmethod
    def ping():
        '''
        Mock ping method
        '''
        MockConnect.counter = MockConnect.counter + 1
        if MockConnect.counter == 1:
            return 'A'
        elif MockConnect.counter in (2, 3, 5):
            raise Mockredis.ConnectionError('foo')

    @staticmethod
    def save():
        '''
        Mock save method
        '''
        return 'A'

    def set(self, key, value):
        '''
        Mock set method
        '''
        self.key = key
        self.value = value
        return 'A'

    @staticmethod
    def shutdown():
        '''
        Mock shutdown method
        '''
        return 'A'

    def slaveof(self, master_host, master_port):
        '''
        Mock slaveof method
        '''
        self.master_host = master_host
        self.master_port = master_port
        return 'A'

    def smembers(self, key):
        '''
        Mock smembers method
        '''
        self.key = key
        return 'A'

    @staticmethod
    def time():
        '''
        Mock time method
        '''
        return 'A'

    def zcard(self, key):
        '''
        Mock zcard method
        '''
        self.key = key
        return 'A'

    def zrange(self, key, start, stop):
        '''
        Mock zrange method
        '''
        self.key = key
        self.start = start
        self.stop = stop
        return 'A'


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.redismod._connect', MagicMock(return_value=MockConnect()))
class RedismodTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.redismod
    '''
    def setup_loader_modules(self):
        return {redismod: {'redis': Mockredis}}

    def test_bgrewriteaof(self):
        '''
        Test to asynchronously rewrite the append-only file
        '''
        self.assertEqual(redismod.bgrewriteaof(), 'A')

    def test_bgsave(self):
        '''
        Test to asynchronously save the dataset to disk
        '''
        self.assertEqual(redismod.bgsave(), 'A')

    def test_config_get(self):
        '''
        Test to get redis server configuration values
        '''
        self.assertEqual(redismod.config_get('*'), 'A')

    def test_config_set(self):
        '''
        Test to set redis server configuration values
        '''
        self.assertEqual(redismod.config_set('name', 'value'), 'A')

    def test_dbsize(self):
        '''
        Test to return the number of keys in the selected database
        '''
        self.assertEqual(redismod.dbsize(), 'A')

    def test_delete(self):
        '''
        Test to deletes the keys from redis, returns number of keys deleted
        '''
        self.assertEqual(redismod.delete(), 'A')

    def test_exists(self):
        '''
        Test to return true if the key exists in redis
        '''
        self.assertEqual(redismod.exists('key'), 'A')

    def test_expire(self):
        '''
        Test to set a keys time to live in seconds
        '''
        self.assertEqual(redismod.expire('key', 'seconds'), 'A')

    def test_expireat(self):
        '''
        Test to set a keys expire at given UNIX time
        '''
        self.assertEqual(redismod.expireat('key', 'timestamp'), 'A')

    def test_flushall(self):
        '''
        Test to remove all keys from all databases
        '''
        self.assertEqual(redismod.flushall(), 'A')

    def test_flushdb(self):
        '''
        Test to remove all keys from the selected database
        '''
        self.assertEqual(redismod.flushdb(), 'A')

    def test_get_key(self):
        '''
        Test to get redis key value
        '''
        self.assertEqual(redismod.get_key('key'), 'A')

    def test_hget(self):
        '''
        Test to get specific field value from a redis hash, returns dict
        '''
        self.assertEqual(redismod.hget('key', 'field'), 'A')

    def test_hgetall(self):
        '''
        Test to get all fields and values from a redis hash, returns dict
        '''
        self.assertEqual(redismod.hgetall('key'), 'A')

    def test_info(self):
        '''
        Test to get information and statistics about the server
        '''
        self.assertEqual(redismod.info(), 'A')

    def test_keys(self):
        '''
        Test to get redis keys, supports glob style patterns
        '''
        self.assertEqual(redismod.keys('pattern'), 'A')

    def test_key_type(self):
        '''
        Test to get redis key type
        '''
        self.assertEqual(redismod.key_type('key'), 'A')

    def test_lastsave(self):
        '''
        Test to get the UNIX time in seconds of the last successful
        save to disk
        '''
        self.assertTrue(redismod.lastsave())

    def test_llen(self):
        '''
        Test to get the length of a list in Redis
        '''
        self.assertEqual(redismod.llen('key'), 'A')

    def test_lrange(self):
        '''
        Test to get a range of values from a list in Redis
        '''
        self.assertEqual(redismod.lrange('key', 'start', 'stop'), 'A')

    def test_ping(self):
        '''
        Test to ping the server, returns False on connection errors
        '''
        self.assertEqual(redismod.ping(), 'A')

        self.assertFalse(redismod.ping())

    def test_save(self):
        '''
        Test to synchronously save the dataset to disk
        '''
        self.assertEqual(redismod.save(), 'A')

    def test_set_key(self):
        '''
        Test to set redis key value
        '''
        self.assertEqual(redismod.set_key('key', 'value'), 'A')

    def test_shutdown(self):
        '''
        Test to synchronously save the dataset to disk and then
        shut down the server
        '''
        self.assertFalse(redismod.shutdown())

        self.assertTrue(redismod.shutdown())

        self.assertFalse(redismod.shutdown())

    def test_slaveof(self):
        '''
        Test to make the server a slave of another instance, or
        promote it as master
        '''
        self.assertEqual(redismod.slaveof('master_host', 'master_port'), 'A')

    def test_smembers(self):
        '''
        Test to get members in a Redis set
        '''
        self.assertListEqual(redismod.smembers('key'), ['A'])

    def test_time(self):
        '''
        Test to return the current server UNIX time in seconds
        '''
        self.assertEqual(redismod.time(), 'A')

    def test_zcard(self):
        '''
        Test to get the length of a sorted set in Redis
        '''
        self.assertEqual(redismod.zcard('key'), 'A')

    def test_zrange(self):
        '''
        Test to get a range of values from a sorted set in Redis by index
        '''
        self.assertEqual(redismod.zrange('key', 'start', 'stop'), 'A')
