# -*- coding: utf-8 -*-
"""
Tests for the salt-run command
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt Testing libs
from tests.support.case import ShellCase

log = logging.getLogger(__name__)


class ManageTest(ShellCase):
    """
    Test the manage runner
    """

    def test_queue_insert_delete(self):
        """
        Test inserting and deleting from a queue
        """
        ret = self.run_run_plus("queue.insert", "testqueue", "a")
        self.assertTrue(ret["return"], msg="Failure inserting item into test queue")

        ret = self.run_run_plus("queue.delete", "testqueue", "a")
        self.assertTrue(ret["return"], msg="Failure to delete item from test queue")

    def test_queue_list(self):
        """
        Test queue item listing
        """
        ret = self.run_run_plus("queue.insert", "testqueue", ["a", "z", "b", "r", "e"])
        self.assertTrue(ret["return"], msg="Failure inserting items into test queue")
        log.debug("ELM - ret == {}".format(ret))

        # default returns lexical sort of items
        ret = self.run_run_plus("queue.list_items", "testqueue")
        self.assertEqual(
            ret["return"],
            ["a", "b", "e", "r", "z"],
            msg='queue item list not returned as expected ("{0}" returned)'.format(
                ret["return"]
            ),
        )

        # fifo list
        ret = self.run_run_plus("queue.list_items", "testqueue", mode="fifo")
        # ensure fifo output
        self.assertEqual(
            ret["return"],
            ["a", "z", "b", "r", "e"],
            msg="queue items not listed in fifo order as expected",
        )

        # lifo list
        ret = self.run_run_plus("queue.list_items", "testqueue", mode="lifo")
        # ensure lifo output
        self.assertEqual(
            ret["return"],
            ["e", "r", "b", "z", "a"],
            msg="queue items not listed in lifo order as expected",
        )

        # delete items from queue
        ret = self.run_run_plus("queue.delete", "testqueue", ["a", "z", "b", "r", "e"])
        self.assertTrue(ret["return"], msg="Failure deleting items from test queue")

    def test_queue_pop(self):
        """
        Test popping items from queue
        """
        ret = self.run_run_plus(
            "queue.insert", "testqueue", ["z", "t", "a", "r", "b", "e"]
        )
        self.assertTrue(ret["return"], msg="Failure inserting items into test queue")

        # default returns first item from a lexical sorted list
        expected_return = ["a"]
        ret = self.run_run_plus("queue.pop", "testqueue")
        self.assertEqual(
            ret["return"],
            expected_return,
            msg='Item returned from queue "{0}" not the expected item "{1}"'.format(
                ret["return"], expected_return
            ),
        )

        # pop fifo
        ret = self.run_run_plus("queue.pop", "testqueue", mode="fifo")
        expected_return = ["z"]
        self.assertEqual(
            ret["return"],
            expected_return,
            msg='Item returned from queue "{0}" not the expected item "{1}"'.format(
                ret["return"], expected_return
            ),
        )

        # pop lifo
        ret = self.run_run_plus("queue.pop", "testqueue", mode="lifo")
        expected_return = ["e"]
        self.assertEqual(
            ret["return"],
            expected_return,
            msg='Item returned from queue "{0}" not the expected item "{1}"'.format(
                ret["return"], expected_return
            ),
        )

        # delete items from queue
        ret = self.run_run_plus("queue.delete", "testqueue", ["t", "r", "b"])
        self.assertTrue(ret["return"], msg="Failure deleting items from test queue")

    def test_queue_process(self):
        """
        Test processing queue items
        """
        ret = self.run_run_plus(
            "queue.insert", "testqueue", ["z", "t", "a", "r", "b", "e"]
        )
        self.assertTrue(ret["return"], msg="Failure inserting items into test queue")

        # process queue items, default order is lexically by item
        ret = self.run_run_plus("queue.process_queue", "testqueue", 2)
        self.assertTrue("items" in ret["return"], msg='Return does not include "items"')
        self.assertEqual(
            ret["return"]["items"],
            ["a", "b"],
            msg='Items returned from process queue runner not as expected (items returned "{0}")'.format(
                ret["return"]["items"]
            ),
        )

        # delete items from queue
        ret = self.run_run_plus("queue.delete", "testqueue", ["z", "t", "r", "e"])
        self.assertTrue(ret["return"], msg="Failure deleting items from test queue")

    def test_queue_process_all(self):
        """
        Test processing queue items
        """
        ret = self.run_run_plus(
            "queue.insert", "testqueue", ["z", "t", "a", "r", "b", "e"]
        )
        self.assertTrue(ret["return"], msg="Failure inserting items into test queue")

        # process queue items, default order is lexically by item
        ret = self.run_run_plus("queue.process_queue", "testqueue", "all")
        self.assertTrue("items" in ret["return"], msg='Return does not include "items"')
        self.assertEqual(
            ret["return"]["items"],
            ["a", "b", "e", "r", "t", "z"],
            msg='Items returned from process queue runner not as expected (items returned "{0}")'.format(
                ret["return"]["items"]
            ),
        )

    def test_queue_process_fifo(self):
        """
        Test processing queue items
        """
        ret = self.run_run_plus(
            "queue.insert", "testqueue", ["z", "t", "a", "r", "b", "e"]
        )
        self.assertTrue(ret["return"], msg="Failure inserting items into test queue")

        # process queue items, default order is lexically by item
        ret = self.run_run_plus("queue.process_queue", "testqueue", 2, mode="fifo")
        self.assertTrue("items" in ret["return"], msg='Return does not include "items"')
        self.assertEqual(
            ret["return"]["items"],
            ["z", "t"],
            msg='Items returned from process queue runner not as expected (items returned "{0}")'.format(
                ret["return"]["items"]
            ),
        )

        # delete items from queue
        ret = self.run_run_plus("queue.delete", "testqueue", ["a", "b", "r", "e"])
        self.assertTrue(ret["return"], msg="Failure deleting items from test queue")

    def test_queue_process_lifo(self):
        """
        Test processing queue items
        """
        ret = self.run_run_plus(
            "queue.insert", "testqueue", ["z", "t", "a", "r", "b", "e"]
        )
        self.assertTrue(ret["return"], msg="Failure inserting items into test queue")

        # process queue items, default order is lexically by item
        ret = self.run_run_plus("queue.process_queue", "testqueue", 2, mode="lifo")
        self.assertTrue("items" in ret["return"], msg='Return does not include "items"')
        self.assertEqual(
            ret["return"]["items"],
            ["e", "b"],
            msg='Items returned from process queue runner not as expected (items returned "{0}")'.format(
                ret["return"]["items"]
            ),
        )

        # delete items from queue
        ret = self.run_run_plus("queue.delete", "testqueue", ["z", "t", "a", "r"])
        self.assertTrue(ret["return"], msg="Failure deleting items from test queue")

    def test_queue_process_fifo_all(self):
        """
        Test processing queue items
        """
        ret = self.run_run_plus(
            "queue.insert", "testqueue", ["z", "t", "a", "r", "b", "e"]
        )
        self.assertTrue(ret["return"], msg="Failure inserting items into test queue")

        # process queue items, default order is lexically by item
        ret = self.run_run_plus("queue.process_queue", "testqueue", "all", mode="fifo")
        self.assertTrue("items" in ret["return"], msg='Return does not include "items"')
        self.assertEqual(
            ret["return"]["items"],
            ["z", "t", "a", "r", "b", "e"],
            msg='Items returned from process queue runner not as expected (items returned "{0}")'.format(
                ret["return"]["items"]
            ),
        )

    def test_queue_process_lifo_all(self):
        """
        Test processing queue items
        """
        ret = self.run_run_plus(
            "queue.insert", "testqueue", ["z", "t", "a", "r", "b", "e"]
        )
        self.assertTrue(ret["return"], msg="Failure inserting items into test queue")

        # process queue items, default order is lexically by item
        ret = self.run_run_plus("queue.process_queue", "testqueue", "all", mode="lifo")
        self.assertTrue("items" in ret["return"], msg='Return does not include "items"')
        self.assertEqual(
            ret["return"]["items"],
            ["e", "b", "r", "a", "t", "z"],
            msg='Items returned from process queue runner not as expected (items returned "{0}")'.format(
                ret["return"]["items"]
            ),
        )
