# -*- coding: utf-8 -*-
'''
Raet Ioflo Behavior Unittests
'''
from __future__ import absolute_import, print_function, unicode_literals
import sys
from salt.ext.six.moves import map
import importlib
# pylint: disable=blacklisted-import
if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest
# pylint: enable=blacklisted-import
import time

from ioflo.base.consoling import getConsole
console = getConsole()
from ioflo.aid.odicting import odict
from ioflo.test import testing

from raet.abiding import ns2u
from raet.lane.stacking import LaneStack
from raet.road.stacking import RoadStack

import salt.utils.stringutils
from salt.utils.event import tagify


def setUpModule():
    console.reinit(verbosity=console.Wordage.concise)


def tearDownModule():
    pass


class StatsEventerTestCase(testing.FrameIofloTestCase):
    '''
    Test case for Salt Raet Stats Eventer Master and Minion deeds
    '''

    def setUp(self):
        '''
        Call super if override so House Framer and Frame are setup correctly
        '''
        behaviors = ['salt.daemons.flo', 'salt.daemons.test.plan']
        for behavior in behaviors:
            mod = importlib.import_module(behavior)
        super(StatsEventerTestCase, self).setUp()

    def tearDown(self):
        '''
        Call super if override so House Framer and Frame are torn down correctly
        '''
        super(StatsEventerTestCase, self).tearDown()

    def testMasterContextSetup(self):
        '''
        Test the context setup procedure used in all the consequence tests works as expected
        This test intended to avoid some checks in other tests
        '''
        console.terse("{0}\n".format(self.testMasterContextSetup.__doc__))

        act = self.addEnterDeed("TestOptsSetupMaster")
        self.assertIn(act, self.frame.enacts)
        self.assertEqual(act.actor, "TestOptsSetupMaster")
        act = self.addEnterDeed("SaltRaetManorLaneSetup")
        self.assertIn(act, self.frame.enacts)
        self.assertEqual(act.actor, "SaltRaetManorLaneSetup")
        act = self.addEnterDeed("SaltRaetRoadStackSetup")
        self.assertIn(act, self.frame.enacts)
        self.assertEqual(act.actor, "SaltRaetRoadStackSetup")
        act = self.addEnterDeed("StatsMasterTestSetup")
        self.assertIn(act, self.frame.enacts)
        self.assertEqual(act.actor, "StatsMasterTestSetup")

        act = self.addRecurDeed("SaltRaetStatsEventer")
        self.assertIn(act, self.frame.reacts)
        self.assertEqual(act.actor, "SaltRaetStatsEventer")

        self.resolve()  # resolve House, Framer, Frame, Acts, Actors

        self.frame.enter()
        self.assertDictEqual(
                act.actor.Ioinits,
                {'opts': salt.utils.stringutils.to_str('.salt.opts'),
                 'stats_req': salt.utils.stringutils.to_str('.salt.stats.event_req'),
                 'lane_stack': salt.utils.stringutils.to_str('.salt.lane.manor.stack'),
                 'road_stack': salt.utils.stringutils.to_str('.salt.road.manor.stack')})

        self.assertTrue(hasattr(act.actor, 'opts'))
        self.assertTrue(hasattr(act.actor, 'stats_req'))
        self.assertTrue(hasattr(act.actor, 'lane_stack'))
        self.assertTrue(hasattr(act.actor, 'road_stack'))
        self.assertIsInstance(act.actor.lane_stack.value, LaneStack)
        self.assertIsInstance(act.actor.road_stack.value, RoadStack)
        self.frame.recur()

        # Close active stacks servers
        act.actor.lane_stack.value.server.close()
        testStack = self.store.fetch('.salt.test.lane.stack')
        if testStack:
            testStack.value.server.close()
        act.actor.road_stack.value.server.close()

    def testMasterRoadStats(self):
        '''
        Test Master Road Stats request (A1)
        '''
        console.terse("{0}\n".format(self.testMasterRoadStats.__doc__))

        # Bootstrap
        self.addEnterDeed("TestOptsSetupMaster")
        self.addEnterDeed("SaltRaetManorLaneSetup")
        self.addEnterDeed("SaltRaetRoadStackSetup")
        self.addEnterDeed("StatsMasterTestSetup")
        act = self.addRecurDeed("SaltRaetStatsEventerMaster")
        self.resolve()  # resolve House, Framer, Frame, Acts, Actors
        self.frame.enter()

        # Prepare
        # add a test stat key-value
        roadStack = self.store.fetch('.salt.road.manor.stack')
        laneStack = self.store.fetch('.salt.lane.manor.stack')
        roadStack.value.stats['test_stats_event'] = 111
        # ensure stats are equal to expected
        self.assertDictEqual(roadStack.value.stats, {'test_stats_event': 111})
        self.assertDictEqual(laneStack.value.stats, {})

        # add stats request
        testStack = self.store.fetch('.salt.test.lane.stack').value
        statsReq = self.store.fetch('.salt.stats.event_req').value
        tag = tagify('road', 'stats')
        # road stats request
        statsReq.append({'route': {'dst': (None, None, 'stats_req'),
                                   'src': (None, testStack.local.name, None)},
                         'tag': tag})

        # Test
        self.frame.recur()  # run in frame

        # Check
        self.assertEqual(len(testStack.rxMsgs), 0)
        testStack.serviceAll()
        self.assertEqual(len(testStack.rxMsgs), 1)

        msg, sender = testStack.rxMsgs.popleft()
        self.assertDictEqual(msg, {'route': {'src': [None, 'manor', None],
                                             'dst': [None, None, 'event_fire']},
                                   'tag': tag,
                                   'data': {'test_stats_event': 111}})

        # Close active stacks servers
        act.actor.lane_stack.value.server.close()
        act.actor.road_stack.value.server.close()
        testStack = self.store.fetch('.salt.test.lane.stack')
        if testStack:
            testStack.value.server.close()
        time.sleep(0.1)

    def testMasterLaneStats(self):
        '''
        Test Master Road Stats request (A2)
        '''
        console.terse("{0}\n".format(self.testMasterLaneStats.__doc__))

        # Bootstrap
        self.addEnterDeed("TestOptsSetupMaster")
        self.addEnterDeed("SaltRaetManorLaneSetup")
        self.addEnterDeed("SaltRaetRoadStackSetup")
        self.addEnterDeed("StatsMasterTestSetup")
        act = self.addRecurDeed("SaltRaetStatsEventerMaster")
        self.resolve()  # resolve House, Framer, Frame, Acts, Actors
        self.frame.enter()

        # Prepare
        # add a test stat key-value
        roadStack = self.store.fetch('.salt.road.manor.stack')
        laneStack = self.store.fetch('.salt.lane.manor.stack')
        laneStack.value.stats['test_stats_event'] = 111
        # ensure stats are equal to expected
        self.assertDictEqual(roadStack.value.stats, {})
        self.assertDictEqual(laneStack.value.stats, {'test_stats_event': 111})

        # add stats request
        testStack = self.store.fetch('.salt.test.lane.stack').value
        statsReq = self.store.fetch('.salt.stats.event_req').value
        tag = tagify('lane', 'stats')
        # lane stats request
        statsReq.append({'route': {'dst': (None, None, 'stats_req'),
                                   'src': (None, testStack.local.name, None)},
                         'tag': tag})

        # Test
        self.frame.recur()  # run in frame

        # Check
        self.assertEqual(len(testStack.rxMsgs), 0)
        testStack.serviceAll()
        self.assertEqual(len(testStack.rxMsgs), 1)

        msg, sender = testStack.rxMsgs.popleft()
        self.assertDictEqual(msg, {'route': {'src': [None, 'manor', None],
                                             'dst': [None, None, 'event_fire']},
                                   'tag': tag,
                                   'data': {'test_stats_event': 111}})

        # Close active stacks servers
        act.actor.lane_stack.value.server.close()
        act.actor.road_stack.value.server.close()
        testStack = self.store.fetch('.salt.test.lane.stack')
        if testStack:
            testStack.value.server.close()

    def testMasterStatsWrongMissingTag(self):
        '''
        Test Master Stats requests with unknown and missing tag (A3, A4)
        '''
        console.terse("{0}\n".format(self.testMasterStatsWrongMissingTag.__doc__))

        # Bootstrap
        self.addEnterDeed("TestOptsSetupMaster")
        self.addEnterDeed("SaltRaetManorLaneSetup")
        self.addEnterDeed("SaltRaetRoadStackSetup")
        self.addEnterDeed("StatsMasterTestSetup")
        act = self.addRecurDeed("SaltRaetStatsEventerMaster")
        self.resolve()  # resolve House, Framer, Frame, Acts, Actors
        self.frame.enter()

        # Prepare
        # add a test stat key-value
        roadStack = self.store.fetch('.salt.road.manor.stack')
        laneStack = self.store.fetch('.salt.lane.manor.stack')
        roadStack.value.stats['test_road_stats_event'] = 111
        laneStack.value.stats['test_lane_stats_event'] = 222
        # ensure stats are equal to expected
        self.assertDictEqual(roadStack.value.stats, {'test_road_stats_event': 111})
        self.assertDictEqual(laneStack.value.stats, {'test_lane_stats_event': 222})

        # add stats request
        testStack = self.store.fetch('.salt.test.lane.stack').value
        statsReq = self.store.fetch('.salt.stats.event_req').value
        tag = 'salt/unknown/tag'
        self.assertNotEqual(tag, tagify('lane', 'stats'))
        self.assertNotEqual(tag, tagify('road', 'stats'))
        # unknown tag in stats request
        statsReq.append({'route': {'dst': (None, None, 'stats_req'),
                                   'src': (None, testStack.local.name, None)},
                         'tag': tag})
        # no tag in stats request
        statsReq.append({'route': {'dst': (None, None, 'stats_req'),
                                   'src': (None, testStack.local.name, None)}})

        # Test
        self.frame.recur()  # run in frame

        # Check
        self.assertEqual(len(testStack.rxMsgs), 0)
        testStack.serviceAll()
        self.assertEqual(len(testStack.rxMsgs), 0)

        # Close active stacks servers
        act.actor.lane_stack.value.server.close()
        act.actor.road_stack.value.server.close()
        testStack = self.store.fetch('.salt.test.lane.stack')
        if testStack:
            testStack.value.server.close()

    def testMasterStatsUnknownRemote(self):
        '''
        Test Master Stats request with unknown remote (B1)
        '''
        console.terse("{0}\n".format(self.testMasterStatsUnknownRemote.__doc__))

        # Bootstrap
        self.addEnterDeed("TestOptsSetupMaster")
        self.addEnterDeed("SaltRaetManorLaneSetup")
        self.addEnterDeed("SaltRaetRoadStackSetup")
        self.addEnterDeed("StatsMasterTestSetup")
        act = self.addRecurDeed("SaltRaetStatsEventerMaster")
        self.resolve()  # resolve House, Framer, Frame, Acts, Actors
        self.frame.enter()

        # Prepare
        # add a test stat key-value
        roadStack = self.store.fetch('.salt.road.manor.stack')
        laneStack = self.store.fetch('.salt.lane.manor.stack')
        roadStack.value.stats['test_road_stats_event'] = 111
        laneStack.value.stats['test_lane_stats_event'] = 222
        # ensure stats are equal to expected
        self.assertDictEqual(roadStack.value.stats, {'test_road_stats_event': 111})
        self.assertDictEqual(laneStack.value.stats, {'test_lane_stats_event': 222})

        # add stats request
        testStack = self.store.fetch('.salt.test.lane.stack').value
        statsReq = self.store.fetch('.salt.stats.event_req').value
        tag = tagify('road', 'stats')
        # unknown tag in stats request
        unknownName = 'unknownName'
        statsReq.append({'route': {'dst': (None, None, 'stats_req'),
                                   'src': (None, unknownName, None)},
                         'tag': tag})

        # Test
        self.frame.recur()  # run in frame

        # Check
        self.assertEqual(len(testStack.rxMsgs), 0)
        testStack.serviceAll()
        self.assertEqual(len(testStack.rxMsgs), 0)

        # Close active stacks servers
        act.actor.lane_stack.value.server.close()
        act.actor.road_stack.value.server.close()
        testStack = self.store.fetch('.salt.test.lane.stack')
        if testStack:
            testStack.value.server.close()

    def testMasterStatsNoRequest(self):
        '''
        Test Master Stats no requests (nothing to do) (B2)
        '''
        console.terse("{0}\n".format(self.testMasterStatsNoRequest.__doc__))

        # Bootstrap
        self.addEnterDeed("TestOptsSetupMaster")
        self.addEnterDeed("SaltRaetManorLaneSetup")
        self.addEnterDeed("SaltRaetRoadStackSetup")
        self.addEnterDeed("StatsMasterTestSetup")
        act = self.addRecurDeed("SaltRaetStatsEventerMaster")
        self.resolve()  # resolve House, Framer, Frame, Acts, Actors
        self.frame.enter()

        # Prepare
        # add a test stat key-value
        roadStack = self.store.fetch('.salt.road.manor.stack')
        laneStack = self.store.fetch('.salt.lane.manor.stack')
        roadStack.value.stats['test_road_stats_event'] = 111
        laneStack.value.stats['test_lane_stats_event'] = 222
        # ensure stats are equal to expected
        self.assertDictEqual(roadStack.value.stats, {'test_road_stats_event': 111})
        self.assertDictEqual(laneStack.value.stats, {'test_lane_stats_event': 222})

        # add stats request
        testStack = self.store.fetch('.salt.test.lane.stack').value
        statsReq = self.store.fetch('.salt.stats.event_req').value
        # no requests
        self.assertEqual(len(statsReq), 0)

        # Test
        self.frame.recur()  # run in frame

        # Check
        self.assertEqual(len(testStack.rxMsgs), 0)
        testStack.serviceAll()
        self.assertEqual(len(testStack.rxMsgs), 0)

        # Close active stacks servers
        act.actor.lane_stack.value.server.close()
        act.actor.road_stack.value.server.close()
        testStack = self.store.fetch('.salt.test.lane.stack')
        if testStack:
            testStack.value.server.close()

    def testMinionContextSetup(self):
        '''
        Test the context setup procedure used in all the consequence tests works as expected
        This test intended to avoid some checks in other tests
        '''
        console.terse("{0}\n".format(self.testMinionContextSetup.__doc__))

        act = self.addEnterDeed("TestOptsSetupMinion")
        self.assertIn(act, self.frame.enacts)
        self.assertEqual(act.actor, "TestOptsSetupMinion")
        act = self.addEnterDeed("SaltRaetManorLaneSetup")
        self.assertIn(act, self.frame.enacts)
        self.assertEqual(act.actor, "SaltRaetManorLaneSetup")
        act = self.addEnterDeed("SaltRaetRoadStackSetup")
        self.assertIn(act, self.frame.enacts)
        self.assertEqual(act.actor, "SaltRaetRoadStackSetup")
        act = self.addEnterDeed("StatsMinionTestSetup")
        self.assertIn(act, self.frame.enacts)
        self.assertEqual(act.actor, "StatsMinionTestSetup")

        act = self.addRecurDeed("SaltRaetStatsEventer")
        self.assertIn(act, self.frame.reacts)
        self.assertEqual(act.actor, "SaltRaetStatsEventer")

        self.resolve()  # resolve House, Framer, Frame, Acts, Actors

        self.frame.enter()
        self.assertDictEqual(
                act.actor.Ioinits,
                {'opts': salt.utils.stringutils.to_str('.salt.opts'),
                 'stats_req': salt.utils.stringutils.to_str('.salt.stats.event_req'),
                 'lane_stack': salt.utils.stringutils.to_str('.salt.lane.manor.stack'),
                 'road_stack': salt.utils.stringutils.to_str('.salt.road.manor.stack')})

        self.assertTrue(hasattr(act.actor, 'opts'))
        self.assertTrue(hasattr(act.actor, 'stats_req'))
        self.assertTrue(hasattr(act.actor, 'lane_stack'))
        self.assertTrue(hasattr(act.actor, 'road_stack'))
        self.assertIsInstance(act.actor.lane_stack.value, LaneStack)
        self.assertIsInstance(act.actor.road_stack.value, RoadStack)
        self.frame.recur()

        # Close active stacks servers
        act.actor.lane_stack.value.server.close()
        testStack = self.store.fetch('.salt.test.road.stack')
        if testStack:
            testStack.value.server.close()
        act.actor.road_stack.value.server.close()

    def testMinionRoadStats(self):
        '''
        Test Minion Road Stats request (A1)
        '''
        console.terse("{0}\n".format(self.testMinionRoadStats.__doc__))

        # Bootstrap
        self.addEnterDeed("TestOptsSetupMinion")
        self.addEnterDeed("SaltRaetManorLaneSetup")
        self.addEnterDeed("SaltRaetRoadStackSetup")
        self.addEnterDeed("StatsMinionTestSetup")
        act = self.addRecurDeed("SaltRaetStatsEventerMinion")
        self.resolve()  # resolve House, Framer, Frame, Acts, Actors
        self.frame.enter()

        # Prepare
        # add a test stat key-value
        roadStack = self.store.fetch('.salt.road.manor.stack')
        laneStack = self.store.fetch('.salt.lane.manor.stack')
        roadStack.value.stats = odict({'test_stats_event': 111})
        laneStack.value.stats = odict()
        # ensure stats are equal to expected
        self.assertDictEqual(roadStack.value.stats, {'test_stats_event': 111})
        self.assertDictEqual(laneStack.value.stats, {})

        # add stats request
        testStack = self.store.fetch('.salt.test.road.stack').value
        statsReq = self.store.fetch('.salt.stats.event_req').value
        tag = tagify('road', 'stats')
        minionName = roadStack.value.local.name
        masterName = testStack.local.name
        # road stats request
        statsReq.append({'route': {'dst': (minionName, None, 'stats_req'),
                                   'src': (masterName, None, None)},
                         'tag': tag})

        # Test
        self.frame.recur()  # run in frame

        # Check
        self.assertEqual(len(testStack.rxMsgs), 0)
        testStack.serviceAll()
        self.assertEqual(len(testStack.rxMsgs), 1)

        msg, sender = testStack.rxMsgs.popleft()
        self.assertDictEqual(msg, {'route': {'src': [ns2u(minionName), 'manor', None],
                                             'dst': [ns2u(masterName), None, 'event_fire']},
                                   'tag': ns2u(tag),
                                   'data': {'test_stats_event': 111}})

        # Close active stacks servers
        act.actor.lane_stack.value.server.close()
        act.actor.road_stack.value.server.close()
        testStack = self.store.fetch('.salt.test.road.stack')
        if testStack:
            testStack.value.server.close()

    def testMinionLaneStats(self):
        '''
        Test Minion Road Stats request (A2)
        '''
        console.terse("{0}\n".format(self.testMinionLaneStats.__doc__))

        # Bootstrap
        self.addEnterDeed("TestOptsSetupMinion")
        self.addEnterDeed("SaltRaetManorLaneSetup")
        self.addEnterDeed("SaltRaetRoadStackSetup")
        self.addEnterDeed("StatsMinionTestSetup")
        act = self.addRecurDeed("SaltRaetStatsEventerMinion")
        self.resolve()  # resolve House, Framer, Frame, Acts, Actors
        self.frame.enter()

        # Prepare
        # add a test stat key-value
        roadStack = self.store.fetch('.salt.road.manor.stack')
        laneStack = self.store.fetch('.salt.lane.manor.stack')
        roadStack.value.stats = odict()
        laneStack.value.stats = odict({'test_stats_event': 111})
        # ensure stats are equal to expected
        self.assertDictEqual(roadStack.value.stats, {})
        self.assertDictEqual(laneStack.value.stats, {'test_stats_event': 111})

        # add stats request
        testStack = self.store.fetch('.salt.test.road.stack').value
        statsReq = self.store.fetch('.salt.stats.event_req').value
        tag = tagify('lane', 'stats')
        minionName = roadStack.value.local.name
        masterName = testStack.local.name
        # lane stats request
        statsReq.append({'route': {'dst': (minionName, None, 'stats_req'),
                                   'src': (masterName, None, None)},
                         'tag': tag})

        # Test
        self.frame.recur()  # run in frame

        # Check
        self.assertEqual(len(testStack.rxMsgs), 0)
        testStack.serviceAll()
        self.assertEqual(len(testStack.rxMsgs), 1)

        msg, sender = testStack.rxMsgs.popleft()
        self.assertDictEqual(msg, {'route': {'src': [ns2u(minionName), 'manor', None],
                                             'dst': [ns2u(masterName), None, 'event_fire']},
                                   'tag': ns2u(tag),
                                   'data': {'test_stats_event': 111}})

        # Close active stacks servers
        act.actor.lane_stack.value.server.close()
        act.actor.road_stack.value.server.close()
        testStack = self.store.fetch('.salt.test.road.stack')
        if testStack:
            testStack.value.server.close()

    def testMinionStatsWrongMissingTag(self):
        '''
        Test Minion Stats requests with unknown and missing tag (A3, A4)
        '''
        console.terse("{0}\n".format(self.testMinionStatsWrongMissingTag.__doc__))

        # Bootstrap
        self.addEnterDeed("TestOptsSetupMinion")
        self.addEnterDeed("SaltRaetManorLaneSetup")
        self.addEnterDeed("SaltRaetRoadStackSetup")
        self.addEnterDeed("StatsMinionTestSetup")
        act = self.addRecurDeed("SaltRaetStatsEventerMinion")
        self.resolve()  # resolve House, Framer, Frame, Acts, Actors
        self.frame.enter()

        # Prepare
        # add a test stat key-value
        roadStack = self.store.fetch('.salt.road.manor.stack')
        laneStack = self.store.fetch('.salt.lane.manor.stack')
        roadStack.value.stats = odict({'test_road_stats_event': 111})
        laneStack.value.stats = odict({'test_lane_stats_event': 222})
        # ensure stats are equal to expected
        self.assertDictEqual(roadStack.value.stats, {'test_road_stats_event': 111})
        self.assertDictEqual(laneStack.value.stats, {'test_lane_stats_event': 222})

        # add stats request
        testStack = self.store.fetch('.salt.test.road.stack').value
        statsReq = self.store.fetch('.salt.stats.event_req').value
        tag = 'salt/unknown/tag'
        self.assertNotEqual(tag, tagify('lane', 'stats'))
        self.assertNotEqual(tag, tagify('road', 'stats'))
        minionName = roadStack.value.local.name
        masterName = testStack.local.name
        # unknown tag in stats request
        statsReq.append({'route': {'dst': (minionName, None, 'stats_req'),
                                   'src': (masterName, None, None)},
                         'tag': tag})
        # no tag in stats request
        statsReq.append({'route': {'dst': (minionName, None, 'stats_req'),
                                   'src': (masterName, None, None)}})

        # Test
        self.frame.recur()  # run in frame

        # Check
        self.assertEqual(len(testStack.rxMsgs), 0)
        testStack.serviceAll()
        self.assertEqual(len(testStack.rxMsgs), 0)

        # Close active stacks servers
        act.actor.lane_stack.value.server.close()
        act.actor.road_stack.value.server.close()
        testStack = self.store.fetch('.salt.test.road.stack')
        if testStack:
            testStack.value.server.close()

    def testMinionStatsUnknownRemote(self):
        '''
        Test Minion Stats request with unknown remote (B1)
        '''
        console.terse("{0}\n".format(self.testMinionStatsUnknownRemote.__doc__))

        # Bootstrap
        self.addEnterDeed("TestOptsSetupMinion")
        self.addEnterDeed("SaltRaetManorLaneSetup")
        self.addEnterDeed("SaltRaetRoadStackSetup")
        self.addEnterDeed("StatsMinionTestSetup")
        act = self.addRecurDeed("SaltRaetStatsEventerMinion")
        self.resolve()  # resolve House, Framer, Frame, Acts, Actors
        self.frame.enter()

        # Prepare
        # add a test stat key-value
        roadStack = self.store.fetch('.salt.road.manor.stack')
        laneStack = self.store.fetch('.salt.lane.manor.stack')
        roadStack.value.stats = odict({'test_road_stats_event': 111})
        laneStack.value.stats = odict({'test_lane_stats_event': 222})
        # ensure stats are equal to expected
        self.assertDictEqual(roadStack.value.stats, {'test_road_stats_event': 111})
        self.assertDictEqual(laneStack.value.stats, {'test_lane_stats_event': 222})

        # add stats request
        testStack = self.store.fetch('.salt.test.road.stack').value
        statsReq = self.store.fetch('.salt.stats.event_req').value
        tag = tagify('road', 'stats')
        minionName = roadStack.value.local.name
        # unknown remote (src) name in stats request
        unknownName = 'unknownName'
        statsReq.append({'route': {'dst': (minionName, None, 'stats_req'),
                                   'src': (unknownName, None, None)},
                         'tag': tag})

        # Test
        self.frame.recur()  # run in frame

        # Check
        self.assertEqual(len(testStack.rxMsgs), 0)
        testStack.serviceAll()
        self.assertEqual(len(testStack.rxMsgs), 0)

        # Close active stacks servers
        act.actor.lane_stack.value.server.close()
        act.actor.road_stack.value.server.close()
        testStack = self.store.fetch('.salt.test.road.stack')
        if testStack:
            testStack.value.server.close()

    def testMinionStatsNoRequest(self):
        '''
        Test Minion Stats no requests (nothing to do) (B2)
        '''
        console.terse("{0}\n".format(self.testMinionStatsNoRequest.__doc__))

        # Bootstrap
        self.addEnterDeed("TestOptsSetupMinion")
        self.addEnterDeed("SaltRaetManorLaneSetup")
        self.addEnterDeed("SaltRaetRoadStackSetup")
        self.addEnterDeed("StatsMinionTestSetup")
        act = self.addRecurDeed("SaltRaetStatsEventerMinion")
        self.resolve()  # resolve House, Framer, Frame, Acts, Actors
        self.frame.enter()

        # Prepare
        # add a test stat key-value
        roadStack = self.store.fetch('.salt.road.manor.stack')
        laneStack = self.store.fetch('.salt.lane.manor.stack')
        roadStack.value.stats = odict({'test_road_stats_event': 111})
        laneStack.value.stats = odict({'test_lane_stats_event': 222})
        # ensure stats are equal to expected
        self.assertDictEqual(roadStack.value.stats, {'test_road_stats_event': 111})
        self.assertDictEqual(laneStack.value.stats, {'test_lane_stats_event': 222})
        # clear lane stack remotes

        # add stats request
        testStack = self.store.fetch('.salt.test.road.stack').value
        statsReq = self.store.fetch('.salt.stats.event_req').value
        # no request
        self.assertEqual(len(statsReq), 0)

        # Test
        self.frame.recur()  # run in frame

        # Check
        self.assertEqual(len(testStack.rxMsgs), 0)
        testStack.serviceAll()
        self.assertEqual(len(testStack.rxMsgs), 0)

        # Close active stacks servers
        act.actor.lane_stack.value.server.close()
        act.actor.road_stack.value.server.close()
        testStack = self.store.fetch('.salt.test.road.stack')
        if testStack:
            testStack.value.server.close()


