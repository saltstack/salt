# -*- coding: utf-8 -*-
'''
Tests for runner_returns
'''
# Import Python libs
from __future__ import absolute_import
import errno
import os
import tempfile
import yaml

# Import Salt Testing libs
from tests.support.case import ShellCase
from tests.support.runtests import RUNTIME_VARS

# Import salt libs
import salt.payload
import salt.utils
import salt.utils.jid


class RunnerReturnsTest(ShellCase):
    '''
    Test the "runner_returns" feature
    '''
    def setUp(self):
        '''
        Create the temp file and master.d directory
        '''
        self.job_dir = os.path.join(self.master_opts['cachedir'], 'jobs')
        self.hash_type = self.master_opts['hash_type']
        self.master_d_dir = os.path.join(self.get_config_dir(), 'master.d')
        try:
            os.makedirs(self.master_d_dir)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise

        self.conf = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.conf',
            dir=self.master_d_dir,
            delete=True,
        )

    def tearDown(self):
        '''
        Close the tempfile.NamedTemporaryFile object, cleaning it up
        '''
        self.conf.close()
        # Force a reload of the configuration now that our temp config file has
        # been removed.
        self.run_run_plus('test.arg', __reload_config=True)

    @staticmethod
    def clean_return(data):
        '''
        Remove kwargs and timestamp (things that are variable) so we have a
        stable value to assert
        '''
        # Remove pub_kwargs
        data['fun_args'][1] = \
            salt.utils.clean_kwargs(**data['fun_args'][1])
        data['return']['kwargs'] = \
            salt.utils.clean_kwargs(**data['return']['kwargs'])

        # Pop off the timestamp (do not provide a 2nd argument, if the stamp is
        # missing we want to know!)
        data.pop('_stamp')

    def write_conf(self, data):
        '''
        Dump the config dict to the conf file
        '''
        self.conf.write(yaml.dump(data, default_flow_style=False))
        self.conf.flush()

    def test_runner_returns_disabled(self):
        '''
        Test with runner_returns enabled
        '''
        self.write_conf({'runner_returns': False})
        ret = self.run_run_plus(
            'test.arg',
            'foo',
            bar='hello world!',
            __reload_config=True)

        jid = ret.get('jid')
        if jid is None:
            raise Exception('jid missing from run_run_plus output')

        serialized_return = os.path.join(
            salt.utils.jid.jid_dir(jid, self.job_dir, self.hash_type),
            'master',
            'return.p',
        )
        self.assertFalse(os.path.isfile(serialized_return))

    def test_runner_returns_enabled(self):
        '''
        Test with runner_returns enabled
        '''
        self.write_conf({'runner_returns': True})
        ret = self.run_run_plus(
            'test.arg',
            'foo',
            bar='hello world!',
            __reload_config=True)

        jid = ret.get('jid')
        if jid is None:
            raise Exception('jid missing from run_run_plus output')

        serialized_return = os.path.join(
            salt.utils.jid.jid_dir(jid, self.job_dir, self.hash_type),
            'master',
            'return.p',
        )
        serial = salt.payload.Serial(self.master_opts)
        with salt.utils.fopen(serialized_return, 'rb') as fp_:
            deserialized = serial.loads(fp_.read())

        self.clean_return(deserialized['return'])

        # Now we have something sane we can reliably compare in an assert.
        self.assertEqual(
            deserialized,
            {'return': {'fun': 'runner.test.arg',
                        'fun_args': ['foo', {'bar': 'hello world!'}],
                        'jid': jid,
                        'return': {'args': ['foo'], 'kwargs': {'bar': 'hello world!'}},
                        'success': True,
                        'user': RUNTIME_VARS.RUNNING_TESTS_USER}}
                        'user': 'root'}}
        )
