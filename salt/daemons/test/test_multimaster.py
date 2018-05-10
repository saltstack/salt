# -*- coding: utf-8 -*-
'''
Tests of utilities that support multiple masters in Salt Raet

'''
from __future__ import absolute_import, print_function, unicode_literals
import sys
from salt.ext.six.moves import map
# pylint: disable=blacklisted-import
if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest
# pylint: enable=blacklisted-import

from ioflo.aid.timing import StoreTimer
from ioflo.base import storing
from ioflo.base.consoling import getConsole
console = getConsole()

from salt.daemons import parse_hostname, extract_masters


def setUpModule():
    console.reinit(verbosity=console.Wordage.concise)


def tearDownModule():
    pass


class BasicTestCase(unittest.TestCase):  # pylint: disable=moved-test-case-class

    def setUp(self):
        self.store = storing.Store(stamp=0.0)
        self.timer = StoreTimer(store=self.store, duration=1.0)
        self.port = 4506
        self.opts = dict(master_port=self.port)

    def tearDown(self):
        pass

    def testParseHostname(self):
        '''
        Test parsing hostname provided according to syntax for opts['master']
        '''
        console.terse("{0}\n".format(self.testParseHostname.__doc__))

        self.assertEquals(parse_hostname('localhost', self.port),
                                       ('localhost', 4506))
        self.assertEquals(parse_hostname('127.0.0.1', self.port),
                                       ('127.0.0.1', 4506))
        self.assertEquals(parse_hostname('10.0.2.100', self.port),
                                        ('10.0.2.100', 4506))
        self.assertEquals(parse_hostname('me.example.com', self.port),
                                        ('me.example.com', 4506))
        self.assertEquals(parse_hostname(
               '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa',
                self.port),
                ('1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa',
                 4506))
        self.assertEquals(parse_hostname('fe80::1%lo0', self.port),
                                                ('fe80::1%lo0', 4506))

        self.assertEquals(parse_hostname('  localhost   ', self.port),
                                               ('localhost', 4506))
        self.assertEquals(parse_hostname('  127.0.0.1   ', self.port),
                                       ('127.0.0.1', 4506))
        self.assertEquals(parse_hostname('   10.0.2.100   ', self.port),
                                        ('10.0.2.100', 4506))
        self.assertEquals(parse_hostname('  me.example.com  ', self.port),
                                        ('me.example.com', 4506))
        self.assertEquals(parse_hostname(
               '  1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa   ',
                self.port),
                ('1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa',
                 4506))
        self.assertEquals(parse_hostname('  fe80::1%lo0  ', self.port),
                                                ('fe80::1%lo0', 4506))

        self.assertEquals(parse_hostname('localhost 4510', self.port),
                                               ('localhost', 4510))
        self.assertEquals(parse_hostname('127.0.0.1 4510', self.port),
                                       ('127.0.0.1', 4510))
        self.assertEquals(parse_hostname('10.0.2.100 4510', self.port),
                                        ('10.0.2.100', 4510))
        self.assertEquals(parse_hostname('me.example.com 4510', self.port),
                                        ('me.example.com', 4510))
        self.assertEquals(parse_hostname(
               '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa 4510',
                self.port),
                ('1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa',
                 4510))
        self.assertEquals(parse_hostname('fe80::1%lo0 4510', self.port),
                                                ('fe80::1%lo0', 4510))

        self.assertEquals(parse_hostname('  localhost     4510 ', self.port),
                                               ('localhost', 4510))
        self.assertEquals(parse_hostname('   127.0.0.1    4510   ', self.port),
                                       ('127.0.0.1', 4510))
        self.assertEquals(parse_hostname('   10.0.2.100   4510   ', self.port),
                                        ('10.0.2.100', 4510))
        self.assertEquals(parse_hostname('   me.example.com    4510   ', self.port),
                                        ('me.example.com', 4510))
        self.assertEquals(parse_hostname(
               '   1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa   4510   ',
                self.port),
                ('1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa',
                 4510))
        self.assertEquals(parse_hostname('   fe80::1%lo0   4510   ', self.port),
                                                ('fe80::1%lo0', 4510))

        self.assertEquals(parse_hostname('localhost abcde', self.port), None)
        self.assertEquals(parse_hostname('127.0.0.1 a4510', self.port), None)
        self.assertEquals(parse_hostname(list([1, 2, 3]), self.port), None)
        self.assertEquals(parse_hostname(list(), self.port), None)
        self.assertEquals(parse_hostname(dict(a=1), self.port), None)
        self.assertEquals(parse_hostname(dict(), self.port), None)
        self.assertEquals(parse_hostname(4510, self.port), None)
        self.assertEquals(parse_hostname(('localhost', 4510), self.port), None)

        self.assertEquals(parse_hostname('localhost:4510', self.port),
                                               ('localhost', 4510))
        self.assertEquals(parse_hostname('127.0.0.1:4510', self.port),
                                       ('127.0.0.1', 4510))
        self.assertEquals(parse_hostname('10.0.2.100:4510', self.port),
                                        ('10.0.2.100', 4510))
        self.assertEquals(parse_hostname('me.example.com:4510', self.port),
                                        ('me.example.com', 4510))
        self.assertEquals(parse_hostname(
               '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa:4510',
                self.port),
                ('1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa',
                 4510))
        self.assertEquals(parse_hostname('fe80::1%lo0:4510', self.port),
                                                      ('fe80::1%lo0:4510', 4506))
        self.assertEquals(parse_hostname('localhost::4510', self.port),
                                                       ('localhost::4510', 4506))

    def testExtractMastersSingle(self):
        '''
        Test extracting from master provided according to syntax for opts['master']
        '''
        console.terse("{0}\n".format(self.testExtractMastersSingle.__doc__))

        master = 'localhost'
        self.opts.update(master=master)
        self.assertEquals(extract_masters(self.opts),
                          [
                              dict(external=('localhost', 4506),
                                   internal=None),
                          ])

        master = '127.0.0.1'
        self.opts.update(master=master)
        self.assertEquals(extract_masters(self.opts),
                          [
                              dict(external=('127.0.0.1', 4506),
                                   internal=None),
                          ])

        master = 'localhost 4510'
        self.opts.update(master=master)
        self.assertEquals(extract_masters(self.opts),
                          [
                              dict(external=('localhost', 4510),
                                   internal=None),
                          ])

        master = '127.0.0.1 4510'
        self.opts.update(master=master)
        self.assertEquals(extract_masters(self.opts),
                          [
                              dict(external=('127.0.0.1', 4510),
                                   internal=None),
                          ])

        master = '10.0.2.23'
        self.opts.update(master=master)
        self.assertEquals(extract_masters(self.opts),
                          [
                              dict(external=('10.0.2.23', 4506),
                                   internal=None),
                          ])

        master = 'me.example.com'
        self.opts.update(master=master)
        self.assertEquals(extract_masters(self.opts),
                                  [
                                      dict(external=('me.example.com', 4506),
                                           internal=None),
                                  ])

        master = '10.0.2.23 4510'
        self.opts.update(master=master)
        self.assertEquals(extract_masters(self.opts),
                                  [
                                      dict(external=('10.0.2.23', 4510),
                                           internal=None),
                                  ])

        master = 'me.example.com 4510'
        self.opts.update(master=master)
        self.assertEquals(extract_masters(self.opts),
                                  [
                                      dict(external=('me.example.com', 4510),
                                           internal=None),
                                  ])

        master = dict(external='10.0.2.23 4510')
        self.opts.update(master=master)
        self.assertEquals(extract_masters(self.opts),
                                  [
                                      dict(external=('10.0.2.23', 4510),
                                           internal=None),
                                  ])

        master = dict(external='10.0.2.23 4510', internal='')
        self.opts.update(master=master)
        self.assertEquals(extract_masters(self.opts),
                                  [
                                      dict(external=('10.0.2.23', 4510),
                                           internal=None),
                                  ])

        master = dict(internal='10.0.2.23 4510')
        self.opts.update(master=master)
        self.assertEquals(extract_masters(self.opts), [])

    def testExtractMastersMultiple(self):
        '''
        Test extracting from master provided according to syntax for opts['master']
        '''
        console.terse("{0}\n".format(self.testExtractMastersMultiple.__doc__))

        master = [
                    'localhost',
                    '10.0.2.23',
                    'me.example.com'
                 ]
        self.opts.update(master=master)
        self.assertEquals(extract_masters(self.opts),
                          [
                            {
                                'external': ('localhost', 4506),
                                'internal': None
                            },
                            {
                                'external': ('10.0.2.23', 4506),
                                'internal': None
                            },
                            {
                                'external': ('me.example.com', 4506),
                                'internal': None
                            },
                          ])

        master = [
                    'localhost 4510',
                    '10.0.2.23 4510',
                    'me.example.com 4510'
                 ]
        self.opts.update(master=master)
        self.assertEquals(extract_masters(self.opts),
                          [
                            {
                                'external': ('localhost', 4510),
                                'internal': None
                            },
                            {
                                'external': ('10.0.2.23', 4510),
                                'internal': None
                            },
                            {
                                'external': ('me.example.com', 4510),
                                'internal': None
                            },
                          ])

        master = [
                    {
                        'external': 'localhost 4510',
                        'internal': '',
                    },
                    {
                        'external': 'me.example.com 4510',
                        'internal': '10.0.2.23 4510',
                    },
                    {
                        'external': 'you.example.com 4509',
                    }
                 ]
        self.opts.update(master=master)
        self.assertEquals(extract_masters(self.opts),
                          [
                            {
                                'external': ('localhost', 4510),
                                'internal': None
                            },
                            {
                                'external': ('me.example.com', 4510),
                                'internal': ('10.0.2.23', 4510)
                            },
                            {
                                'external': ('you.example.com', 4509),
                                'internal': None
                            },
                          ])


def runOne(test):
    '''
    Unittest Runner
    '''
    test = BasicTestCase(test)
    suite = unittest.TestSuite([test])
    unittest.TextTestRunner(verbosity=2).run(suite)


def runSome():
    '''
    Unittest runner
    '''
    tests = []
    names = [
        'testParseHostname',
        'testExtractMastersSingle',
        'testExtractMastersMultiple',
    ]

    tests.extend(list(list(map(BasicTestCase, names))))

    suite = unittest.TestSuite(tests)
    unittest.TextTestRunner(verbosity=2).run(suite)


def runAll():
    '''
    Unittest runner
    '''
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(BasicTestCase))

    unittest.TextTestRunner(verbosity=2).run(suite)


if __name__ == '__main__' and __package__ is None:

    #console.reinit(verbosity=console.Wordage.concise)

    runAll()  # run all unittests

    #runSome()  # only run some

    #runOne('testParseHostname')