def runOne(test):
    '''
    Unittest Runner
    '''
    test = StatsEventerTestCase(test)
    suite = unittest.TestSuite([test])
    unittest.TextTestRunner(verbosity=2).run(suite)


def runSome():
    '''
    Unittest runner
    '''
    tests = []
    names = [
        'testMasterContextSetup',
        'testMasterRoadStats',
        'testMasterLaneStats',
        'testMasterStatsWrongMissingTag',
        'testMasterStatsUnknownRemote',
        'testMasterStatsNoRequest',
        'testMinionContextSetup',
        'testMinionRoadStats',
        'testMinionLaneStats',
        'testMinionStatsWrongMissingTag',
        'testMinionStatsUnknownRemote',
        'testMinionStatsNoRequest',
        ]
    tests.extend(list(map(StatsEventerTestCase, names)))
    suite = unittest.TestSuite(tests)
    unittest.TextTestRunner(verbosity=2).run(suite)


def runAll():
    '''
    Unittest runner
    '''
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(StatsEventerTestCase))
    unittest.TextTestRunner(verbosity=2).run(suite)


if __name__ == '__main__' and __package__ is None:

    # console.reinit(verbosity=console.Wordage.concise)

    runAll()  # run all unittests

    #runSome()  # only run some

    #runOne('testMasterLaneStats')
