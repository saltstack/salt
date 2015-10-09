# -*- coding: utf-8 -*-
'''
    tests.unit.context_test
    ~~~~~~~~~~~~~~~~~~~~
'''
# Import python libs
from __future__ import absolute_import
import tornado.stack_context
import threading
import time

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import Salt libs
from salt.utils.context import ContextDict, NamespacedDictWrapper


class ContextDictTests(TestCase):
    def setUp(self):
        self.cd = ContextDict()
        # set a global value
        self.cd['foo'] = 'global'

    def test_threads(self):
        rets = []

        def tgt(x, s):
            inner_ret = []
            over = self.cd.clone()

            inner_ret.append(self.cd.get('foo'))
            with over:
                inner_ret.append(over.get('foo'))
                over['foo'] = x
                inner_ret.append(over.get('foo'))
                time.sleep(s)
                inner_ret.append(over.get('foo'))
                rets.append(inner_ret)

        threads = []
        NUM_JOBS = 5
        for x in xrange(0, NUM_JOBS):
            s = NUM_JOBS - x
            t = threading.Thread(target=tgt, args=(x, s))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        for r in rets:
            self.assertEqual(r[0], r[1])
            self.assertEqual(r[2], r[3])

    def test_basic(self):
        '''Test that the contextDict is a dict
        '''
        # ensure we get the global value
        self.assertEqual(
            dict(self.cd),
            {'foo': 'global'},
        )

    def test_override(self):
        over = self.cd.clone()
        over['bar'] = 'global'
        self.assertEqual(
            dict(over),
            {'foo': 'global', 'bar': 'global'},
        )
        self.assertEqual(
            dict(self.cd),
            {'foo': 'global'},
        )
        with tornado.stack_context.StackContext(lambda: over):
            self.assertEqual(
                dict(over),
                {'foo': 'global', 'bar': 'global'},
            )
            self.assertEqual(
                dict(self.cd),
                {'foo': 'global', 'bar': 'global'},
            )
            over['bar'] = 'baz'
            self.assertEqual(
                dict(over),
                {'foo': 'global', 'bar': 'baz'},
            )
            self.assertEqual(
                dict(self.cd),
                {'foo': 'global', 'bar': 'baz'},
            )
        self.assertEqual(
            dict(over),
            {'foo': 'global', 'bar': 'baz'},
        )
        self.assertEqual(
            dict(self.cd),
            {'foo': 'global'},
        )

    def test_multiple_contexts(self):
        cds = []
        for x in xrange(0, 10):
            cds.append(self.cd.clone(bar=x))
        for x, cd in enumerate(cds):
            self.assertNotIn('bar', self.cd)
            with tornado.stack_context.StackContext(lambda: cd):
                self.assertEqual(
                    dict(self.cd),
                    {'bar': x, 'foo': 'global'},
                )
        self.assertNotIn('bar', self.cd)


class NamespacedDictWrapperTests(TestCase):
    PREFIX = 'prefix'

    def setUp(self):
        self._dict = {}

    def test_single_key(self):
        self._dict['prefix'] = {'foo': 'bar'}
        w = NamespacedDictWrapper(self._dict, 'prefix')
        self.assertEqual(w['foo'], 'bar')

    def test_multiple_key(self):
        self._dict['prefix'] = {'foo': {'bar': 'baz'}}
        w = NamespacedDictWrapper(self._dict, ('prefix', 'foo'))
        self.assertEqual(w['bar'], 'baz')
