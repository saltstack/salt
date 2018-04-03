
# -*- coding: utf-8 -*-
'''
Test roster default rendering
'''

# Import python libs
from __future__ import absolute_import
import os
import shutil
import tempfile

# Import Salt Testing libs
from tests.support.unit import TestCase
from tests.support.mock import MagicMock, patch
from tests.support.paths import TMP

# Import Salt libs
import salt.roster
import salt.config
import salt.utils.files
import salt.utils.yaml

ROSTER = '''
localhost:
  host: 127.0.0.1
  port: 2827
self:
  host: 0.0.0.0
  port: 42
'''


class SSHRosterDefaults(TestCase):
    def test_roster_defaults_flat(self):
        '''
        Test Roster Defaults on the flat roster
        '''
        tempdir = tempfile.mkdtemp(dir=TMP)
        expected = {
            'self': {
                'host': '0.0.0.0',
                'user': 'daniel',
                'port': 42,
            },
            'localhost': {
                'host': '127.0.0.1',
                'user': 'daniel',
                'port': 2827,
            },
        }
        try:
            root_dir = os.path.join(tempdir, 'foo', 'bar')
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, 'config')
            with salt.utils.files.fopen(fpath, 'w') as fp_:
                fp_.write(
                    '''
                    roster_defaults:
                      user: daniel
                    '''
                )
            opts = salt.config.master_config(fpath)
            with patch('salt.roster.get_roster_file', MagicMock(return_value=ROSTER)):
                with patch('salt.template.compile_template', MagicMock(return_value=salt.utils.yaml.safe_load(ROSTER))):
                    roster = salt.roster.Roster(opts=opts)
                    self.assertEqual(roster.targets('*', 'glob'), expected)
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)
