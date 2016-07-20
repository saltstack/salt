# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.pillar import nodegroups

fake_minion_id = 'fake_id'
fake_pillar = {}
fake_nodegroups = {
    'a': fake_minion_id,
    'b': 'nodegroup_b',
}
fake_opts = {'nodegroups': fake_nodegroups, 'id': fake_minion_id}
fake_pillar_name = 'fake_pillar_name'

nodegroups.__opts__ = fake_opts


class NodegroupsPillarTestCase(TestCase):
    '''
    Tests for salt.pillar.nodegroups
    '''

    def _runner(self, expected_ret, pillar_name=None):
        pillar_name = pillar_name or fake_pillar_name
        actual_ret = nodegroups.ext_pillar(fake_minion_id, fake_pillar, pillar_name=pillar_name)
        self.assertDictEqual(actual_ret, expected_ret)

    def test_succeeds(self):
        ret = {fake_pillar_name: ['a', ]}
        self._runner(ret)
