# -*- coding: utf-8 -*-
'''
tests for docker module
'''

# Import Python libs
from __future__ import absolute_import
import textwrap
import os
import json
from subprocess import Popen, PIPE
# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import skipIf
# Import salt libs
import salt.version

NO_DOCKERPY = False
NO_DOCKERPY = False
try:
    import docker  # pylint: disable=import-error,unused-import
except ImportError:
    NO_DOCKERPY = True
# Checking if docker is running.
PROCESS = Popen('docker ps -a', shell=True, stdout=PIPE, stderr=PIPE)
OUTPUT = PROCESS.communicate()[0]

if PROCESS.returncode != 0:
    NO_DOCKERPY = True

if not salt.utils.which('docker'):
    NO_DOCKERPY = True

STATE_DIR = os.path.join(integration.FILES, 'file', 'base')


@skipIf(
    NO_DOCKERPY,
    'Please install docker-py  '
    'and make sure docker daemon is ruuning before running '
    'Docker integration tests. '
)
@skipIf(salt.utils.which('docker') is None, 'Docker is not installed')
class TestModuleDockereng(integration.ModuleCase,
                          integration.AdaptedConfigurationTestCaseMixIn):
    '''
    Validate the test module
    '''
    def setUp(self):
        '''
        Setup
        '''
        self.state_name = 'docker_top'
        state_filename = self.state_name + '.sls'
        self.state_file = os.path.join(STATE_DIR, state_filename)
        with salt.utils.fopen(self.state_file, 'w') as fb_:
            fb_.write(textwrap.dedent('''
                foo:
                  dockerng.running:
                    - image: ubuntu
                    - detach: True
                    - command: bash
                    - interactive: True
                    - environment:
                      - VAR1: value1
                      - VAR2: value2
                      - VAR3: value3
                        '''))
        self.run_function('state.sls', [self.state_name])
        super(TestModuleDockereng, self).setUp()

    def tearDown(self):
        '''
        remove files created in previous tests
        '''
        try:
            os.remove(self.state_file)
        except OSError:
            pass
        self.run_function('cmd.run', ['docker kill foo'])

    def test_docker_env(self):
        '''
        dockerng.running environnment part.
        '''
        with salt.utils.fopen(self.state_file, 'w') as fb_:
            fb_.write(textwrap.dedent('''
                foo:
                  dockerng.running:
                    - image: ubuntu
                    - detach: True
                    - command: bash
                    - interactive: True
                    - environment:
                      - VAR1: value1
                      #- VAR2: value2
                      - VAR3: value3
                        '''))
        ret = self.run_function('state.sls', [self.state_name])
        self.assertEqual(ret['dockerng_|-foo_|-foo_|-running']['comment'],
                         'Container \'foo\' was replaced')
        self.assertEqual(ret['dockerng_|-foo_|-foo_|-running']['changes']['diff']
                         ['environment']['old']['VAR2'], 'value2')
        ret = self.run_function('cmd.run', ['docker inspect foo'])
        container_json_data = json.loads(ret)
        container_data = container_json_data[0]
        self.assertIn('VAR1=value1', container_data['Config']['Env'])
        self.assertIn('VAR3=value3', container_data['Config']['Env'])
        self.assertNotIn('VAR2=value2', container_data['Config']['Env'])

        # Running same state to make sure that container should not get restarted every time
        ret = self.run_function('state.sls', [self.state_name])
        self.assertEqual(ret['dockerng_|-foo_|-foo_|-running']['comment'],
                         'Container \'foo\' is already configured as specified')
