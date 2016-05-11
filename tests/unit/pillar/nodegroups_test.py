# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, call, patch
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.pillar import nodegroups

fake_minion_id = 'fake_id'
fake_pillar = {}
fake_nodegroups = {
    'a': 'nodegroup_a',
    'b': 'nodegroup_b',
}
fake_opts = {'nodegroups': fake_nodegroups, }
fake_pillar_name = 'fake_pillar_name'

nodegroups.__opts__ = fake_opts


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NodegroupsPillarTestCase(TestCase):
    '''
    Tests for salt.pillar.nodegroups
    '''

    def _runner(self, expected_ret, pillar_name=None, nodegroup_matches=None):
        pillar_name = pillar_name or fake_pillar_name
        nodegroup_matches = nodegroup_matches or [True, False, ]
        mock_nodegroup_match = MagicMock(side_effect=nodegroup_matches)
        with patch.object(nodegroups.Matcher, 'nodegroup_match', mock_nodegroup_match):
            actual_ret = nodegroups.ext_pillar(fake_minion_id, fake_pillar, pillar_name=pillar_name)
        self.assertDictEqual(actual_ret, expected_ret)
        fake_nodegroup_count = len(fake_nodegroups)
        self.assertEqual(mock_nodegroup_match.call_count, fake_nodegroup_count)
        mock_nodegroup_match.assert_has_calls([call(x, fake_nodegroups) for x in fake_nodegroups.keys()])

    def test_succeeds(self):
        ret = {fake_pillar_name: ['a', ]}
        self._runner(ret)
