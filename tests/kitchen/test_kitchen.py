# -*- coding: utf-8 -*-
'''
Test wrapper for running all KitchenSalt tests

All directories in 'tests/kitchen/' will be treated as a separate test under
the KitchenTestCase.
'''
from __future__ import absolute_import
import os

from tests.support.unit import TestCase, skipIf
import setup

import salt.utils.path
from salt.modules import cmdmod as cmd

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))


@skipIf(not salt.utils.path.which('bundle'), 'Bundler is not installed')
class KitchenTestCase(TestCase):
    '''
    Test kitchen environments
    '''
    @classmethod
    def setUpClass(cls):
        '''
        setup kitchen tests
        '''
        cls.topdir = '/' + os.path.join(*CURRENT_DIR.split('/')[:-2])
        cls.use_vt = int(os.environ.get('TESTS_LOG_LEVEL')) >= 5
        cmd.run('python setup.py sdist', cwd=cls.topdir)
        cmd.run('bundle install', cwd=CURRENT_DIR)
        cls.env = {
            'KITCHEN_YAML': os.path.join(CURRENT_DIR, '.kitchen.yml'),
            'SALT_SDIST_PATH': os.path.join(cls.topdir, 'dist', 'salt-{0}.tar.gz'.format(setup.__version__)),
        }

    @classmethod
    def tearDownClass(cls):
        del cls.topdir
        del cls.env

    def tearDown(self):
        cmd.run(
            'bundle exec kitchen destroy all',
            cwd=os.path.join(CURRENT_DIR, 'tests', self.testdir),
            env=self.env,
            use_vt=self.use_vt,
        )
        del self.testdir


def func_builder(testdir):
    def func(self):
        self.testdir = testdir
        if 'TESTS_XML_OUTPUT_DIR' in os.environ:
            self.env['TESTS_JUNIT_XML_PATH'] = '{0}/kitchen.tests.{1}.$KITCHEN_SUITE.$KITCHEN_PLATFORM.xml'.format(
                os.environ.get('TESTS_XML_OUTPUT_DIR'),
                self.testdir,
            )
        self.assertEqual(
            cmd.retcode(
                'bundle exec kitchen converge -c 999 all',
                cwd=os.path.join(CURRENT_DIR, 'tests', self.testdir),
                env=self.env,
                use_vt=self.use_vt,
            ),
            0
        )
        self.assertEqual(
            cmd.retcode(
                'bundle exec kitchen verify all',
                cwd=os.path.join(CURRENT_DIR, 'tests', self.testdir),
                env=self.env,
                use_vt=self.use_vt,
            ),
            0
        )
    return func

for testdir in os.listdir(os.path.join(CURRENT_DIR, 'tests')):
    setattr(KitchenTestCase, 'test_kitchen_{0}'.format(testdir), func_builder(testdir))
