# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Eric Radman <ericshane@eradman.com`
'''

# Import python libs
from __future__ import absolute_import
import tempfile
import os.path

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

# Import Salt libs
import tests.integration as integration
from salt.states import saltmod


@skipIf(NO_MOCK, NO_MOCK_REASON)
class StatemodTests(TestCase):
    def setUp(self):
        self.tmp_cachedir = tempfile.mkdtemp(dir=integration.TMP)

    @patch('salt.states.saltmod.__salt__', MagicMock())
    def test_statemod_state(self):
        ''' Smoke test for for salt.states.statemod.state().  Ensures that we
            don't take an exception if optional parameters are not specified in
            __opts__ or __env__.
        '''
        argv = []
        saltmod.__opts__ = {
            'id': 'webserver2',
            'argv': argv,
            '__role': 'master',
            'cachedir': self.tmp_cachedir,
            'extension_modules': os.path.join(self.tmp_cachedir, 'extmods'),
        }
        args = ('webserver_setup', 'webserver2')
        kwargs = {
            'tgt_type': 'glob',
            'fail_minions': None,
            'pillar': None,
            'top': None,
            'batch': None,
            'orchestration_jid': None,
            'sls': 'vroom',
            'queue': False,
            'concurrent': False,
            'highstate': None,
            'expr_form': None,
            'ret': '',
            'ssh': False,
            'timeout': None, 'test': False,
            'allow_fail': 0,
            'saltenv': None,
            'expect_minions': False
        }
        ret = saltmod.state(*args, **kwargs)
        expected = {
            'comment': 'States ran successfully.',
            'changes': {},
            'name': 'webserver_setup',
            'result': True
        }
        self.assertEqual(ret, expected)
