"""
tests.unit.context_test
~~~~~~~~~~~~~~~~~~~~~~~
"""

import threading
import time

import pytest

import salt.ext.tornado.gen
import salt.ext.tornado.stack_context
import salt.utils.json
from salt.ext.tornado.testing import AsyncTestCase, gen_test
from salt.utils.context import ContextDict, NamespacedDictWrapper
from tests.support.unit import TestCase


class ContextDictTests(AsyncTestCase):
    # how many threads/coroutines to run at a time
    num_concurrent_tasks = 5

    def setUp(self):
        super().setUp()
        self.cd = ContextDict()
        # set a global value
        self.cd["foo"] = "global"

    @pytest.mark.slow_test
    def test_threads(self):
        """Verify that ContextDict overrides properly within threads"""
        rets = []

        def tgt(x, s):
            inner_ret = []
            over = self.cd.clone()

            inner_ret.append(self.cd.get("foo"))
            with over:
                inner_ret.append(over.get("foo"))
                over["foo"] = x
                inner_ret.append(over.get("foo"))
                time.sleep(s)
                inner_ret.append(over.get("foo"))
                rets.append(inner_ret)

        threads = []
        for x in range(0, self.num_concurrent_tasks):
            s = self.num_concurrent_tasks - x
            t = threading.Thread(target=tgt, args=(x, s))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        for r in rets:
            self.assertEqual(r[0], r[1])
            self.assertEqual(r[2], r[3])

    @gen_test
    @pytest.mark.slow_test
    def test_coroutines(self):
        """Verify that ContextDict overrides properly within coroutines"""

        @salt.ext.tornado.gen.coroutine
        def secondary_coroutine(over):
            raise salt.ext.tornado.gen.Return(over.get("foo"))

        @salt.ext.tornado.gen.coroutine
        def tgt(x, s, over):
            inner_ret = []
            # first grab the global
            inner_ret.append(self.cd.get("foo"))
            # grab the child's global (should match)
            inner_ret.append(over.get("foo"))
            # override the global
            over["foo"] = x
            inner_ret.append(over.get("foo"))
            # sleep for some time to let other coroutines do this section of code
            yield salt.ext.tornado.gen.sleep(s)
            # get the value of the global again.
            inner_ret.append(over.get("foo"))
            # Call another coroutine to verify that we keep our context
            r = yield secondary_coroutine(over)
            inner_ret.append(r)
            raise salt.ext.tornado.gen.Return(inner_ret)

        futures = []

        for x in range(0, self.num_concurrent_tasks):
            s = self.num_concurrent_tasks - x
            over = self.cd.clone()

            # pylint: disable=cell-var-from-loop
            f = salt.ext.tornado.stack_context.run_with_stack_context(
                salt.ext.tornado.stack_context.StackContext(lambda: over),
                lambda: tgt(x, s / 5.0, over),
            )
            # pylint: enable=cell-var-from-loop
            futures.append(f)

        wait_iterator = salt.ext.tornado.gen.WaitIterator(*futures)
        while not wait_iterator.done():
            r = yield wait_iterator.next()  # pylint: disable=incompatible-py3-code
            self.assertEqual(r[0], r[1])  # verify that the global value remails
            self.assertEqual(r[2], r[3])  # verify that the override sticks locally
            self.assertEqual(
                r[3], r[4]
            )  # verify that the override sticks across coroutines

    def test_basic(self):
        """Test that the contextDict is a dict"""
        # ensure we get the global value
        self.assertEqual(
            dict(self.cd),
            {"foo": "global"},
        )

    def test_override(self):
        over = self.cd.clone()
        over["bar"] = "global"
        self.assertEqual(
            dict(over),
            {"foo": "global", "bar": "global"},
        )
        self.assertEqual(
            dict(self.cd),
            {"foo": "global"},
        )
        with over:
            self.assertEqual(
                dict(over),
                {"foo": "global", "bar": "global"},
            )
            self.assertEqual(
                dict(self.cd),
                {"foo": "global", "bar": "global"},
            )
            over["bar"] = "baz"
            self.assertEqual(
                dict(over),
                {"foo": "global", "bar": "baz"},
            )
            self.assertEqual(
                dict(self.cd),
                {"foo": "global", "bar": "baz"},
            )
        self.assertEqual(
            dict(over),
            {"foo": "global", "bar": "baz"},
        )
        self.assertEqual(
            dict(self.cd),
            {"foo": "global"},
        )

    def test_multiple_contexts(self):
        cds = []
        for x in range(0, 10):
            cds.append(self.cd.clone(bar=x))
        for x, cd in enumerate(cds):
            self.assertNotIn("bar", self.cd)
            with cd:
                self.assertEqual(
                    dict(self.cd),
                    {"bar": x, "foo": "global"},
                )
        self.assertNotIn("bar", self.cd)


class NamespacedDictWrapperTests(TestCase):
    PREFIX = "prefix"

    def setUp(self):
        self._dict = {}

    def test_single_key(self):
        self._dict["prefix"] = {"foo": "bar"}
        w = NamespacedDictWrapper(self._dict, "prefix")
        self.assertEqual(w["foo"], "bar")

    def test_multiple_key(self):
        self._dict["prefix"] = {"foo": {"bar": "baz"}}
        w = NamespacedDictWrapper(self._dict, ("prefix", "foo"))
        self.assertEqual(w["bar"], "baz")

    def test_json_dumps_single_key(self):
        self._dict["prefix"] = {"foo": {"bar": "baz"}}
        w = NamespacedDictWrapper(self._dict, "prefix")
        self.assertEqual(salt.utils.json.dumps(w), '{"foo": {"bar": "baz"}}')

    def test_json_dumps_multiple_key(self):
        self._dict["prefix"] = {"foo": {"bar": "baz"}}
        w = NamespacedDictWrapper(self._dict, ("prefix", "foo"))
        self.assertEqual(salt.utils.json.dumps(w), '{"bar": "baz"}')
