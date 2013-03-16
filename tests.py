#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Usage examples:
#
#   tests
#   tests testPing
#   VERBOSITY=9 tests
#   VALID_TARGETS="salt min1 min2" tests testMinions

import os
import sys
import json
import re
try:
    # check the system path first
    import unittest2 as unittest
except ImportError:
    if sys.version_info >= (2,7):
        # unittest2 features are native in Python 2.7
        import unittest
    else:
        raise
import requests


CONFIG = {'API_ROOT_URL': 'http://salt/api/salt/',
          'VALID_TARGETS': ['salt'],
          'INVALID_TARGETS': ['nonexist'],
          'VERBOSITY': 1}

for (k, v) in CONFIG.iteritems():
    if k in os.environ:
        if re.match('.+ .+', os.environ[k]):
            setattr(sys.modules[__name__], k, os.environ[k].split(' '))
        elif re.match('\d+', os.environ[k]):
            setattr(sys.modules[__name__], k, int(os.environ[k]))
        else:
            setattr(sys.modules[__name__], k, os.environ[k])
    else:
        setattr(sys.modules[__name__], k, v)


def url(*paths, **kwargs):
    # TODO: if there is a '/' prefix, remove it, on all paths
    url = API_ROOT_URL + '/'.join(paths)
    url += '/' if not url.endswith('/') else ''
    # TODO: add urlencoded arguments through **kwargs
    return url


class testMinions(unittest.TestCase):
    def test_list_minions(self):
        r = requests.get(url('minions'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['Content-Type'], 'application/json')
        self.assertTrue(len(json.loads(r.content).keys()))

    def test_minions(self):
        for target in VALID_TARGETS:
            r = requests.get(url('minions', target))
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertTrue(len(json.loads(r.content).keys()) == 1)


class testJobs(unittest.TestCase):
    def test_list_jobs(self):
        r = requests.get(url('jobs'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['Content-Type'], 'application/json')
        self.assertTrue(re.match('\d+', json.loads(r.content).keys()[0]))

    @unittest.skip("not implemented yet")
    def test_lookup_jid(self):
        pass

    @unittest.skip("does not return 404 yet")
    def test_lookup_invalid_jid(self):
        r = requests.get(url('jobs', '20999999999999999999'))
        self.assertEqual(r.status_code, 404)


class testPing(unittest.TestCase):
    def test_ping(self):
        for target in VALID_TARGETS:
            r = requests.get(url('ping', target))
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertTrue(json.loads(r.content)[target])

    @unittest.skip("does not return 404 yet")
    def test_invalid_ping(self):
        for target in INVALID_TARGETS:
            r = requests.get(url('ping', target))
            self.assertEqual(r.status_code, 404)
            #self.assertEqual(json.loads(r.content), {})


class testApi(unittest.TestCase):
    def test_get_index(self):
        r = requests.get(url())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')

    def test_ping(self):
        for target in VALID_TARGETS:
            r = requests.post(url(),
                              data={'client': 'local',
                                    'tgt': target,
                                    'fun': 'test.ping'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertTrue(json.loads(r.content)[target])

    @unittest.skip("does not return 404 yet")
    def test_invalid_ping(self):
        for target in INVALID_TARGETS:
            r = requests.post(url(),
                              data={'client': 'local',
                                    'tgt': target,
                                    'fun': 'test.ping'})
            self.assertEqual(r.status_code, 404)
            #self.assertEqual(json.loads(r.content), {})

    def test_grains_items(self):
        for target in VALID_TARGETS:
            r = requests.post(url(),
                              data={'client': 'local',
                                    'tgt': target,
                                    'fun': 'grains.items'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertTrue(target in json.loads(r.content)[target]['nodename'])


if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    all_tests = [
        testApi,
        testMinions,
        testJobs,
        testPing,
        ]
    run_tests = []

    # called without arguments
    if len(sys.argv) == 1:
        for test in all_tests:
            suite.addTests(loader.loadTestsFromTestCase(test))
            run_tests.append(str(test))
    # called with arguments, run only specified classes
    else:
        sys.argv.pop(0)
        for name in sys.argv:
            test = getattr(sys.modules[__name__], name)
            suite.addTests(loader.loadTestsFromTestCase(test))
            run_tests.append(name)

    unittest.TextTestRunner(verbosity=VERBOSITY).run(suite)
